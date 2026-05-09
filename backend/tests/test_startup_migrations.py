import logging

import pytest

from backend.config import settings
from backend.startup import MigrationStatus, StartupValidationError, ensure_database_migrations, validate_runtime_config


def test_startup_validation_reports_default_migration_mode(tmp_path) -> None:
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': True,
            'smtp_host': None,
            'smtp_from_email': None,
            'backup_target': None,
            'openai_api_key': None,
        }
    )

    summary = validate_runtime_config(config)

    assert summary['migration_mode'] == 'apply'


def test_startup_warn_mode_reports_pending_without_applying(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    status = MigrationStatus(
        mode='warn',
        database_revisions=('20260508_170455',),
        head_revisions=('20260508_223000',),
        pending_revisions=('20260508_223000',),
        ahead_revisions=(),
        elapsed_seconds=0.01,
    )
    monkeypatch.setattr('backend.startup.inspect_migration_status', lambda config=settings: status)
    monkeypatch.setattr('backend.startup._upgrade_database', lambda *args, **kwargs: pytest.fail('_upgrade_database should not run'))

    with caplog.at_level(logging.WARNING):
        returned = ensure_database_migrations()

    assert returned == status
    assert 'MIGRATION_MODE=warn leaves 20260508_223000 unapplied' in caplog.text


def test_startup_apply_mode_runs_pending_migrations(monkeypatch: pytest.MonkeyPatch) -> None:
    pending_status = MigrationStatus(
        mode='apply',
        database_revisions=('20260508_170455',),
        head_revisions=('20260508_223000',),
        pending_revisions=('20260508_223000',),
        ahead_revisions=(),
        elapsed_seconds=0.01,
    )
    clean_status = MigrationStatus(
        mode='apply',
        database_revisions=('20260508_223000',),
        head_revisions=('20260508_223000',),
        pending_revisions=(),
        ahead_revisions=(),
        elapsed_seconds=0.01,
    )
    calls: list[str] = []

    def fake_inspect(config=settings):
        return pending_status if not calls else clean_status

    def fake_run(config=settings, revision: str = 'head') -> None:
        calls.append(revision)

    monkeypatch.setattr('backend.startup.inspect_migration_status', fake_inspect)
    monkeypatch.setattr('backend.startup._upgrade_database', fake_run)

    returned = ensure_database_migrations()

    assert calls == ['head']
    assert returned == clean_status


def test_startup_blocks_when_migration_upgrade_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    status = MigrationStatus(
        mode='apply',
        database_revisions=('20260508_170455',),
        head_revisions=('20260508_223000',),
        pending_revisions=('20260508_223000',),
        ahead_revisions=(),
        elapsed_seconds=0.01,
    )
    monkeypatch.setattr('backend.startup.inspect_migration_status', lambda config=settings: status)

    def explode(*args, **kwargs) -> None:
        raise RuntimeError('upgrade boom')

    monkeypatch.setattr('backend.startup._upgrade_database', explode)

    with pytest.raises(StartupValidationError) as excinfo:
        ensure_database_migrations()

    assert 'Database migration failed while upgrading' in str(excinfo.value)
