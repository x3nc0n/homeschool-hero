from pathlib import Path

from backend.config import Settings
from backend.services.capabilities import CapabilityRegistry, get_auth_providers


def test_capability_detection_uses_mocked_service_checks(monkeypatch, tmp_path: Path) -> None:
    config = Settings().model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'ai_provider': 'ollama',
            'ollama_host': 'http://ollama.test:11434',
            'ollama_model': 'llama3.2',
            'smtp_host': 'smtp.test',
            'smtp_port': 2525,
            'smtp_from_email': 'robot@test.local',
            'backup_target': str(tmp_path / 'backup'),
            'testing': True,
        }
    )
    registry = CapabilityRegistry(config)

    monkeypatch.setattr(
        'backend.services.capabilities.check_ai_grading',
        lambda *_args, **_kwargs: {
            'name': 'ai_grading',
            'enabled': True,
            'configured': True,
            'status': 'enabled',
            'reason': 'AI reachable',
            'details': {'provider': 'ollama'},
            'checked_at': '2026-05-08T00:00:00+00:00',
        },
    )
    monkeypatch.setattr(
        'backend.services.capabilities.check_email',
        lambda *_args, **_kwargs: {
            'name': 'email',
            'enabled': False,
            'configured': True,
            'status': 'disabled',
            'reason': 'SMTP test failed',
            'details': {'host': 'smtp.test'},
            'checked_at': '2026-05-08T00:00:00+00:00',
        },
    )
    monkeypatch.setattr(
        'backend.services.capabilities.check_backup',
        lambda *_args, **_kwargs: {
            'name': 'backup',
            'enabled': True,
            'configured': True,
            'status': 'enabled',
            'reason': 'Backup target mounted',
            'details': {'target': str(tmp_path / 'backup')},
            'checked_at': '2026-05-08T00:00:00+00:00',
        },
    )
    monkeypatch.setattr(
        'backend.services.capabilities.check_ocr',
        lambda *_args, **_kwargs: {
            'name': 'ocr',
            'enabled': False,
            'configured': False,
            'status': 'disabled',
            'reason': 'Tesseract missing',
            'details': {},
            'checked_at': '2026-05-08T00:00:00+00:00',
        },
    )

    result = registry.check_all_sync()

    assert result['ai_grading']['enabled'] is True
    assert result['email']['enabled'] is False
    assert result['backup']['enabled'] is True
    assert result['ocr']['reason'] == 'Tesseract missing'


def test_auth_provider_capabilities_include_all_configured_providers(tmp_path: Path) -> None:
    config = Settings().model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'auth_provider': 'local',
            'auth_breakglass_local': True,
            'oidc_client_id': 'client-id',
            'oidc_client_secret': 'client-secret',
            'oidc_discovery_url': 'https://login.example/.well-known/openid-configuration',
            'saml_metadata_url': 'https://idp.example/metadata',
            'saml_entity_id': 'https://app.example/api/auth/saml/metadata',
            'saml_acs_url': 'https://app.example/api/auth/saml/acs',
            'testing': True,
        }
    )

    auth = get_auth_providers(config)

    assert auth['current_provider'] == 'local'
    assert auth['available_providers'] == ['local', 'oidc', 'saml']
    assert auth['local_enabled'] is True
    assert auth['oidc_enabled'] is True
    assert auth['saml_enabled'] is True


def test_auth_provider_capabilities_can_disable_breakglass_local(tmp_path: Path) -> None:
    config = Settings().model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'auth_provider': 'oidc',
            'auth_breakglass_local': False,
            'oidc_client_id': 'client-id',
            'oidc_client_secret': 'client-secret',
            'oidc_discovery_url': 'https://login.example/.well-known/openid-configuration',
            'testing': True,
        }
    )

    auth = get_auth_providers(config)

    assert auth['current_provider'] == 'oidc'
    assert auth['available_providers'] == ['oidc']
    assert auth['local_enabled'] is False
    assert auth['oidc_enabled'] is True
    assert auth['saml_enabled'] is False
