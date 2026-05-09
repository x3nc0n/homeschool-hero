from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.config import Settings, settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_SECRETS = {'dev-secret-change-me', 'super-secret-change-me', 'changeme'}
_VALID_MIGRATION_MODES = {'apply', 'warn'}
_VALID_AUTH_PROVIDERS = {'local', 'oidc', 'saml'}
_VALID_AUTO_PROVISION_MODES = {'default_family', 'reject'}
_MIGRATION_FILENAME_RE = re.compile(r'^\d{8}_\d{6}_[a-z0-9_]+\.py$')


@dataclass(slots=True)
class MigrationStatus:
    mode: str
    database_revisions: tuple[str, ...]
    head_revisions: tuple[str, ...]
    pending_revisions: tuple[str, ...]
    ahead_revisions: tuple[str, ...]
    elapsed_seconds: float

    @property
    def has_pending(self) -> bool:
        return bool(self.pending_revisions)

    @property
    def database_ahead(self) -> bool:
        return bool(self.ahead_revisions)


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


def _validate_migration_mode(config: Settings) -> str:
    mode = str(getattr(config, 'migration_mode', os.getenv('MIGRATION_MODE', 'apply'))).strip().lower()
    if mode not in _VALID_MIGRATION_MODES:
        raise StartupValidationError(
            f"MIGRATION_MODE must be one of {sorted(_VALID_MIGRATION_MODES)}. "
            f"Received '{getattr(config, 'migration_mode', os.getenv('MIGRATION_MODE', 'apply'))}'."
        )
    return mode


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


def _validate_auth_config(config: Settings) -> dict[str, str]:
    provider = (config.auth_provider or 'local').strip().lower() or 'local'
    if provider not in _VALID_AUTH_PROVIDERS:
        raise StartupValidationError(
            f"AUTH_PROVIDER must be one of {', '.join(sorted(_VALID_AUTH_PROVIDERS))}; got '{config.auth_provider}'."
        )

    auto_provision_mode = (config.auth_auto_provision_mode or 'default_family').strip().lower() or 'default_family'
    if auto_provision_mode not in _VALID_AUTO_PROVISION_MODES:
        raise StartupValidationError('AUTH_AUTO_PROVISION_MODE must be one of default_family or reject.')

    if provider == 'oidc':
        missing = [
            name
            for name, value in {
                'OIDC_CLIENT_ID': config.oidc_client_id,
                'OIDC_CLIENT_SECRET': config.oidc_client_secret,
                'OIDC_DISCOVERY_URL': config.oidc_discovery_url,
            }.items()
            if not (value or '').strip()
        ]
        if missing:
            raise StartupValidationError('OIDC auth requires these settings: ' + ', '.join(missing))

    if provider == 'saml':
        missing = [
            name
            for name, value in {
                'SAML_METADATA_URL': config.saml_metadata_url,
                'SAML_ENTITY_ID': config.saml_entity_id,
                'SAML_ACS_URL': config.saml_acs_url,
            }.items()
            if not (value or '').strip()
        ]
        if missing:
            raise StartupValidationError('SAML auth requires these settings: ' + ', '.join(missing))

    if auto_provision_mode == 'default_family' and not (config.auth_default_family_name or '').strip():
        raise StartupValidationError(
            'AUTH_DEFAULT_FAMILY_NAME is required when AUTH_AUTO_PROVISION_MODE=default_family.'
        )

    return {'auth_provider': provider, 'auth_auto_provision_mode': auto_provision_mode}


def validate_runtime_config(config: Settings = settings) -> dict[str, object]:
    errors: list[str] = []
    database_summary: dict[str, str] = {}
    auth_summary: dict[str, str] = {}
    backup_summary: dict[str, object] = {}
    upload_dir = config.upload_dir
    migration_mode = str(getattr(config, 'migration_mode', os.getenv('MIGRATION_MODE', 'apply')))

    try:
        database_summary = _validate_database_url(config)
    except StartupValidationError as exc:
        errors.append(str(exc))

    try:
        _validate_secret_key(config)
    except StartupValidationError as exc:
        errors.append(str(exc))

    try:
        migration_mode = _validate_migration_mode(config)
    except StartupValidationError as exc:
        errors.append(str(exc))

    try:
        upload_dir = _validate_upload_dir(config)
    except StartupValidationError as exc:
        errors.append(str(exc))

    try:
        auth_summary = _validate_auth_config(config)
    except StartupValidationError as exc:
        errors.append(str(exc))

    if config.backup_target:
        try:
            from backend.services.backup_service import get_backup_configuration, validate_backup_configuration

            validate_backup_configuration(config)
            backup_summary = get_backup_configuration(config)
        except Exception as exc:  # pragma: no cover - backup validation delegates rich errors
            errors.append(f'Backup configuration is invalid: {exc}')

    if errors:
        raise StartupValidationError('Startup configuration validation failed:\n- ' + '\n- '.join(errors))

    return {
        'database_driver': database_summary.get('driver', 'unknown'),
        'database_name': database_summary.get('database', ''),
        'upload_dir': upload_dir,
        'ai_provider': config.ai_provider.strip().lower() or 'ollama',
        'auth_provider': auth_summary.get('auth_provider', 'local'),
        'auth_auto_provision_mode': auth_summary.get('auth_auto_provision_mode', 'default_family'),
        'smtp_configured': bool(config.smtp_host and config.smtp_from_email),
        'backup_configured': bool(config.backup_target),
        'backup_destination': str(getattr(backup_summary.get('destination'), 'value', backup_summary.get('destination') or 'local')),
        'migration_mode': migration_mode,
        'testing': config.testing,
    }


