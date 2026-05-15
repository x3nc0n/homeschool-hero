from __future__ import annotations

import pytest

from backend.config import settings
from backend.services.auth_oidc import OIDCConfigurationError
from backend.services.capabilities import get_auth_providers
from tests.contracts import AUTH


def _set_auth_settings(monkeypatch, **updates) -> None:
    defaults = {
        'auth_provider': 'local',
        'auth_breakglass_local': False,
        'oidc_client_id': None,
        'oidc_client_secret': None,
        'oidc_discovery_url': None,
        'saml_metadata_url': None,
        'saml_entity_id': None,
        'saml_acs_url': None,
        'testing': True,
    }
    defaults.update(updates)
    for key, value in defaults.items():
        monkeypatch.setattr(settings, key, value, raising=False)


def test_oidc_enabled_when_client_id_configured(monkeypatch) -> None:
    _set_auth_settings(monkeypatch, auth_provider='local', oidc_client_id='client-id')

    auth = get_auth_providers()

    assert auth['oidc_enabled'] is True


def test_oidc_disabled_when_no_client_id(monkeypatch) -> None:
    _set_auth_settings(monkeypatch, auth_provider='oidc', oidc_client_id=None)
    auth_without_client_id = get_auth_providers()

    _set_auth_settings(monkeypatch, auth_provider='local', oidc_client_id='')
    auth_with_empty_client_id = get_auth_providers()

    assert auth_without_client_id['oidc_enabled'] is False
    assert auth_with_empty_client_id['oidc_enabled'] is False


def test_multiple_providers_available(monkeypatch) -> None:
    _set_auth_settings(monkeypatch, auth_provider='local', oidc_client_id='client-id')

    auth = get_auth_providers()

    assert auth['available_providers'] == ['local', 'oidc']


def test_saml_enabled_when_configured(monkeypatch) -> None:
    _set_auth_settings(
        monkeypatch,
        auth_provider='local',
        saml_metadata_url='https://idp.example/metadata',
        saml_entity_id='https://app.example/api/auth/saml/metadata',
        saml_acs_url='https://app.example/api/auth/saml/acs',
    )

    auth = get_auth_providers()

    assert auth['saml_enabled'] is True


def test_all_providers_can_be_enabled(monkeypatch) -> None:
    _set_auth_settings(
        monkeypatch,
        auth_provider='local',
        oidc_client_id='client-id',
        saml_metadata_url='https://idp.example/metadata',
        saml_entity_id='https://app.example/api/auth/saml/metadata',
        saml_acs_url='https://app.example/api/auth/saml/acs',
    )

    auth = get_auth_providers()

    assert auth['oidc_enabled'] is True
    assert auth['saml_enabled'] is True
    assert auth['available_providers'] == ['local', 'oidc', 'saml']


def test_current_provider_reflects_auth_provider(monkeypatch) -> None:
    _set_auth_settings(monkeypatch, auth_provider='oidc')

    auth = get_auth_providers()

    assert auth['current_provider'] == 'oidc'


@pytest.mark.asyncio
async def test_local_login_works_when_auth_provider_oidc(authorized_client, secondary_client, monkeypatch):
    _set_auth_settings(monkeypatch, auth_provider='oidc', oidc_client_id='client-id')

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )

    assert login.status_code == 200, login.text
    assert login.json()['user']['auth_provider'] == 'local'


@pytest.mark.asyncio
async def test_local_login_still_works_when_breakglass_disabled(authorized_client, secondary_client, monkeypatch):
    _set_auth_settings(monkeypatch, auth_provider='oidc', oidc_client_id='client-id', auth_breakglass_local=False)

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )

    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_breakglass_login_logs_warning(authorized_client, secondary_client, monkeypatch, caplog):
    _set_auth_settings(monkeypatch, auth_provider='oidc', oidc_client_id='client-id', auth_breakglass_local=True)
    caplog.set_level('WARNING')

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )

    assert login.status_code == 200, login.text
    assert 'breakglass' in caplog.text.lower()


@pytest.mark.asyncio
async def test_breakglass_no_privilege_escalation(authorized_client, secondary_client, tertiary_client, monkeypatch):
    _set_auth_settings(monkeypatch, auth_provider='local')
    normal_login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )
    assert normal_login.status_code == 200, normal_login.text

    _set_auth_settings(monkeypatch, auth_provider='oidc', oidc_client_id='client-id')
    breakglass_login = await tertiary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )

    assert breakglass_login.status_code == 200, breakglass_login.text
    assert breakglass_login.json()['membership'] == normal_login.json()['membership']
    assert breakglass_login.json()['app_roles'] == normal_login.json()['app_roles']
    assert breakglass_login.json()['effective_capabilities'] == normal_login.json()['effective_capabilities']


@pytest.mark.asyncio
async def test_oidc_failure_redirects_with_error(async_client, monkeypatch):
    _set_auth_settings(monkeypatch, auth_provider='oidc', oidc_client_id='client-id')

    async def _fail_oidc_callback(_request):
        raise OIDCConfigurationError('idp-failure')

    monkeypatch.setattr('backend.routers.auth.complete_oidc_login', _fail_oidc_callback)

    response = await async_client.get(f"{AUTH['oidc_callback']}?code=test-code&state=test-state")

    assert response.status_code == 302
    assert response.headers['location'].startswith('/login?error=')
    assert 'idp-failure' in response.headers['location']
