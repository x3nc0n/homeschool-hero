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
    assert 'SAML auth requires these settings' in str(excinfo.value)


def test_startup_validation_requires_scim_bearer_token_when_enabled(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': True,
            'scim_enabled': True,
            'scim_bearer_token': '',
        }
    )

    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)

    assert 'SCIM_BEARER_TOKEN is required when SCIM_ENABLED=true.' in str(excinfo.value)


def test_startup_validation_reports_scim_summary_when_enabled(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': True,
            'scim_enabled': True,
            'scim_bearer_token': 'test-scim-token',
            'smtp_host': None,
            'smtp_from_email': None,
            'backup_target': None,
            'openai_api_key': None,
        }
    )

    summary = validate_runtime_config(config)

    assert summary['scim_enabled'] is True



def test_startup_validation_requires_oidc_settings_when_secondary_provider_is_exposed(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': True,
            'auth_provider': 'local',
            'oidc_client_id': 'client-id',
            'oidc_client_secret': '',
            'oidc_discovery_url': '',
        }
    )

    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)

    assert 'OIDC auth requires these settings' in str(excinfo.value)



def test_startup_validation_succeeds_with_secondary_external_provider_configured(tmp_path: Path) -> None:
    upload_dir = tmp_path / 'uploads'
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(upload_dir),
            'testing': True,
            'auth_provider': 'local',
            'auth_breakglass_local': True,
            'oidc_client_id': 'client-id',
            'oidc_client_secret': 'client-secret',
            'oidc_discovery_url': 'https://login.example/.well-known/openid-configuration',
            'smtp_host': None,
            'smtp_from_email': None,
            'backup_target': None,
            'openai_api_key': None,
        }
    )

    summary = validate_runtime_config(config)

    assert summary['auth_provider'] == 'local'
    assert summary['upload_dir'] == str(upload_dir.resolve())


def test_startup_validation_requires_entra_tenant_id_for_entra_jwt(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': True,
            'jwt_enabled': True,
            'jwt_jwks_url': 'https://login.microsoftonline.com/common/discovery/v2.0/keys',
            'jwt_secret': '',
            'jwt_issuer': 'https://login.microsoftonline.com/b9735550-cbce-4703-9c6e-e0e51de71a0d/v2.0',
            'jwt_audience': 'api://homeschool-hero',
            'jwt_algorithm': 'RS256',
            'jwt_tenant_id': '',
        }
    )

    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)

    assert 'JWT auth requires JWT_TENANT_ID for Microsoft Entra ID bearer validation.' in str(excinfo.value)


def test_startup_validation_requires_entra_v2_issuer_match(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': True,
            'jwt_enabled': True,
            'jwt_jwks_url': 'https://login.microsoftonline.com/b9735550-cbce-4703-9c6e-e0e51de71a0d/discovery/v2.0/keys',
            'jwt_secret': '',
            'jwt_issuer': 'https://login.microsoftonline.com/common/v2.0',
            'jwt_audience': 'api://homeschool-hero',
            'jwt_algorithm': 'RS256',
            'jwt_tenant_id': 'b9735550-cbce-4703-9c6e-e0e51de71a0d',
        }
    )

    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)

    assert 'JWT_ISSUER must match the Entra v2.0 issuer for JWT_TENANT_ID.' in str(excinfo.value)


def test_startup_validation_rejects_default_credentials_outside_demo_mode(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': 'postgresql+asyncpg://homeschool@db:5432/homeschool_hero',
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': False,
            'demo_mode': False,
            'postgres_password': 'changeme',
            'legacy_family_password': 'changeme',
        }
    )

    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)

    message = str(excinfo.value)
    assert 'POSTGRES_PASSWORD is using the default value "changeme"' in message
    assert 'FAMILY_PASSWORD is using the default value "changeme"' in message


def test_startup_validation_accepts_strong_password_in_database_url(tmp_path: Path) -> None:
    # Regression for #404: prod supplies full credentials via DATABASE_URL and never
    # sets POSTGRES_PASSWORD, so it keeps its unused "changeme" default. Startup must
    # not crash-loop on that unused field when the live connection password is strong.
    config = settings.model_copy(
        update={
            'database_url': 'postgresql+asyncpg://homeschool:S7rong-Prod-Passw0rd-xyz@db:5432/homeschool_hero',
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': False,
            'demo_mode': False,
            'postgres_password': 'changeme',
            'legacy_family_password': 'a-real-family-password',
            'smtp_host': None,
            'smtp_from_email': None,
            'backup_target': None,
            'openai_api_key': None,
        }
    )

    summary = validate_runtime_config(config)

    assert summary['database_driver'] == 'postgresql+asyncpg'


def test_startup_validation_rejects_default_password_in_database_url(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': 'postgresql+asyncpg://homeschool:changeme@db:5432/homeschool_hero',
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': False,
            'demo_mode': False,
            'postgres_password': 'changeme',
            'legacy_family_password': 'a-real-family-password',
        }
    )

    with pytest.raises(StartupValidationError) as excinfo:
        validate_runtime_config(config)

    assert 'DATABASE_URL is using the default password "changeme"' in str(excinfo.value)


def test_startup_validation_allows_default_credentials_in_demo_mode(tmp_path: Path) -> None:
    config = settings.model_copy(
        update={
            'database_url': 'postgresql+asyncpg://homeschool:changeme@db:5432/homeschool_hero',
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'testing': False,
            'demo_mode': True,
            'postgres_password': 'changeme',
            'legacy_family_password': 'changeme',
            'smtp_host': None,
            'smtp_from_email': None,
            'backup_target': None,
            'openai_api_key': None,
        }
    )

    summary = validate_runtime_config(config)

    assert summary['database_driver'] == 'postgresql+asyncpg'
