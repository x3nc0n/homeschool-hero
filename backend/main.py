import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.config import settings
from backend.database import engine
from backend.models import Base
from backend.routers import (
    assignments_router,
    auth_router,
    grades_router,
    invitations_router,
    quizzes_router,
    students_router,
    subjects_router,
    submissions_router,
)
from backend.routers.grading import router as grading_router
from backend.security import verify_session_token
from backend.services.capabilities import get_capability_registry
from backend.services.grading_worker import create_worker
from backend.startup import (
    ensure_auth_runtime_configured,
    log_validated_config_summary,
    run_migrations,
    validate_runtime_config,
)

API_PREFIX = settings.api_prefix.rstrip('/')
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
FRONTEND_INDEX = FRONTEND_DIST_DIR / 'index.html'
logger = logging.getLogger(__name__)
PUBLIC_API_PATHS = {
    f'{API_PREFIX}/auth/bootstrap',
    f'{API_PREFIX}/auth/login',
    f'{API_PREFIX}/auth/register',
    f'{API_PREFIX}/health',
    f'{API_PREFIX}/capabilities',
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = None
    summary = validate_runtime_config()
    log_validated_config_summary(summary)
    capabilities = await get_capability_registry().check_all()
    optional_unavailable = [name for name, state in capabilities.items() if not state['enabled']]
    if optional_unavailable:
        logger.warning('Starting with reduced functionality: %s', ', '.join(optional_unavailable))
    if settings.testing:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        ensure_auth_runtime_configured()
        await asyncio.to_thread(run_migrations)
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
    }
    if required_failures:
        payload['required_failures'] = required_failures
    return status_code, payload


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    if FRONTEND_DIST_DIR.exists():
        assets_dir = FRONTEND_DIST_DIR / 'assets'
        if assets_dir.exists():
            app.mount('/assets', StaticFiles(directory=assets_dir), name='frontend-assets')
    app.mount('/uploads', StaticFiles(directory=settings.upload_dir, check_dir=False), name='uploads')

    @app.middleware('http')
    async def session_auth_middleware(request: Request, call_next):
        path = request.url.path
        is_public = _is_public_api_path(path) or path.startswith('/docs') or path.startswith('/openapi')
        if _is_api_path(path) and not is_public:
            token = request.cookies.get(settings.session_cookie_name)
            session = verify_session_token(token)
            if not session:
                return JSONResponse(status_code=401, content={'detail': 'Authentication required'})
            request.state.session = session
        return await call_next(request)

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
        }

    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(invitations_router, prefix=API_PREFIX)
    app.include_router(students_router, prefix=API_PREFIX)
    app.include_router(subjects_router, prefix=API_PREFIX)
    app.include_router(assignments_router, prefix=API_PREFIX)
    app.include_router(submissions_router, prefix=API_PREFIX)
    app.include_router(grades_router, prefix=API_PREFIX)
    app.include_router(quizzes_router, prefix=API_PREFIX)
    app.include_router(grading_router, prefix=API_PREFIX)

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
