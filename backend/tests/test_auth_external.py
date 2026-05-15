from __future__ import annotations

import logging

import pytest
from fastapi.responses import RedirectResponse

from backend.config import settings
from backend.services.auth_oidc import extract_identity as extract_oidc_identity
from backend.services.auth_oidc import _ensure_oidc_enabled
from backend.services.auth_saml import extract_identity as extract_saml_identity
from backend.services.auth_saml import _ensure_saml_enabled
from tests.contracts import AUTH, BACKUPS, INVITATIONS, bootstrap_payload


def _set_auth_settings(monkeypatch, **updates) -> None:
    defaults = {
        'auth_provider': 'local',
        'auth_breakglass_local': True,
        'oidc_client_id': None,
        'oidc_client_secret': None,
        'oidc_discovery_url': None,
        'oidc_roles_claim': 'roles',
        'oidc_groups_claim': 'groups',
        'oidc_group_role_map': '',
        'saml_metadata_url': None,
        'saml_entity_id': None,
        'saml_acs_url': None,
        'saml_role_attribute': 'http://schemas.microsoft.com/ws/2008/06/identity/claims/role',
        'auth_auto_provision_mode': 'default_family',
        'auth_default_family_name': 'SSO Test Family',
        'role_mapping_admin_raw': 'Admin',
        'role_mapping_teacher_raw': 'Teacher',
        'role_mapping_student_raw': 'Student',
    }
    defaults.update(updates)
    for key, value in defaults.items():
        monkeypatch.setattr(settings, key, value, raising=False)


class _FakeOIDCApp:
    def __init__(self, claims: dict[str, str]) -> None:
        self._claims = claims

    async def authorize_redirect(self, _request, redirect_uri: str):
        return RedirectResponse(url=f'https://idp.example/authorize?redirect_uri={redirect_uri}', status_code=302)

    async def authorize_access_token(self, _request):
        return {'userinfo': self._claims}

    async def parse_id_token(self, _request, _token):
        return self._claims


class _FakeOAuth:
    def __init__(self, claims: dict[str, str]) -> None:
        self.oidc = _FakeOIDCApp(claims)


class _FailingOIDCApp:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def authorize_access_token(self, _request):
        raise self._exc


class _FailingOAuth:
    def __init__(self, exc: Exception) -> None:
        self.oidc = _FailingOIDCApp(exc)


class _FakeSamlAuth:
    def __init__(self, *, attributes: dict[str, list[str]], name_id: str, authenticated: bool = True) -> None:
        self._attributes = attributes
        self._name_id = name_id
        self._authenticated = authenticated

    def login(self) -> str:
        return 'https://sso.example/login'

    def process_response(self) -> None:
        return None

    def get_errors(self) -> list[str]:
        return []

    def get_last_error_reason(self) -> str | None:
        return None

    def is_authenticated(self) -> bool:
        return self._authenticated

    def get_attributes(self) -> dict[str, list[str]]:
        return self._attributes

    def get_nameid(self) -> str:
        return self._name_id


def test_oidc_extract_identity_maps_roles_claim_and_warns_for_unmapped(caplog, monkeypatch):
    _set_auth_settings(monkeypatch)
    caplog.set_level(logging.WARNING)

    identity = extract_oidc_identity(
        {
            'sub': 'oidc-user',
            'email': 'oidc@example.com',
            'name': 'OIDC User',
            'roles': ['Teacher', 'Unknown Role', 'Admin'],
        }
    )

    assert identity.roles == ('admin', 'teacher')
    assert 'Unknown Role' in caplog.text


def test_oidc_extract_identity_falls_back_to_groups_claim(monkeypatch):
    _set_auth_settings(
        monkeypatch,
        oidc_group_role_map='{"group-admin": "Admin", "group-student": "Student"}',
    )

    identity = extract_oidc_identity(
        {
            'sub': 'oidc-user',
            'email': 'oidc@example.com',
            'name': 'OIDC User',
            'groups': ['group-student', 'ignored-group'],
        }
    )

    assert identity.roles == ('student',)


