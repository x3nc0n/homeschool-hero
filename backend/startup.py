from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from backend.config import Settings, settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_SECRETS = {'dev-secret-change-me', 'super-secret-change-me', 'changeme'}


class StartupValidationError(RuntimeError):
    """Raised when required runtime configuration is invalid."""


def _normalize_database_url(url: str) -> str:
    if url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    if url.startswith('sqlite:///'):
        return url.replace('sqlite:///', 'sqlite+aiosqlite:///', 1)
    return url


def _validate_database_url(config: Settings) -> dict[str, str]:
    raw_url = config.database_url.strip()
    if not raw_url:
        raise StartupValidationError('DATABASE_URL is required. Set DATABASE_URL to a valid SQLite or PostgreSQL URL.')

    try:
        parsed = make_url(_normalize_database_url(raw_url))
    except Exception as exc:  # pragma: no cover - SQLAlchemy error shapes vary
        raise StartupValidationError(
            f"DATABASE_URL is invalid: {exc}. Example: sqlite+aiosqlite:///./homeschool.db or "
            'postgresql+asyncpg://user:pass@host:5432/dbname'
        ) from exc

    if parsed.drivername not in {'sqlite', 'sqlite+aiosqlite', 'postgresql', 'postgresql+asyncpg'}:
        raise StartupValidationError(
            f"DATABASE_URL uses unsupported driver '{parsed.drivername}'. Use sqlite+aiosqlite or postgresql+asyncpg."
        )

    return {'driver': parsed.drivername, 'database': parsed.database or ''}


def _validate_secret_key(config: Settings) -> None:
    secret = config.secret_key.strip()
    if not secret:
        raise StartupValidationError('SECRET_KEY is required. Set SECRET_KEY to a long random value before startup.')
    if not config.testing and secret in _PLACEHOLDER_SECRETS:
        raise StartupValidationError(
            'SECRET_KEY is using a default placeholder. Replace it with a long random value before startup.'
        )


def _validate_upload_dir(config: Settings) -> str:
    upload_dir = Path(config.upload_dir)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        probe = upload_dir / f'.write-test-{uuid4().hex}'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
    except Exception as exc:
        raise StartupValidationError(
            f"UPLOAD_DIR '{upload_dir}' must be writable. Create the directory or fix permissions: {exc}"
        ) from exc
    return str(upload_dir.resolve())


def validate_runtime_config(config: Settings = settings) -> dict[str, object]:
    errors: list[str] = []
    database_summary: dict[str, str] = {}
    upload_dir = config.upload_dir

    try:
        database_summary = _validate_database_url(config)
    except StartupValidationError as exc:
        errors.append(str(exc))

    try:
        _validate_secret_key(config)
    except StartupValidationError as exc:
        errors.append(str(exc))

    try:
        upload_dir = _validate_upload_dir(config)
    except StartupValidationError as exc:
        errors.append(str(exc))

    if errors:
        raise StartupValidationError('Startup configuration validation failed:\n- ' + '\n- '.join(errors))

    return {
        'database_driver': database_summary.get('driver', 'unknown'),
        'database_name': database_summary.get('database', ''),
        'upload_dir': upload_dir,
        'ai_provider': config.ai_provider.strip().lower() or 'ollama',
        'smtp_configured': bool(config.smtp_host and config.smtp_from_email),
        'backup_configured': bool(config.backup_target),
        'testing': config.testing,
    }


def log_validated_config_summary(summary: dict[str, object]) -> None:
    logger.info(
        'Validated runtime config: database_driver=%s database_name=%s upload_dir=%s ai_provider=%s '
        'smtp_configured=%s backup_configured=%s testing=%s',
        summary.get('database_driver'),
        summary.get('database_name') or '(default)',
        summary.get('upload_dir'),
        summary.get('ai_provider'),
        summary.get('smtp_configured'),
        summary.get('backup_configured'),
        summary.get('testing'),
    )


def ensure_runtime_directories() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


def ensure_auth_runtime_configured() -> None:
    if not settings.secret_key.strip():
        raise RuntimeError('Set SECRET_KEY before starting Homeschool Hero.')


def run_migrations() -> None:
    alembic_ini = Path(__file__).resolve().with_name('alembic.ini')
    migrations_dir = Path(__file__).resolve().with_name('migrations')

    config = Config(str(alembic_ini))
    config.set_main_option('script_location', str(migrations_dir))
    config.set_main_option('sqlalchemy.url', settings.database_url)
    command.upgrade(config, 'head')


def bootstrap_application() -> None:
    summary = validate_runtime_config()
    log_validated_config_summary(summary)
    ensure_auth_runtime_configured()
    if not settings.testing:
        run_migrations()