def log_validated_config_summary(summary: dict[str, object]) -> None:
    logger.info(
        'Validated runtime config: database_driver=%s database_name=%s upload_dir=%s ai_provider=%s '
        'auth_provider=%s auth_auto_provision_mode=%s smtp_configured=%s backup_configured=%s backup_destination=%s '
        'migration_mode=%s testing=%s',
        summary.get('database_driver'),
        summary.get('database_name') or '(default)',
        summary.get('upload_dir'),
        summary.get('ai_provider'),
        summary.get('auth_provider'),
        summary.get('auth_auto_provision_mode'),
        summary.get('smtp_configured'),
        summary.get('backup_configured'),
        summary.get('backup_destination'),
        summary.get('migration_mode'),
        summary.get('testing'),
    )


def ensure_runtime_directories() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


def ensure_auth_runtime_configured() -> None:
    if not settings.secret_key.strip():
        raise RuntimeError('Set SECRET_KEY before starting Homeschool Hero.')


def build_alembic_config(config: Settings = settings) -> Config:
    alembic_ini = Path(__file__).resolve().with_name('alembic.ini')
    migrations_dir = Path(__file__).resolve().with_name('migrations')

    alembic_config = Config(str(alembic_ini))
    alembic_config.set_main_option('script_location', str(migrations_dir))
    alembic_config.set_main_option('sqlalchemy.url', config.database_url)
    return alembic_config


def _format_revisions(revisions: tuple[str, ...], *, empty_label: str = '(base)') -> str:
    return ', '.join(revisions) if revisions else empty_label


async def _fetch_database_revisions(database_url: str) -> tuple[str, ...]:
    engine_kwargs: dict[str, object] = {'pool_pre_ping': True}
    normalized_url = _normalize_database_url(database_url)
    if normalized_url.startswith('postgresql+asyncpg://'):
        engine_kwargs['poolclass'] = NullPool
    engine = create_async_engine(normalized_url, **engine_kwargs)

    async def _read_revisions() -> tuple[str, ...]:
        async with engine.connect() as connection:
            await connection.execute(text('SELECT 1'))

            def _load_current_revision(sync_connection) -> tuple[str, ...]:
                inspector = inspect(sync_connection)
                if 'alembic_version' not in inspector.get_table_names():
                    return ()
                rows = sync_connection.execute(text('SELECT version_num FROM alembic_version ORDER BY version_num')).fetchall()
                return tuple(str(row[0]) for row in rows)

            return await connection.run_sync(_load_current_revision)

    try:
        return await _read_revisions()
    finally:
        await engine.dispose()


def inspect_migration_status(config: Settings = settings) -> MigrationStatus:
    mode = _validate_migration_mode(config)
    start = perf_counter()
    alembic_config = build_alembic_config(config)
    script_directory = ScriptDirectory.from_config(alembic_config)
    ordered_revisions = list(reversed(list(script_directory.walk_revisions())))
    revision_ids = [revision.revision for revision in ordered_revisions]
    head_revisions = tuple(script_directory.get_heads())
    database_revisions = asyncio.run(_fetch_database_revisions(config.database_url))
    known_revision_ids = set(revision_ids)
    ahead_revisions = tuple(revision for revision in database_revisions if revision not in known_revision_ids)

    pending_revisions: tuple[str, ...] = ()
    if revision_ids:
        if not database_revisions:
            pending_revisions = tuple(revision_ids)
        elif not ahead_revisions:
            applied_indexes = [revision_ids.index(revision) for revision in database_revisions if revision in known_revision_ids]
            if applied_indexes:
                pending_revisions = tuple(revision_ids[max(applied_indexes) + 1 :])

    elapsed_seconds = perf_counter() - start
    status = MigrationStatus(
        mode=mode,
        database_revisions=database_revisions,
        head_revisions=head_revisions,
        pending_revisions=pending_revisions,
        ahead_revisions=ahead_revisions,
        elapsed_seconds=elapsed_seconds,
    )
    logger.info(
        'Migration preflight complete in %.3fs: mode=%s current=%s head=%s pending=%s ahead=%s',
        status.elapsed_seconds,
        status.mode,
        _format_revisions(status.database_revisions),
        _format_revisions(status.head_revisions),
        _format_revisions(status.pending_revisions, empty_label='none'),
        _format_revisions(status.ahead_revisions, empty_label='none'),
    )
    if status.has_pending:
        logger.warning('Detected unapplied migrations: %s', _format_revisions(status.pending_revisions, empty_label='none'))
    if status.database_ahead:
        logger.warning(
            'Database revision is ahead of this code checkout: %s. Downgrade or deploy matching code before writing data.',
            _format_revisions(status.ahead_revisions, empty_label='none'),
        )
    return status