def test_oidc_extract_identity_ignores_groups_fallback_when_overage_is_signaled(caplog, monkeypatch):
    _set_auth_settings(
        monkeypatch,
        oidc_group_role_map='{"group-admin": "Admin"}',
    )
    caplog.set_level(logging.WARNING)

    identity = extract_oidc_identity(
        {
            'sub': 'oidc-user',
            'email': 'oidc@example.com',
            'name': 'OIDC User',
            '_claim_names': {'groups': 'src1'},
            '_claim_sources': {'src1': {'endpoint': 'https://graph.example/groups'}},
        }
    )

    assert identity.roles == ()
    assert 'groups overage' in caplog.text


def test_saml_extract_identity_collects_and_maps_role_attributes(caplog, monkeypatch):
    _set_auth_settings(monkeypatch)
    caplog.set_level(logging.WARNING)

    identity = extract_saml_identity(
        _FakeSamlAuth(
            attributes={
                'email': ['saml@example.com'],
                'displayName': ['SAML User'],
                'http://schemas.microsoft.com/ws/2008/06/identity/claims/role': ['Teacher', 'Unknown Role'],
                'Role': ['Admin'],
                'role': ['Student'],
            },
            name_id='saml-subject',
        )
    )

    assert identity.roles == ('admin', 'teacher', 'student')
    assert 'Unknown Role' in caplog.text


@pytest.mark.asyncio
async def test_local_auth_still_works_when_provider_is_local(async_client, monkeypatch):
    _set_auth_settings(monkeypatch, auth_provider='local')

    registered = await async_client.post(AUTH['register'], json=bootstrap_payload())
    assert registered.status_code == 201, registered.text

    await async_client.post(AUTH['logout'])
    login = await async_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )

    assert login.status_code == 200, login.text
    assert login.json()['user']['auth_provider'] == 'local'


@pytest.mark.asyncio
async def test_local_login_remains_available_when_provider_is_oidc(async_client, monkeypatch):
    _set_auth_settings(monkeypatch, auth_provider='local')

    registered = await async_client.post(AUTH['register'], json=bootstrap_payload())
    assert registered.status_code == 201, registered.text

    await async_client.post(AUTH['logout'])
    _set_auth_settings(monkeypatch, auth_provider='oidc')

    login = await async_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )

    assert login.status_code == 200, login.text
    assert login.json()['user']['auth_provider'] == 'local'


@pytest.mark.asyncio
async def test_breakglass_local_login_logs_warning_when_sso_provider_enabled(async_client, monkeypatch, caplog):
    _set_auth_settings(monkeypatch, auth_provider='local')

    registered = await async_client.post(AUTH['register'], json=bootstrap_payload())
    assert registered.status_code == 201, registered.text

    await async_client.post(AUTH['logout'])
    _set_auth_settings(monkeypatch, auth_provider='saml', auth_breakglass_local=True)
    caplog.set_level(logging.WARNING)

    login = await async_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )

    assert login.status_code == 200, login.text
    assert 'Breakglass local login used while AUTH_PROVIDER=saml' in caplog.text


def test_oidc_enablement_does_not_require_oidc_to_be_primary(monkeypatch):
    _set_auth_settings(
        monkeypatch,
        auth_provider='local',
        oidc_client_id='client-id',
        oidc_client_secret='client-secret',
        oidc_discovery_url='https://idp.example/.well-known/openid-configuration',
    )
    monkeypatch.setattr('backend.services.auth_oidc.AUTHLIB_AVAILABLE', True)

    _ensure_oidc_enabled()



def test_saml_enablement_does_not_require_saml_to_be_primary(monkeypatch):
    _set_auth_settings(
        monkeypatch,
        auth_provider='local',
        saml_metadata_url='https://idp.example/metadata',
        saml_entity_id='https://app.example/api/auth/saml/metadata',
        saml_acs_url='https://app.example/api/auth/saml/acs',
    )
    monkeypatch.setattr('backend.services.auth_saml.SAML_TOOLKIT_AVAILABLE', True)

    _ensure_saml_enabled()



