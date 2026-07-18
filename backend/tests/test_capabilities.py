from pathlib import Path

import pytest

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


def test_check_ai_grading_azure_openai_healthy_with_api_key(monkeypatch, tmp_path: Path) -> None:
    from backend.services import capabilities as capabilities_module

    config = Settings().model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'ai_provider': 'azure_openai',
            'azure_openai_endpoint': 'https://acct.openai.azure.com/',
            'azure_openai_deployment': 'gpt-4o',
            'azure_openai_api_key': 'secret-key-123',
            'testing': True,
        }
    )

    captured = {}

    class _FakeResponse:
        status_code = 200

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def post(self, url, *, headers=None, params=None, json=None):
            captured['url'] = url
            captured['headers'] = headers or {}
            captured['params'] = params or {}
            captured['json'] = json or {}
            return _FakeResponse()

    monkeypatch.setattr(capabilities_module.httpx, 'Client', _FakeClient)

    result = capabilities_module.check_ai_grading(config)

    assert result['enabled'] is True
    assert result['configured'] is True
    assert result['details']['provider'] == 'azure_openai'
    assert captured['url'] == 'https://acct.openai.azure.com/openai/deployments/gpt-4o/chat/completions'
    assert captured['headers'].get('api-key') == 'secret-key-123'
    assert captured['params'] == {'api-version': config.azure_openai_api_version}
    assert captured['json'].get('max_tokens') == 1


def _azure_grading_config(tmp_path: Path) -> Settings:
    return Settings().model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'ai_provider': 'azure_openai',
            'azure_openai_endpoint': 'https://acct.openai.azure.com/',
            'azure_openai_deployment': 'gpt-4o',
            'azure_openai_api_key': 'secret-key-123',
            'testing': True,
        }
    )


def _patch_azure_probe_status(monkeypatch, capabilities_module, status_code: int) -> None:
    class _FakeResponse:
        def __init__(self) -> None:
            self.status_code = status_code

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def post(self, url, *, headers=None, params=None, json=None):
            return _FakeResponse()

    monkeypatch.setattr(capabilities_module.httpx, 'Client', _FakeClient)


@pytest.mark.parametrize('status_code', [200, 400, 404, 429])
def test_check_ai_grading_azure_openai_reachable_under_least_privilege(monkeypatch, tmp_path: Path, status_code: int) -> None:
    from backend.services import capabilities as capabilities_module

    config = _azure_grading_config(tmp_path)
    _patch_azure_probe_status(monkeypatch, capabilities_module, status_code)

    result = capabilities_module.check_ai_grading(config)

    # A minimal inference probe: 200 or any non-auth model-layer 4xx means the deployment is reachable.
    assert result['enabled'] is True
    assert result['details']['status_code'] == status_code


@pytest.mark.parametrize('status_code', [401, 403, 500, 503])
def test_check_ai_grading_azure_openai_unavailable_on_auth_or_server_error(monkeypatch, tmp_path: Path, status_code: int) -> None:
    from backend.services import capabilities as capabilities_module

    config = _azure_grading_config(tmp_path)
    _patch_azure_probe_status(monkeypatch, capabilities_module, status_code)

    result = capabilities_module.check_ai_grading(config)

    assert result['enabled'] is False
    assert result['configured'] is True
    assert result['details']['status_code'] == status_code


def test_check_ai_grading_azure_openai_unconfigured(tmp_path: Path) -> None:
    from backend.services import capabilities as capabilities_module

    config = Settings().model_copy(
        update={
            'database_url': f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
            'secret_key': 'required-test-secret',
            'upload_dir': str(tmp_path / 'uploads'),
            'ai_provider': 'azure_openai',
            'testing': True,
        }
    )

    result = capabilities_module.check_ai_grading(config)

    assert result['enabled'] is False
    assert result['configured'] is False
    assert 'AZURE_OPENAI_ENDPOINT' in result['reason']
