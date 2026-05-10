from contextlib import asynccontextmanager
from datetime import UTC, datetime
import asyncio
import logging
from pathlib import Path
from time import perf_counter
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.gzip import GZipMiddleware

from backend.config import settings
from backend.database import AsyncSessionLocal, get_db
from backend.i18n import DATE_FORMAT_HINT, build_error_payload, error_detail, parse_accept_language
from backend.models import Base
from backend.openapi import API_DESCRIPTION, API_SUMMARY, API_VERSION, configure_openapi
from backend.rate_limit import RateLimitRule, RateLimiter
from backend.routers import (
    assignments_router,
    attendance_router,
    admin_router,
    audit_router,
    auth_router,
    backups_router,
    compliance_router,
    compliance_reports_router,
    curriculum_router,
    dashboard_router,
    exports_router,
    family_settings_router,
    gradebook_router,
    grades_router,
    invitations_router,
    lesson_plans_router,
    notifications_router,
    portfolio_router,
    quizzes_router,
    report_cards_router,
    restore_router,
    reviews_router,
    schedule_router,
    search_router,
    students_router,
    subjects_router,
    submissions_router,
    transcripts_router,
    users_router,
)
from backend.routers.calendar import router as calendar_router
from backend.routers.grading import router as grading_router
from backend.routers.health import router as health_router
from backend.routers.imports import router as imports_router
from backend.services.capabilities import get_auth_providers, get_capability_registry
from backend.services.backup_service import get_backup_scheduler
from backend.services.grading_worker import create_worker
from backend.services.health import build_simple_health_payload, get_runtime_started_at, log_startup_health_snapshot
from backend.services.logging_config import bind_context, configure_logging, log_action, reset_context, update_context
from backend.services.maintenance import get_maintenance_status, session_can_bypass_maintenance
from backend.services.monitoring import collect_metrics_payload, get_monitoring, install_monitoring
from backend.seed_demo import seed_demo_data
from backend.startup import (
    ensure_database_migrations,
    ensure_auth_runtime_configured,
    log_validated_config_summary,
    validate_runtime_config,
)
from backend.security import (
    get_request_ip,
    is_secure_request,
    require_csrf,
    session_needs_rotation,
    set_session_cookies,
    verify_session_token,
)

API_PREFIX = settings.api_prefix.rstrip('/')
OPENAPI_PATH = f'{API_PREFIX}/openapi.json'
DOCS_PATH = f'{API_PREFIX}/docs'
REDOC_PATH = f'{API_PREFIX}/redoc'
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
FRONTEND_INDEX = FRONTEND_DIST_DIR / 'index.html'
HEALTH_PATHS = {f'{API_PREFIX}/health', f'{API_PREFIX}/health/ready', '/health'}
logger = logging.getLogger(__name__)
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
PUBLIC_API_PATHS = {
    f'{API_PREFIX}/auth/bootstrap',
    f'{API_PREFIX}/auth/login',
    f'{API_PREFIX}/auth/register',
    f'{API_PREFIX}/auth/oidc/login',
    f'{API_PREFIX}/auth/oidc/callback',
    f'{API_PREFIX}/auth/saml/login',
    f'{API_PREFIX}/auth/saml/metadata',
    f'{API_PREFIX}/auth/saml/acs',
    f'{API_PREFIX}/health',
    f'{API_PREFIX}/health/ready',
    f'{API_PREFIX}/capabilities',
    OPENAPI_PATH,
    DOCS_PATH,
    REDOC_PATH,
}
AUTH_RATE_LIMIT = RateLimitRule('auth', 5, 60)
UPLOAD_RATE_LIMIT = RateLimitRule('upload', 10, 60)
EXPORT_RATE_LIMIT = RateLimitRule('export', 5, 60)
GENERAL_RATE_LIMIT = RateLimitRule('general', 100, 60)