@pytest.mark.asyncio
async def test_oidc_login_redirects_to_identity_provider(async_client, monkeypatch):
    _set_auth_settings(
        monkeypatch,
        auth_provider='oidc',
        oidc_client_id='client-id',
        oidc_client_secret='client-secret',
        oidc_discovery_url='https://idp.example/.well-known/openid-configuration',
    )
    monkeypatch.setattr(
        'backend.services.auth_oidc.create_oauth_client',
        lambda: _FakeOAuth({'sub': 'oidc-user', 'email': 'oidc@example.com', 'name': 'OIDC User'}),
    )
    monkeypatch.setattr('backend.services.auth_oidc._ensure_oidc_enabled', lambda: None)

    response = await async_client.get(AUTH['oidc_login'])

    assert response.status_code == 302
    assert response.headers['location'].startswith('https://idp.example/authorize')


@pytest.mark.asyncio
async def test_oidc_callback_redirects_to_login_when_token_exchange_fails(async_client, monkeypatch):
    _set_auth_settings(
        monkeypatch,
        auth_provider='oidc',
        oidc_client_id='client-id',
        oidc_client_secret='client-secret',
        oidc_discovery_url='https://idp.example/.well-known/openid-configuration',
    )
    monkeypatch.setattr(
        'backend.services.auth_oidc.create_oauth_client',
        lambda: _FailingOAuth(RuntimeError('token endpoint unavailable')),
    )
    monkeypatch.setattr('backend.services.auth_oidc._ensure_oidc_enabled', lambda: None)

    response = await async_client.get(f"{AUTH['oidc_callback']}?code=test-code&state=test-state")

    assert response.status_code == 302
    assert response.headers['location'].startswith('/login?error=OIDC%20sign-in%20failed')


@pytest.mark.asyncio
async def test_oidc_callback_matches_existing_user(async_client, monkeypatch, create_family_user):
    await create_family_user(
        family_name='OIDC Family',
        email='existing@example.com',
        password='strongpass456',
        display_name='Existing User',
    )
    _set_auth_settings(
        monkeypatch,
        auth_provider='oidc',
        oidc_client_id='client-id',
        oidc_client_secret='client-secret',
        oidc_discovery_url='https://idp.example/.well-known/openid-configuration',
    )
    monkeypatch.setattr(
        'backend.services.auth_oidc.create_oauth_client',
        lambda: _FakeOAuth({'sub': 'external-123', 'email': 'existing@example.com', 'name': 'Existing User'}),
    )
    monkeypatch.setattr('backend.services.auth_oidc._ensure_oidc_enabled', lambda: None)

    response = await async_client.get(f"{AUTH['oidc_callback']}?code=test-code&state=test-state")

    assert response.status_code == 302
    assert response.headers['location'] == '/'

    session = await async_client.get(AUTH['me'])
    assert session.status_code == 200, session.text
    assert session.json()['user']['email'] == 'existing@example.com'
    assert session.json()['user']['auth_provider'] == 'oidc'


@pytest.mark.asyncio
async def test_oidc_callback_auto_accepts_invitation(authorized_client, secondary_client, monkeypatch):
    _set_auth_settings(
        monkeypatch,
        auth_provider='oidc',
        oidc_client_id='client-id',
        oidc_client_secret='client-secret',
        oidc_discovery_url='https://idp.example/.well-known/openid-configuration',
    )
    create_invitation = await authorized_client.post(
        INVITATIONS['collection'],
        json={'email': 'invitee@example.com', 'role': 'co-parent'},
    )
    assert create_invitation.status_code == 201, create_invitation.text
    monkeypatch.setattr(
        'backend.services.auth_oidc.create_oauth_client',
        lambda: _FakeOAuth({'sub': 'invitee-oidc', 'email': 'invitee@example.com', 'name': 'Invited User'}),
    )
    monkeypatch.setattr('backend.services.auth_oidc._ensure_oidc_enabled', lambda: None)

    response = await secondary_client.get(f"{AUTH['oidc_callback']}?code=test-code&state=test-state")

    assert response.status_code == 302
    session = await secondary_client.get(AUTH['me'])
    assert session.status_code == 200, session.text
    assert session.json()['membership']['role'] == 'co-parent'


