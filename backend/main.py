import asyncio
import logging
import uuid
from time import perf_counter
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from backend.config import settings
from backend.database import engine, get_db
from backend.models import Base
from backend.rate_limit import RateLimitRule, RateLimiter
from backend.routers import (
    assignments_router,
    attendance_router,
    audit_router,
    auth_router,
    curriculum_router,
    dashboard_router,
    grades_router,
    invitations_router,
    lesson_plans_router,
    notifications_router,
    quizzes_router,
    schedule_router,
    search_router,
    students_router,
    subjects_router,
    submissions_router,
)
from backend.routers.calendar import router as calendar_router
from backend.routers.grading import router as grading_router
from backend.services.capabilities import get_auth_providers, get_capability_registry
from backend.services.grading_worker import create_worker
from backend.services.logging_config import bind_context, configure_logging, log_action, reset_context, update_context
from backend.services.monitoring import collect_metrics_payload, get_monitoring, install_monitoring
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
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
FRONTEND_INDEX = FRONTEND_DIST_DIR / 'index.html'
HEALTH_PATHS = {f'{API_PREFIX}/health', '/health'}
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
    f'{API_PREFIX}/capabilities',
}
AUTH_RATE_LIMIT = RateLimitRule('auth', 5, 60)
UPLOAD_RATE_LIMIT = RateLimitRule('upload', 10, 60)
EXPORT_RATE_LIMIT = RateLimitRule('export', 5, 60)
GENERAL_RATE_LIMIT = RateLimitRule('general', 100, 60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = None
    summary = validate_runtime_config()
    log_validated_config_summary(summary)
    capabilities = await get_capability_registry().check_all()
    optional_unavailable = [name for name, state in capabilities.items() if not state['enabled']]
    if optional_unavailable:
        logger.warning('Starting with reduced functionality: %s', ', '.join(optional_unavailable))
    if not settings.testing:
        ensure_auth_runtime_configured()
        await asyncio.to_thread(ensure_database_migrations)
        worker = create_worker()
        worker.start()
    yield
    if worker is not None:
        worker.stop()


def _is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(f'{API_PREFIX}/')


def _is_public_api_path(path: str) -> bool:
    if path in PUBLIC_API_PATHS:
        return True
    return path.startswith(f'{API_PREFIX}/invitations/') and path.endswith('/accept')


def _error_payload(code: str, message: str, *, details: object | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        'detail': message,
        'error': {
            'code': code,
            'message': message,
        },
    }
    if details is not None:
        payload['error']['details'] = details
    return payload


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


def _apply_transport_headers(request: Request, response: JSONResponse | FileResponse) -> None:
    _apply_security_headers(response)
    if is_secure_request(request):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'


def _get_rate_limit(request: Request, session: dict[str, object] | None) -> tuple[RateLimitRule, str] | None:
    path = request.url.path
    if not _is_api_path(path) or path in {f'{API_PREFIX}/health', f'{API_PREFIX}/capabilities'}:
        return None

    ip = get_request_ip(request)
    if path in {f'{API_PREFIX}/auth/login', f'{API_PREFIX}/auth/register'} or (
        path.startswith(f'{API_PREFIX}/invitations/') and path.endswith('/accept')
    ):
        return AUTH_RATE_LIMIT, f'ip:{ip}'

    user_id = session.get('user_id') if session else None
    principal = f'user:{user_id}' if isinstance(user_id, int) else f'ip:{ip}'

    if request.method.upper() == 'POST' and path == f'{API_PREFIX}/submissions':
        return UPLOAD_RATE_LIMIT, principal
    if '/export' in path:
        return EXPORT_RATE_LIMIT, principal
    return GENERAL_RATE_LIMIT, principal


async def _check_database_health() -> str:
    async with engine.connect() as connection:
        await connection.execute(text('SELECT 1'))
    return 'ok'


async def _build_health_payload() -> tuple[int, dict[str, object]]:
    capabilities = await get_capability_registry().check_all()
    required = {'config': 'ok', 'database': 'ok'}
    required_failures: dict[str, str] = {}

    try:
        await _check_database_health()
    except Exception as exc:
        required['database'] = 'failed'
        required_failures['database'] = str(exc)

    optional_unavailable = [name for name, state in capabilities.items() if not state['enabled']]
    if required_failures:
        status_code = 503
        overall_status = 'required_failure'
    elif optional_unavailable:
        status_code = 200
        overall_status = 'degraded'
    else:
        status_code = 200
        overall_status = 'ok'

    payload: dict[str, object] = {
        'status': overall_status,
        'required': required,
        'optional_unavailable': optional_unavailable,
        'capabilities': capabilities,
        'auth': get_auth_providers(),
    }
    if required_failures:
        payload['required_failures'] = required_failures
    return status_code, payload


def create_app() -> FastAPI:
    configure_logging(settings)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.rate_limiter = RateLimiter()
    install_monitoring(app)
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
        message = exc.detail if isinstance(exc.detail, str) else 'Request failed'
        response = JSONResponse(
            status_code=exc.status_code,
            content=_error_payload('http_error', message, details=None if isinstance(exc.detail, str) else exc.detail),
            headers=exc.headers,
        )
        _apply_transport_headers(request, response)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        response = JSONResponse(
            status_code=422,
            content=_error_payload('validation_error', 'Invalid request.', details=_json_safe(exc.errors())),
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
            content=_error_payload('internal_error', 'An unexpected error occurred.', details=details),
        )
        _apply_transport_headers(request, response)
        return response

    @app.middleware('http')
    async def security_middleware(request: Request, call_next):
        path = request.url.path
        correlation_id = request.headers.get('x-correlation-id') or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        context_token = bind_context(correlation_id=correlation_id, action='http_request')
        started_at = perf_counter()
        is_public = _is_public_api_path(path) or path.startswith('/docs') or path.startswith('/openapi')
        session = None
        try:
            if _is_api_path(path) and not is_public:
                token = request.cookies.get(settings.session_cookie_name)
                session = verify_session_token(token)
                if not session:
                    response = JSONResponse(
                        status_code=401,
                        content=_error_payload('auth_required', 'Authentication required'),
                    )
                    _apply_transport_headers(request, response)
                    return response
                if request.method.upper() not in SAFE_METHODS:
                    try:
                        require_csrf(request, session)
                    except HTTPException as exc:
                        response = JSONResponse(
                            status_code=exc.status_code,
                            content=_error_payload('csrf_failed', str(exc.detail)),
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
                        content=_error_payload('rate_limited', 'Too many requests. Please try again later.'),
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

    @app.get(f'{API_PREFIX}/health')
    async def api_health() -> JSONResponse:
        status_code, payload = await _build_health_payload()
        return JSONResponse(status_code=status_code, content=payload)

    @app.get('/health', include_in_schema=False)
    async def health_alias() -> JSONResponse:
        return await api_health()

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
    app.include_router(invitations_router, prefix=API_PREFIX)
    app.include_router(notifications_router, prefix=API_PREFIX)
    app.include_router(audit_router, prefix=API_PREFIX)
    app.include_router(curriculum_router, prefix=API_PREFIX)
    app.include_router(dashboard_router, prefix=API_PREFIX)
    app.include_router(students_router, prefix=API_PREFIX)
    app.include_router(subjects_router, prefix=API_PREFIX)
    app.include_router(calendar_router, prefix=API_PREFIX)
    app.include_router(attendance_router, prefix=API_PREFIX)
    app.include_router(assignments_router, prefix=API_PREFIX)
    app.include_router(lesson_plans_router, prefix=API_PREFIX)
    app.include_router(submissions_router, prefix=API_PREFIX)
    app.include_router(grades_router, prefix=API_PREFIX)
    app.include_router(quizzes_router, prefix=API_PREFIX)
    app.include_router(schedule_router, prefix=API_PREFIX)
    app.include_router(grading_router, prefix=API_PREFIX)
    app.include_router(search_router, prefix=API_PREFIX)

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