async def maybe_seed_demo_data() -> bool:
    if not settings.demo_mode:
        return False

    async with AsyncSessionLocal() as session:
        seeded = await seed_demo_data(session)
    if seeded:
        logger.info('Demo mode seed data loaded for a fresh install')
    else:
        logger.info('Demo mode seed skipped because family data already exists')
    return seeded


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = None
    backup_scheduler = None
    app.state.started_at = get_runtime_started_at(app)
    app.state.database_migrated = settings.testing
    app.state.services_initialized = settings.testing
    app.state.startup_health = None
    summary = validate_runtime_config()
    log_validated_config_summary(summary)
    capabilities = await get_capability_registry().check_all()
    optional_unavailable = [name for name, state in capabilities.items() if not state['enabled']]
    if optional_unavailable:
        logger.warning('Starting with reduced functionality: %s', ', '.join(optional_unavailable))
    if not settings.testing:
        ensure_auth_runtime_configured()
        await asyncio.to_thread(ensure_database_migrations)
        app.state.database_migrated = True
        await maybe_seed_demo_data()
        worker = create_worker()
        worker.start()
        backup_scheduler = get_backup_scheduler()
        backup_scheduler.start()
    app.state.services_initialized = True
    app.state.startup_health = await log_startup_health_snapshot(app)
    yield
    if worker is not None:
        worker.stop()
    if backup_scheduler is not None:
        backup_scheduler.stop()


def _is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(f'{API_PREFIX}/')


def _is_public_api_path(path: str) -> bool:
    if path in PUBLIC_API_PATHS:
        return True
    if path.startswith(f'{API_PREFIX}/portfolio/public/'):
        return True
    return path.startswith(f'{API_PREFIX}/invitations/') and path.endswith('/accept')


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _apply_security_headers(response: JSONResponse | FileResponse) -> None:
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "img-src 'self' data: blob:; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'"
    )
    if 'Server' in response.headers:
        del response.headers['Server']


def _append_vary_header(response: JSONResponse | FileResponse, value: str) -> None:
    existing = response.headers.get('Vary')
    if not existing:
        response.headers['Vary'] = value
        return
    values = {item.strip() for item in existing.split(',') if item.strip()}
    values.add(value)
    response.headers['Vary'] = ', '.join(sorted(values))


def _get_request_locale(request: Request) -> str:
    locale = getattr(request.state, 'locale', None)
    if isinstance(locale, str) and locale:
        return locale
    return parse_accept_language(request.headers.get('accept-language'))


def _apply_transport_headers(request: Request, response: JSONResponse | FileResponse) -> None:
    _apply_security_headers(response)
    locale = _get_request_locale(request)
    response.headers['Content-Language'] = locale
    response.headers['X-Response-Locale'] = locale
    response.headers['X-Date-Format-Hint'] = f"locale={locale}; dateStyle={DATE_FORMAT_HINT['date_style']}; timeStyle={DATE_FORMAT_HINT['time_style']}"
    _append_vary_header(response, 'Accept-Language')
    if settings.hsts_enabled and is_secure_request(request):
        value = [f'max-age={settings.hsts_max_age_seconds}']
        if settings.hsts_include_subdomains:
            value.append('includeSubDomains')
        if settings.hsts_preload:
            value.append('preload')
        response.headers['Strict-Transport-Security'] = '; '.join(value)


def _get_rate_limit(request: Request, session: dict[str, object] | None) -> tuple[RateLimitRule, str] | None:
    path = request.url.path
    if not _is_api_path(path) or path in {f'{API_PREFIX}/health', f'{API_PREFIX}/health/ready', f'{API_PREFIX}/capabilities'}:
        return None

    ip = get_request_ip(request)
    if path in {f'{API_PREFIX}/auth/login', f'{API_PREFIX}/auth/register'} or (
        path.startswith(f'{API_PREFIX}/invitations/') and path.endswith('/accept')
    ):
        return AUTH_RATE_LIMIT, f'ip:{ip}'

    user_id = session.get('user_id') if session else None
    principal = f'user:{user_id}' if isinstance(user_id, int) else f'ip:{ip}'

    method = request.method.upper()
    if method == 'POST' and path == f'{API_PREFIX}/submissions':
        return UPLOAD_RATE_LIMIT, principal
    if path.startswith(f'{API_PREFIX}/exports') and method in {'POST', 'DELETE'}:
        return EXPORT_RATE_LIMIT, principal
    return GENERAL_RATE_LIMIT, principal