@pytest.mark.asyncio
async def test_oidc_callback_respects_reject_mode(async_client, monkeypatch):
    _set_auth_settings(
        monkeypatch,
        auth_provider='oidc',
        oidc_client_id='client-id',
        oidc_client_secret='client-secret',
        oidc_discovery_url='https://idp.example/.well-known/openid-configuration',
        auth_auto_provision_mode='reject',
    )
    monkeypatch.setattr(
        'backend.services.auth_oidc.create_oauth_client',
        lambda: _FakeOAuth({'sub': 'new-user', 'email': 'blocked@example.com', 'name': 'Blocked User'}),
    )
    monkeypatch.setattr('backend.services.auth_oidc._ensure_oidc_enabled', lambda: None)

    response = await async_client.get(f"{AUTH['oidc_callback']}?code=test-code&state=test-state")

    assert response.status_code == 302
    assert response.headers['location'].startswith('/login?error=')

    me = await async_client.get(AUTH['me'])
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_oidc_callback_persists_normalized_app_roles_in_session(async_client, monkeypatch, create_family_user):
    user = await create_family_user(
        family_name='OIDC Tutor Family',
        email='platform-admin@example.com',
        password='strongpass789',
        display_name='Platform Admin',
        role='tutor',
    )
    _set_auth_settings(
        monkeypatch,
        auth_provider='oidc',
        oidc_client_id='client-id',
        oidc_client_secret='client-secret',
        oidc_discovery_url='https://idp.example/.well-known/openid-configuration',
    )
    monkeypatch.setattr(
        'backend.services.auth_oidc.create_oauth_client',
        lambda: _FakeOAuth(
            {
                'sub': 'platform-admin-oidc',
                'email': 'platform-admin@example.com',
                'name': 'Platform Admin',
                'roles': ['Admin'],
            }
        ),
    )
    monkeypatch.setattr('backend.services.auth_oidc._ensure_oidc_enabled', lambda: None)

    response = await async_client.get(f"{AUTH['oidc_callback']}?code=test-code&state=test-state")

    assert response.status_code == 302
    assert response.headers['location'] == '/'

    session = await async_client.get(AUTH['me'])
    assert session.status_code == 200, session.text
    assert session.json()['app_roles'] == ['admin']
    assert 'manage_platform' in session.json()['effective_capabilities']

    backup_config = await async_client.get(BACKUPS['config'])
    assert backup_config.status_code == 200, backup_config.text
    assert user['email'] == 'platform-admin@example.com'


@pytest.mark.asyncio
async def test_saml_endpoints_handle_assertion_and_create_session(async_client, monkeypatch):
    _set_auth_settings(
        monkeypatch,
        auth_provider='saml',
        saml_metadata_url='https://idp.example/metadata',
        saml_entity_id='https://app.example/api/auth/saml/metadata',
        saml_acs_url='https://app.example/api/auth/saml/acs',
    )
    monkeypatch.setattr('backend.routers.auth.get_metadata_xml', lambda: '<xml>metadata</xml>')
    monkeypatch.setattr('backend.services.auth_saml._ensure_saml_enabled', lambda: None)

    async def fake_create_saml_auth(_request):
        return _FakeSamlAuth(
            attributes={'email': ['saml@example.com'], 'displayName': ['SAML User']},
            name_id='saml-subject',
        )

    monkeypatch.setattr(
        'backend.services.auth_saml.create_saml_auth',
        fake_create_saml_auth,
    )

    metadata = await async_client.get(AUTH['saml_metadata'])
    assert metadata.status_code == 200
    assert '<xml>metadata</xml>' in metadata.text

    login = await async_client.get(AUTH['saml_login'])
    assert login.status_code == 302
    assert login.headers['location'] == 'https://sso.example/login'

    acs = await async_client.post(AUTH['saml_acs'], data={'SAMLResponse': 'fake'})
    assert acs.status_code == 302
    assert acs.headers['location'] == '/'

    session = await async_client.get(AUTH['me'])
    assert session.status_code == 200, session.text
    assert session.json()['user']['auth_provider'] == 'saml'
    assert session.json()['family']['name'] == 'SSO Test Family'
