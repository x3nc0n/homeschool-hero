from pathlib import Path

import pytest

from backend.config import settings
from backend.startup import StartupValidationError, validate_runtime_config


def test_startup_validation_fails_with_missing_required_config(tmp_path: Path) -> None:
    blocked_upload_path = tmp_path / 'blocked-upload-dir'
    blocked_upload_path.write_text('not a directory', encoding='utf-8')
    config = settings.model_copy(
        update={
            'database_url': '',
            'secret_key': '',
            'upload_dir': str(blocked_upload_path),
            'testing': True,
        }
    )

    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)

    message = str(excinfo.value)
    assert 'DATABASE_URL is required' in message
    assert 'SECRET_KEY is required' in message
    assert 'UPLOAD_DIR' in message


def test_startup_validation_succeeds_with_only_required_config(tmp_path: Path) -> None:
    upload_dir = tmp_path / 'uploads'
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(upload_dir),
            'testing': True,
            'smtp_host': None,
            'smtp_from_email': None,
            'backup_target': None,
            'openai_api_key': None,
        }
    )

    summary = validate_runtime_config(config)

    assert summary['database_driver'] == 'sqlite+aiosqlite'
    assert summary['upload_dir'] == str(upload_dir.resolve())
    assert summary['smtp_configured'] is False
    assert summary['backup_configured'] is False


def test_startup_validation_requires_oidc_settings(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': True,
            'auth_provider': 'oidc',
            'oidc_client_id': '',
            'oidc_client_secret': '',
            'oidc_discovery_url': '',
        }
    )

    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)

    assert 'OIDC auth requires these settings' in str(excinfo.value)


def test_startup_validation_requires_saml_settings(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': True,
            'auth_provider': 'saml',
            'saml_metadata_url': '',
            'saml_entity_id': '',
            'saml_acs_url': '',
        }
    )
    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)
        validate_runtime_config(config)
    assert 'SAML auth requires these settings' in str(excinfo.value)
    assert 'SAML auth requires these settings' in str(excinfo.value)