def _maintenance_payload(*, message: str, source: str) -> dict[str, object]:
    return error_detail(
        code='maintenance_mode',
        message_key='errors.maintenance.active',
        default_message=message,
        details={
            'maintenance': {
                'active': True,
                'message': message,
                'source': source,
            }
        },
    )


def _https_redirect_url(request: Request) -> str:
    target = request.url.replace(scheme='https')
    return str(target)


def _should_redirect_to_https(request: Request) -> bool:
    if not settings.tls_enabled or not settings.https_redirect_enabled:
        return False
    if request.url.path in HEALTH_PATHS:
        return False
    return not is_secure_request(request)


def create_app() -> FastAPI:
    configure_logging(settings)
    app = FastAPI(
        title=settings.app_name,
        summary=API_SUMMARY,
        description=API_DESCRIPTION,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=OPENAPI_PATH,
    )
    app.state.started_at = datetime.now(UTC)
    app.state.database_migrated = settings.testing
    app.state.services_initialized = settings.testing
    app.state.startup_health = None
    app.state.rate_limiter = RateLimiter()
    install_monitoring(app)
    configure_openapi(
        app,
        api_prefix=API_PREFIX,
        session_cookie_name=settings.session_cookie_name,
        csrf_cookie_name=settings.csrf_cookie_name,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie='homeschool_oidc_state',
        same_site='lax',
        https_only=settings.session_cookie_secure,
    )

    if FRONTEND_DIST_DIR.exists():
        assets_dir = FRONTEND_DIST_DIR / 'assets'
        if assets_dir.exists():
            app.mount('/assets', StaticFiles(directory=assets_dir), name='frontend-assets')
    app.mount('/uploads', StaticFiles(directory=settings.upload_dir, check_dir=False), name='uploads')

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        response = JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(
                exc.detail,
                locale=_get_request_locale(request),
                requested_locale=request.headers.get('accept-language'),
                fallback_code='http_error',
                fallback_message='Request failed',
            ),
            headers=exc.headers,
        )
        _apply_transport_headers(request, response)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        response = JSONResponse(
            status_code=422,
            content=build_error_payload(
                error_detail(
                    code='validation_error',
                    message_key='errors.request.invalid',
                    default_message='Invalid request.',
                    details=_json_safe(exc.errors()),
                ),
                locale=_get_request_locale(request),
                requested_locale=request.headers.get('accept-language'),
            ),
        )
        _apply_transport_headers(request, response)
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log_action(
            logger,
            logging.ERROR,
            'Unhandled application error',
            action='unhandled_error',
            details={'path': request.url.path, 'method': request.method},
            exc_info=exc,
        )
        details = {'type': exc.__class__.__name__} if settings.testing else None
        response = JSONResponse(
            status_code=500,
            content=build_error_payload(
                error_detail(
                    code='internal_error',
                    message_key='errors.request.internal',
                    default_message='An unexpected error occurred.',
                    details=details,
                ),
                locale=_get_request_locale(request),
                requested_locale=request.headers.get('accept-language'),
            ),
        )
        _apply_transport_headers(request, response)
        return response

    @app.middleware('http')
    async def security_middleware(request: Request, call_next):
        path = request.url.path
        request.state.locale = parse_accept_language(request.headers.get('accept-language'))
        correlation_id = request.headers.get('x-correlation-id') or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        context_token = bind_context(correlation_id=correlation_id, action='http_request')
        started_at = perf_counter()
        is_public = _is_public_api_path(path)
        session = None
        try:
            if _should_redirect_to_https(request):
                response = RedirectResponse(url=_https_redirect_url(request), status_code=307)
                _apply_transport_headers(request, response)
                return response

            maintenance_status = None
            if _is_api_path(path) and path not in {f'{API_PREFIX}/health', f'{API_PREFIX}/health/ready', f'{API_PREFIX}/capabilities'}:
                async with AsyncSessionLocal() as db:
                    maintenance_status = await get_maintenance_status(db)
            if _is_api_path(path) and not is_public:
                token = request.cookies.get(settings.session_cookie_name)
                session = verify_session_token(token)
            maintenance_bypass_paths = {
                f'{API_PREFIX}/auth/login',
                f'{API_PREFIX}/auth/oidc/login',
                f'{API_PREFIX}/auth/oidc/callback',
                f'{API_PREFIX}/auth/saml/login',
                f'{API_PREFIX}/auth/saml/acs',
                f'{API_PREFIX}/auth/saml/metadata',
            }
            if (
                maintenance_status
                and maintenance_status.active
                and _is_api_path(path)
                and path not in {f'{API_PREFIX}/health', f'{API_PREFIX}/health/ready', f'{API_PREFIX}/capabilities', OPENAPI_PATH, DOCS_PATH, REDOC_PATH}
                and path not in maintenance_bypass_paths
            ):
                bypass_allowed = False
                async with AsyncSessionLocal() as db:
                    bypass_allowed = await session_can_bypass_maintenance(db, session)
                if not bypass_allowed:
                    response = JSONResponse(
                        status_code=503,
                        content=build_error_payload(
                            _maintenance_payload(message=maintenance_status.message, source=maintenance_status.source),
                            locale=_get_request_locale(request),
                            requested_locale=request.headers.get('accept-language'),
                        ),
                    )
                    _apply_transport_headers(request, response)
                    return response

            if _is_api_path(path) and not is_public:
                if not session:
                    response = JSONResponse(
                        status_code=401,
                        content=build_error_payload(
                            error_detail(
                                code='auth_required',
                                message_key='errors.auth.required',
                                default_message='Authentication required',
                            ),
                            locale=_get_request_locale(request),
                            requested_locale=request.headers.get('accept-language'),
                        ),
                    )
                    _apply_transport_headers(request, response)
                    return response
                if request.method.upper() not in SAFE_METHODS:
                    try:
                        require_csrf(request, session)
                    except HTTPException as exc:
                        response = JSONResponse(
                            status_code=exc.status_code,
                            content=build_error_payload(
                                exc.detail,
                                locale=_get_request_locale(request),
                                requested_locale=request.headers.get('accept-language'),
                                fallback_code='csrf_failed',
                                fallback_message='CSRF validation failed',
                            ),
                        )
                        _apply_transport_headers(request, response)
                        return response
                request.state.session = session

            if session:
                update_context(
                    correlation_id=correlation_id,
                    user_id=session['user_id'],
                    family_id=session['family_id'],
                    action='http_request',
                )

            rate_limit = _get_rate_limit(request, session)
            if rate_limit is not None:
                rule, key = rate_limit
                allowed, retry_after = await app.state.rate_limiter.check(rule, key)
                if not allowed:
                    response = JSONResponse(
                        status_code=429,
                        content=build_error_payload(
                            error_detail(
                                code='rate_limited',
                                message_key='errors.request.rate_limited',
                                default_message='Too many requests. Please try again later.',
                            ),
                            locale=_get_request_locale(request),
                            requested_locale=request.headers.get('accept-language'),
                        ),
                        headers={'Retry-After': str(retry_after)},
                    )
                    _apply_transport_headers(request, response)
                    return response

            response = await call_next(request)
            _apply_transport_headers(request, response)
            if session and response.status_code < 500 and session_needs_rotation(session):
                set_session_cookies(
                    response,
                    request,
                    user_id=session['user_id'],
                    family_id=session['family_id'],
                )
            return response
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            status_code = getattr(locals().get('response', None), 'status_code', 500)
            if 'response' in locals():
                response.headers['X-Correlation-ID'] = correlation_id
            if path not in HEALTH_PATHS:
                slow_request = duration_ms > 1000
                get_monitoring(app).observe_request(status_code=status_code, duration_ms=duration_ms, slow=slow_request)
                log_action(
                    logger,
                    logging.WARNING if slow_request else logging.INFO,
                    'Handled HTTP request',
                    action='http_request',
                    correlation_id=correlation_id,
                    user_id=session['user_id'] if session else None,
                    family_id=session['family_id'] if session else None,
                    details={
                        'method': request.method,
                        'path': path,
                        'status_code': status_code,
                        'duration_ms': duration_ms,
                    },
                )
            reset_context(context_token)

    @app.get('/health', include_in_schema=False)
    async def health_alias() -> JSONResponse:
        status_code, payload = await build_simple_health_payload(app)
        return JSONResponse(status_code=status_code, content=payload)

    @app.get(f'{API_PREFIX}/capabilities')
    async def api_capabilities() -> dict[str, object]:
        capabilities = await get_capability_registry().check_all()
        disabled = [name for name, state in capabilities.items() if not state['enabled']]
        return {
            'status': 'degraded' if disabled else 'ok',
            'capabilities': capabilities,
            'optional_unavailable': disabled,
            'auth': get_auth_providers(),
        }

    @app.get(f'{API_PREFIX}/metrics')
    async def api_metrics(request: Request, db=Depends(get_db)) -> JSONResponse:
        if not settings.enable_metrics_endpoint:
            raise HTTPException(status_code=404, detail='Metrics endpoint is disabled')
        return JSONResponse(status_code=200, content=await collect_metrics_payload(request.app, db))

    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(admin_router, prefix=API_PREFIX)
    app.include_router(invitations_router, prefix=API_PREFIX)
    app.include_router(notifications_router, prefix=API_PREFIX)
    app.include_router(portfolio_router, prefix=API_PREFIX)
    app.include_router(audit_router, prefix=API_PREFIX)
    app.include_router(curriculum_router, prefix=API_PREFIX)
    app.include_router(dashboard_router, prefix=API_PREFIX)
    app.include_router(backups_router, prefix=API_PREFIX)
    app.include_router(exports_router, prefix=API_PREFIX)
    app.include_router(family_settings_router, prefix=API_PREFIX)
    app.include_router(gradebook_router, prefix=API_PREFIX)
    app.include_router(students_router, prefix=API_PREFIX)
    app.include_router(subjects_router, prefix=API_PREFIX)
    app.include_router(calendar_router, prefix=API_PREFIX)
    app.include_router(attendance_router, prefix=API_PREFIX)
    app.include_router(compliance_router, prefix=API_PREFIX)
    app.include_router(compliance_reports_router, prefix=API_PREFIX)
    app.include_router(assignments_router, prefix=API_PREFIX)
    app.include_router(lesson_plans_router, prefix=API_PREFIX)
    app.include_router(submissions_router, prefix=API_PREFIX)
    app.include_router(grades_router, prefix=API_PREFIX)
    app.include_router(imports_router, prefix=API_PREFIX)
    app.include_router(quizzes_router, prefix=API_PREFIX)
    app.include_router(report_cards_router, prefix=API_PREFIX)
    app.include_router(restore_router, prefix=API_PREFIX)
    app.include_router(transcripts_router, prefix=API_PREFIX)
    app.include_router(schedule_router, prefix=API_PREFIX)
    app.include_router(grading_router, prefix=API_PREFIX)
    app.include_router(reviews_router, prefix=API_PREFIX)
    app.include_router(search_router, prefix=API_PREFIX)
    app.include_router(users_router, prefix=API_PREFIX)

    @app.get('/', include_in_schema=False)
    async def serve_index() -> FileResponse:
        if not FRONTEND_INDEX.exists():
            raise HTTPException(status_code=404, detail='Frontend build not found')
        return FileResponse(FRONTEND_INDEX)

    @app.get('/{full_path:path}', include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        if _is_api_path(f'/{full_path}'):
            raise HTTPException(status_code=404, detail='Not found')

        candidate = (FRONTEND_DIST_DIR / full_path).resolve()
        if FRONTEND_DIST_DIR.exists() and str(candidate).startswith(str(FRONTEND_DIST_DIR.resolve())) and candidate.is_file():
            return FileResponse(candidate)

        if not FRONTEND_INDEX.exists():
            raise HTTPException(status_code=404, detail='Frontend build not found')

        if Path(full_path).suffix:
            raise HTTPException(status_code=404, detail='Not found')
        return FileResponse(FRONTEND_INDEX)

    return app


app = create_app()