def _upgrade_database(config: Settings = settings, revision: str = 'head') -> None:
    alembic_config = build_alembic_config(config)
    start = perf_counter()
    logger.info('Applying database migrations to %s', revision)
    command.upgrade(alembic_config, revision)
    logger.info('Database migrations reached %s in %.3fs', revision, perf_counter() - start)


def run_migrations(config: Settings = settings, revision: str | None = None) -> None:
    if revision is None:
        ensure_database_migrations(config)
        return
    _upgrade_database(config, revision)


def downgrade_database(config: Settings = settings, revision: str = '-1') -> None:
    alembic_config = build_alembic_config(config)
    start = perf_counter()
    logger.info('Downgrading database to %s', revision)
    command.downgrade(alembic_config, revision)
    logger.info('Database downgrade reached %s in %.3fs', revision, perf_counter() - start)


def ensure_database_migrations(config: Settings = settings) -> MigrationStatus:
    try:
        status = inspect_migration_status(config)
    except Exception as exc:  # pragma: no cover - exact DB/connectivity exception varies
        raise StartupValidationError(f'Database migration preflight failed: {exc}') from exc

    if status.has_pending and status.mode == 'warn':
        logger.warning(
            'MIGRATION_MODE=warn leaves %s unapplied. Startup will continue without changing schema.',
            _format_revisions(status.pending_revisions, empty_label='none'),
        )
        return status

    if not status.has_pending:
        return status

    try:
        _upgrade_database(config, 'head')
    except Exception as exc:  # pragma: no cover - Alembic exception types vary
        raise StartupValidationError(
            f"Database migration failed while upgrading from {_format_revisions(status.database_revisions)} "
            f'to {_format_revisions(status.head_revisions)}: {exc}'
        ) from exc

    final_status = inspect_migration_status(config)
    if final_status.has_pending:
        raise StartupValidationError(
            f"Database still has unapplied migrations after upgrade: "
            f"{_format_revisions(final_status.pending_revisions, empty_label='none')}"
        )
    return final_status


def create_migration_revision(message: str, *, autogenerate: bool = False, config: Settings = settings) -> None:
    alembic_config = build_alembic_config(config)
    command.revision(alembic_config, message=message, autogenerate=autogenerate)


def lint_migration_scripts(config: Settings = settings, versions_dir: Path | None = None) -> list[str]:
    versions_dir = versions_dir or (Path(__file__).resolve().with_name('migrations') / 'versions')
    errors: list[str] = []
    for path in sorted(versions_dir.glob('*.py')):
        if path.name == '__init__.py':
            continue
        contents = path.read_text(encoding='utf-8')
        is_merge_revision = bool(
            re.search(r'down_revision\s*:\s*.*=\s*\([^)]*,[^)]*\)', contents, re.MULTILINE | re.DOTALL)
        )
        if not _MIGRATION_FILENAME_RE.match(path.name):
            errors.append(f'{path.name}: filename must follow YYYYMMDD_HHMMSS_slug.py')
        if 'ROLLBACK_NOTES' not in contents:
            errors.append(f'{path.name}: missing ROLLBACK_NOTES block')
        elif 'TODO:' in contents.partition('ROLLBACK_NOTES')[2]:
            errors.append(f'{path.name}: replace the ROLLBACK_NOTES TODO template before merge')
        if 'def downgrade()' not in contents:
            errors.append(f'{path.name}: missing downgrade() function')
        elif (
            'def downgrade() -> None:\n    pass' in contents or "def downgrade() -> None:\r\n    pass" in contents
        ) and not is_merge_revision:
            errors.append(f'{path.name}: downgrade() cannot be a no-op pass')
    return errors


def verify_migration_cycle(config: Settings = settings) -> None:
    lint_errors = lint_migration_scripts(config)
    if lint_errors:
        raise StartupValidationError('Migration lint failed:\n- ' + '\n- '.join(lint_errors))
    _upgrade_database(config, 'head')
    downgrade_database(config, '-1')
    _upgrade_database(config, 'head')


def bootstrap_application() -> None:
    summary = validate_runtime_config()
    log_validated_config_summary(summary)
    ensure_auth_runtime_configured()
    if not settings.testing:
        ensure_database_migrations()
