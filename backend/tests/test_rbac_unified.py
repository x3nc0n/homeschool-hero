from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import User
from backend.security import AuthSession, resolve_external_app_roles
from backend.services.auth_oidc import extract_identity as extract_oidc_identity
from backend.services.auth_provisioning import ExternalIdentity, provision_external_identity
from backend.services.auth_saml import extract_identity as extract_saml_identity
from backend.services.authorization import Capability, has_capability
from tests.contracts import AUTH, BACKUPS, CURRICULUM, GRADES, GRADING, STUDENTS, student_payload
from tests.helpers import response_id, sync_csrf_header

AUTH_PROVIDERS = ('local', 'oidc', 'saml')
EXTERNAL_ROLE_MAPPINGS = (
    ('Admin', 'admin'),
    ('Teacher', 'teacher'),
    ('Student', 'student'),
)

ADMIN_ROUTE = BACKUPS['config']
TEACHER_ROUTE = CURRICULUM['packages']
STUDENT_PROGRESS_ROUTE = GRADES['history']


@pytest.fixture
def jwt_auth_settings(monkeypatch):
    monkeypatch.setattr(settings, 'jwt_enabled', True, raising=False)
    monkeypatch.setattr(settings, 'jwt_secret', 'rbac-jwt-test-secret-with-32-char-minimum', raising=False)
    monkeypatch.setattr(settings, 'jwt_jwks_url', '', raising=False)
    monkeypatch.setattr(settings, 'jwt_algorithm', 'HS256', raising=False)
    monkeypatch.setattr(settings, 'jwt_issuer', 'https://issuer.example.test', raising=False)
    monkeypatch.setattr(settings, 'jwt_audience', 'homeschool-hero-tests', raising=False)
    return {
        'secret': settings.jwt_secret,
        'issuer': settings.jwt_issuer,
        'audience': settings.jwt_audience,
        'algorithm': settings.jwt_algorithm,
    }


def _issue_token(
    jwt_auth_settings: dict[str, str],
    *,
    roles: list[str],
    family_id: int | None,
    user_id: int,
    family_role: str | None = None,
    student_id: int | None = None,
    auth_provider: str = 'jwt',
    expires_in_seconds: int = 3600,
    issuer: str | None = None,
    audience: str | None = None,
    secret: str | None = None,
    extra_claims: dict[str, object] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, object] = {
        'iss': issuer or jwt_auth_settings['issuer'],
        'aud': audience or jwt_auth_settings['audience'],
        'sub': str(user_id),
        'user_id': user_id,
        'email': f'user{user_id}@example.com',
        'name': f'User {user_id}',
        'roles': roles,
        'auth_provider': auth_provider,
        'iat': int(now.timestamp()),
        'nbf': int((now - timedelta(seconds=30)).timestamp()),
        'exp': int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    if family_id is not None:
        claims['family_id'] = family_id
    if family_role is not None:
        claims['family_role'] = family_role
    if student_id is not None:
        claims['student_id'] = student_id
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, secret or jwt_auth_settings['secret'], algorithm=jwt_auth_settings['algorithm'])


async def _login_local(client, *, email: str, password: str, family_id: int) -> None:
    response = await client.post(AUTH['login'], json={'email': email, 'password': password, 'family_id': family_id})
    assert response.status_code == 200, response.text
    sync_csrf_header(client)


async def _family_id_from_client(client) -> int:
    me = await client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    return me.json()['family']['id']


def _bearer_headers(token: str, *, family_id_header: int | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {token}'}
    if family_id_header is not None:
        headers['X-Family-Id'] = str(family_id_header)
    return headers


def _issue_entra_token(
    jwt_auth_settings: dict[str, str],
    *,
    tenant_id: str,
    object_id: str,
    email: str,
    roles: list[str],
    display_name: str = 'Entra User',
    expires_in_seconds: int = 3600,
    issuer: str | None = None,
    audience: str | None = None,
    secret: str | None = None,
    extra_claims: dict[str, object] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, object] = {
        'iss': issuer or settings.jwt_issuer or jwt_auth_settings['issuer'],
        'aud': audience or settings.jwt_audience or jwt_auth_settings['audience'],
        'sub': f'entra-subject-{object_id}',
        'tid': tenant_id,
        'oid': object_id,
        'preferred_username': email,
        'name': display_name,
        'roles': roles,
        'iat': int(now.timestamp()),
        'nbf': int((now - timedelta(seconds=30)).timestamp()),
        'exp': int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, secret or jwt_auth_settings['secret'], algorithm=jwt_auth_settings['algorithm'])


async def _link_user_to_external_identity(*, user_id: int, provider: str, external_id: str) -> None:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        assert user is not None
        user.auth_provider = provider
        user.external_id = external_id
        await db.commit()


async def _create_bearer_member(
    create_family_user,
    *,
    family_id: int,
    email: str,
    role: str,
    student_id: int | None = None,
    is_owner: bool = False,
) -> dict[str, int | str | None]:
    return await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email=email,
        password='strongpass-bearer',
        display_name=email.split('@', 1)[0].replace('-', ' ').title(),
        role=role,
        student_id=student_id,
        is_owner=is_owner,
    )


class TestUnifiedRBACAccessMatrix:
    @pytest.mark.asyncio
    @pytest.mark.parametrize('provider', AUTH_PROVIDERS, ids=AUTH_PROVIDERS)
    async def test_admin_can_access_admin_only_routes_for_each_provider(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        jwt_auth_settings,
        provider: str,
    ):
        family_id = await _family_id_from_client(authorized_client)
        if provider == 'local':
            response = await authorized_client.get(ADMIN_ROUTE)
        else:
            user = await _create_bearer_member(
                create_family_user,
                family_id=family_id,
                email=f'admin-{provider}@example.com',
                role='tutor',
            )
            token = _issue_token(
                jwt_auth_settings,
                roles=['Admin'],
                family_id=family_id,
                user_id=user['user_id'],
                family_role='tutor',
                auth_provider=provider,
            )
            response = await secondary_client.get(ADMIN_ROUTE, headers=_bearer_headers(token))
        assert response.status_code == 200, response.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize('provider', AUTH_PROVIDERS, ids=AUTH_PROVIDERS)
    async def test_teacher_can_access_curriculum_and_grading_routes_for_each_provider(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        jwt_auth_settings,
        provider: str,
    ):
        family_id = await _family_id_from_client(authorized_client)
        if provider == 'local':
            await create_family_user(
                family_name='Test Family',
                family_id=family_id,
                email='teacher-local@example.com',
                password='strongpass234',
                display_name='Teacher Local',
                role='tutor',
            )
            await _login_local(secondary_client, email='teacher-local@example.com', password='strongpass234', family_id=family_id)
            packages = await secondary_client.get(TEACHER_ROUTE)
            grading_jobs = await secondary_client.get(GRADING['jobs'])
        else:
            user = await _create_bearer_member(
                create_family_user,
                family_id=family_id,
                email=f'teacher-{provider}@example.com',
                role='tutor',
            )
            token = _issue_token(
                jwt_auth_settings,
                roles=['Teacher'],
                family_id=family_id,
                user_id=user['user_id'],
                family_role='tutor',
                auth_provider=provider,
            )
            headers = _bearer_headers(token)
            packages = await secondary_client.get(TEACHER_ROUTE, headers=headers)
            grading_jobs = await secondary_client.get(GRADING['jobs'], headers=headers)
        assert packages.status_code == 200, packages.text
        assert grading_jobs.status_code == 200, grading_jobs.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize('provider', AUTH_PROVIDERS, ids=AUTH_PROVIDERS)
    async def test_student_can_only_read_owned_records_for_each_provider(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        seeded_student,
        jwt_auth_settings,
        provider: str,
    ):
        family_id = await _family_id_from_client(authorized_client)
        own_student_id = response_id(seeded_student)
        other_student_response = await authorized_client.post(STUDENTS['collection'], json=student_payload('Other Student'))
        assert other_student_response.status_code == 201, other_student_response.text
        other_student_id = response_id(other_student_response.json())

        if provider == 'local':
            await create_family_user(
                family_name='Test Family',
                family_id=family_id,
                email='student-local@example.com',
                password='strongpass345',
                display_name='Student Local',
                role='student_viewer',
                student_id=own_student_id,
            )
            await _login_local(secondary_client, email='student-local@example.com', password='strongpass345', family_id=family_id)
            own_detail = await secondary_client.get(STUDENTS['detail'].format(student_id=own_student_id))
            other_detail = await secondary_client.get(STUDENTS['detail'].format(student_id=other_student_id))
            own_history = await secondary_client.get(f"{STUDENT_PROGRESS_ROUTE}?student_id={own_student_id}")
            other_history = await secondary_client.get(f"{STUDENT_PROGRESS_ROUTE}?student_id={other_student_id}")
        else:
            user = await _create_bearer_member(
                create_family_user,
                family_id=family_id,
                email=f'student-{provider}@example.com',
                role='student_viewer',
                student_id=own_student_id,
            )
            token = _issue_token(
                jwt_auth_settings,
                roles=['Student'],
                family_id=family_id,
                user_id=user['user_id'],
                family_role='student_viewer',
                student_id=own_student_id,
                auth_provider=provider,
            )
            headers = _bearer_headers(token)
            own_detail = await secondary_client.get(STUDENTS['detail'].format(student_id=own_student_id), headers=headers)
            other_detail = await secondary_client.get(STUDENTS['detail'].format(student_id=other_student_id), headers=headers)
            own_history = await secondary_client.get(f"{STUDENT_PROGRESS_ROUTE}?student_id={own_student_id}", headers=headers)
            other_history = await secondary_client.get(f"{STUDENT_PROGRESS_ROUTE}?student_id={other_student_id}", headers=headers)

        assert own_detail.status_code == 200, own_detail.text
        assert own_history.status_code == 200, own_history.text
        assert other_detail.status_code == 403, other_detail.text
        assert other_history.status_code == 403, other_history.text

    @pytest.mark.asyncio
    async def test_same_internal_role_has_same_access_across_all_providers(
        self,
        authorized_client,
        secondary_client,
        tertiary_client,
        create_family_user,
        jwt_auth_settings,
    ):
        family_id = await _family_id_from_client(authorized_client)
        await create_family_user(
            family_name='Test Family',
            family_id=family_id,
            email='teacher-compare@example.com',
            password='strongpass456',
            display_name='Teacher Compare',
            role='tutor',
        )
        await _login_local(secondary_client, email='teacher-compare@example.com', password='strongpass456', family_id=family_id)

        local_statuses = {
            'admin': (await secondary_client.get(ADMIN_ROUTE)).status_code,
            'curriculum': (await secondary_client.get(TEACHER_ROUTE)).status_code,
            'grading': (await secondary_client.get(GRADING['jobs'])).status_code,
        }

        external_statuses = []
        for provider, client in (('oidc', tertiary_client), ('saml', authorized_client)):
            user = await _create_bearer_member(
                create_family_user,
                family_id=family_id,
                email=f'teacher-compare-{provider}@example.com',
                role='tutor',
            )
            token = _issue_token(
                jwt_auth_settings,
                roles=['Teacher'],
                family_id=family_id,
                user_id=user['user_id'],
                family_role='tutor',
                auth_provider=provider,
            )
            headers = _bearer_headers(token)
            external_statuses.append(
                {
                    'admin': (await client.get(ADMIN_ROUTE, headers=headers)).status_code,
                    'curriculum': (await client.get(TEACHER_ROUTE, headers=headers)).status_code,
                    'grading': (await client.get(GRADING['jobs'], headers=headers)).status_code,
                }
            )

        assert local_statuses == {'admin': 403, 'curriculum': 200, 'grading': 200}
        assert all(statuses == local_statuses for statuses in external_statuses)


class TestUnifiedRBACStatusCodes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ('method', 'path'),
        (
            ('GET', ADMIN_ROUTE),
            ('POST', TEACHER_ROUTE),
            ('GET', STUDENTS['detail'].format(student_id=1)),
            ('GET', f'{STUDENT_PROGRESS_ROUTE}?student_id=1'),
        ),
        ids=('admin-route', 'teacher-route', 'student-self-route', 'student-progress-route'),
    )
    async def test_unauthenticated_requests_return_401(self, async_client, method: str, path: str):
        response = await async_client.request(method, path)
        assert response.status_code == 401, response.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize('provider', AUTH_PROVIDERS, ids=AUTH_PROVIDERS)
    async def test_authenticated_user_with_wrong_role_gets_403(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        seeded_student,
        jwt_auth_settings,
        provider: str,
    ):
        family_id = await _family_id_from_client(authorized_client)
        student_id = response_id(seeded_student)
        if provider == 'local':
            await create_family_user(
                family_name='Test Family',
                family_id=family_id,
                email='student-denied@example.com',
                password='strongpass567',
                display_name='Student Denied',
                role='student_viewer',
                student_id=student_id,
            )
            await _login_local(secondary_client, email='student-denied@example.com', password='strongpass567', family_id=family_id)
            response = await secondary_client.get(ADMIN_ROUTE)
        else:
            user = await _create_bearer_member(
                create_family_user,
                family_id=family_id,
                email=f'student-denied-{provider}@example.com',
                role='student_viewer',
                student_id=student_id,
            )
            token = _issue_token(
                jwt_auth_settings,
                roles=['Student'],
                family_id=family_id,
                user_id=user['user_id'],
                family_role='student_viewer',
                student_id=student_id,
                auth_provider=provider,
            )
            response = await secondary_client.get(ADMIN_ROUTE, headers=_bearer_headers(token))
        assert response.status_code == 403, response.text

    @pytest.mark.asyncio
    async def test_expired_bearer_token_returns_401(self, authorized_client, secondary_client, jwt_auth_settings):
        family_id = await _family_id_from_client(authorized_client)
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher'],
            family_id=family_id,
            user_id=9300,
            family_role='tutor',
            expires_in_seconds=-30,
        )
        response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token))
        assert response.status_code == 401, response.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize('provider', AUTH_PROVIDERS, ids=AUTH_PROVIDERS)
    async def test_valid_role_for_route_returns_200(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        jwt_auth_settings,
        provider: str,
    ):
        family_id = await _family_id_from_client(authorized_client)
        if provider == 'local':
            await create_family_user(
                family_name='Test Family',
                family_id=family_id,
                email='teacher-ok@example.com',
                password='strongpass678',
                display_name='Teacher OK',
                role='tutor',
            )
            await _login_local(secondary_client, email='teacher-ok@example.com', password='strongpass678', family_id=family_id)
            response = await secondary_client.get(TEACHER_ROUTE)
        else:
            user = await _create_bearer_member(
                create_family_user,
                family_id=family_id,
                email=f'teacher-ok-{provider}@example.com',
                role='tutor',
            )
            token = _issue_token(
                jwt_auth_settings,
                roles=['Teacher'],
                family_id=family_id,
                user_id=user['user_id'],
                family_role='tutor',
                auth_provider=provider,
            )
            response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token))
        assert response.status_code == 200, response.text


class TestUnifiedRBACRoleExtraction:
    def test_oidc_roles_claim_maps_to_internal_role(self, monkeypatch):
        monkeypatch.setattr(settings, 'oidc_roles_claim', 'roles', raising=False)
        identity = extract_oidc_identity(
            {
                'sub': 'oidc-user',
                'email': 'oidc@example.com',
                'name': 'OIDC User',
                'roles': ['Teacher'],
            }
        )
        assert identity.roles == ('teacher',)

    def test_oidc_groups_claim_is_used_as_fallback_when_roles_claim_missing(self, monkeypatch):
        monkeypatch.setattr(
            'backend.config.settings.oidc_group_role_map',
            '{"entra-admins": "Admin"}',
            raising=False,
        )
        identity = extract_oidc_identity(
            {
                'sub': 'oidc-user',
                'email': 'oidc@example.com',
                'name': 'OIDC User',
                'groups': ['entra-admins'],
            }
        )
        assert identity.roles == ('admin',)

    def test_saml_role_attribute_maps_to_internal_role(self, monkeypatch):
        monkeypatch.setattr('backend.config.settings.saml_role_attribute', 'CustomRole', raising=False)
        identity = extract_saml_identity(
            type(
                'SamlAuthStub',
                (),
                {
                    'get_attributes': lambda self: {
                        'email': ['saml@example.com'],
                        'displayName': ['SAML User'],
                        'CustomRole': ['Student'],
                    },
                    'get_nameid': lambda self: 'saml-user',
                },
            )()
        )
        assert identity.roles == ('student',)

    def test_missing_external_role_claim_fails_closed(self, caplog):
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


class TestUnifiedRBACRoleMapping:
    @pytest.mark.parametrize('external_role, internal_role', EXTERNAL_ROLE_MAPPINGS)
    def test_external_roles_map_to_expected_internal_roles(self, external_role: str, internal_role: str):
        assert resolve_external_app_roles([external_role]) == [internal_role]

    def test_unknown_external_role_fails_closed(self):
        assert resolve_external_app_roles(['Unknown Role']) == []


class TestUnifiedRBACConflictResolution:
    def test_sso_admin_claim_and_local_student_membership_follow_defined_precedence(self):
        auth = AuthSession(
            user_id=1,
            family_id=1,
            email='admin-student@example.com',
            display_name='Admin Student',
            auth_provider='oidc',
            family_role='student_viewer',
            app_roles=['admin'],
            student_id=42,
            family_name='Test Family',
        )
        assert has_capability(auth, Capability.manage_platform)
        assert not has_capability(auth, Capability.read_students)

    @pytest.mark.asyncio
    async def test_sso_user_without_local_membership_follows_provisioning_policy(self, monkeypatch):
        monkeypatch.setattr(settings, 'auth_auto_provision_mode', 'default_family', raising=False)
        monkeypatch.setattr(settings, 'auth_default_family_name', 'SSO Users', raising=False)
        async with AsyncSessionLocal() as db:
            provisioned = await provision_external_identity(
                db,
                ExternalIdentity(
                    provider='oidc',
                    external_id='oidc-user-1',
                    email='fresh-sso@example.com',
                    display_name='Fresh SSO',
                    roles=('teacher',),
                ),
            )
        assert provisioned.created_default_family_membership is True
        assert provisioned.family.name == 'SSO Users'


class TestEntraBearerRBAC:
    @pytest.mark.asyncio
    async def test_entra_bearer_token_resolves_oidc_user_by_object_id_and_family_header(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        jwt_auth_settings,
        monkeypatch,
    ):
        tenant_id = 'b9735550-cbce-4703-9c6e-e0e51de71a0d'
        monkeypatch.setattr(settings, 'jwt_tenant_id', tenant_id, raising=False)
        monkeypatch.setattr(settings, 'jwt_issuer', f'https://login.microsoftonline.com/{tenant_id}/v2.0', raising=False)
        family_id = await _family_id_from_client(authorized_client)
        user = await create_family_user(
            family_name='Test Family',
            family_id=family_id,
            email='entra-teacher@example.com',
            password='strongpass-entra',
            display_name='Entra Teacher',
            role='tutor',
        )
        await _link_user_to_external_identity(user_id=user['user_id'], provider='oidc', external_id='entra-oid-1')
        token = _issue_entra_token(
            jwt_auth_settings,
            tenant_id=tenant_id,
            object_id='entra-oid-1',
            email='entra-teacher@example.com',
            display_name='Entra Teacher',
            roles=['Teacher'],
        )

        response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token, family_id_header=family_id))

        assert response.status_code == 200, response.text

    @pytest.mark.asyncio
    async def test_entra_bearer_token_rejects_wrong_tenant_id(
        self,
        authorized_client,
        secondary_client,
        jwt_auth_settings,
        monkeypatch,
    ):
        tenant_id = 'b9735550-cbce-4703-9c6e-e0e51de71a0d'
        monkeypatch.setattr(settings, 'jwt_tenant_id', tenant_id, raising=False)
        monkeypatch.setattr(settings, 'jwt_issuer', f'https://login.microsoftonline.com/{tenant_id}/v2.0', raising=False)
        family_id = await _family_id_from_client(authorized_client)
        token = _issue_entra_token(
            jwt_auth_settings,
            tenant_id='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            object_id='entra-oid-2',
            email='entra-user@example.com',
            roles=['Teacher'],
        )

        response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token, family_id_header=family_id))

        assert response.status_code == 401, response.text
        assert response.json()['detail'] == 'Bearer token tenant is invalid'

    @pytest.mark.asyncio
    async def test_entra_groups_overage_keeps_roles_claim_authoritative(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        jwt_auth_settings,
        monkeypatch,
        caplog,
    ):
        tenant_id = 'b9735550-cbce-4703-9c6e-e0e51de71a0d'
        monkeypatch.setattr(settings, 'jwt_tenant_id', tenant_id, raising=False)
        monkeypatch.setattr(settings, 'jwt_issuer', f'https://login.microsoftonline.com/{tenant_id}/v2.0', raising=False)
        caplog.set_level(logging.WARNING)
        family_id = await _family_id_from_client(authorized_client)
        user = await create_family_user(
            family_name='Test Family',
            family_id=family_id,
            email='entra-student@example.com',
            password='strongpass-entra-student',
            display_name='Entra Student',
            role='student_viewer',
            student_name='Entra Student',
        )
        await _link_user_to_external_identity(user_id=user['user_id'], provider='oidc', external_id='entra-oid-3')
        token = _issue_entra_token(
            jwt_auth_settings,
            tenant_id=tenant_id,
            object_id='entra-oid-3',
            email='entra-student@example.com',
            display_name='Entra Student',
            roles=['Student'],
            extra_claims={
                'groups': ['entra-admin-group'],
                '_claim_names': {'groups': 'src1'},
                '_claim_sources': {'src1': {'endpoint': 'https://graph.example/groups'}},
            },
        )

        response = await secondary_client.get(ADMIN_ROUTE, headers=_bearer_headers(token, family_id_header=family_id))

        assert response.status_code == 403, response.text
        assert 'groups overage' in caplog.text


class TestNegativeSecurityCases:
    @pytest.mark.asyncio
    async def test_bearer_token_with_forged_family_header_returns_403(
        self,
        authorized_client,
        secondary_client,
        jwt_auth_settings,
    ):
        family_id = await _family_id_from_client(authorized_client)
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher'],
            family_id=family_id,
            user_id=9501,
            family_role='tutor',
        )

        response = await secondary_client.get(
            TEACHER_ROUTE,
            headers=_bearer_headers(token, family_id_header=family_id + 999),
        )

        assert response.status_code == 403, response.text

    @pytest.mark.asyncio
    async def test_bearer_token_cannot_set_is_owner_via_claims(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        jwt_auth_settings,
    ):
        family_id = await _family_id_from_client(authorized_client)
        user = await create_family_user(
            family_name='Test Family',
            family_id=family_id,
            email='claim-owner@example.com',
            password='strongpass-owner',
            display_name='Claim Owner',
            role='parent',
            is_owner=False,
        )
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher', 'Admin'],
            family_id=family_id,
            user_id=user['user_id'],
            family_role='parent',
            extra_claims={'is_owner': True},
        )

        response = await secondary_client.get(AUTH['me'], headers=_bearer_headers(token))

        assert response.status_code == 200, response.text
        assert response.json()['membership']['is_owner'] is False

    @pytest.mark.asyncio
    async def test_missing_family_role_claims_fail_closed(self, authorized_client, secondary_client, jwt_auth_settings):
        family_id = await _family_id_from_client(authorized_client)
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher'],
            family_id=family_id,
            user_id=9503,
        )

        response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token))

        assert response.status_code == 403, response.text

    @pytest.mark.asyncio
    async def test_expired_jwt_tokens_return_401(self, authorized_client, secondary_client, jwt_auth_settings):
        family_id = await _family_id_from_client(authorized_client)
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher'],
            family_id=family_id,
            user_id=9504,
            family_role='tutor',
            expires_in_seconds=-30,
        )

        response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token))

        assert response.status_code == 401, response.text

    @pytest.mark.asyncio
    async def test_jwt_with_invalid_signature_returns_401(self, authorized_client, secondary_client, jwt_auth_settings):
        family_id = await _family_id_from_client(authorized_client)
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher'],
            family_id=family_id,
            user_id=9505,
            family_role='tutor',
            secret='wrong-signing-secret-with-32-char-minimum',
        )

        response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token))

        assert response.status_code == 401, response.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ('issuer', 'audience'),
        (
            ('https://forged-issuer.example.test', None),
            (None, 'wrong-audience'),
        ),
        ids=('wrong-issuer', 'wrong-audience'),
    )
    async def test_jwt_with_wrong_issuer_or_audience_returns_401(
        self,
        authorized_client,
        secondary_client,
        jwt_auth_settings,
        issuer: str | None,
        audience: str | None,
    ):
        family_id = await _family_id_from_client(authorized_client)
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher'],
            family_id=family_id,
            user_id=9506,
            family_role='tutor',
            issuer=issuer,
            audience=audience,
        )

        response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token))

        assert response.status_code == 401, response.text

    @pytest.mark.asyncio
    async def test_bearer_token_for_nonexistent_user_returns_403_when_membership_lookup_fails(
        self, authorized_client, secondary_client, jwt_auth_settings
    ):
        family_id = await _family_id_from_client(authorized_client)
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher'],
            family_id=family_id,
            user_id=9951,
            family_role='tutor',
        )

        response = await secondary_client.get(AUTH['me'], headers=_bearer_headers(token))

        assert response.status_code == 403, response.text
        assert response.json()['detail'] == 'Bearer token family access is forbidden'

    @pytest.mark.asyncio
    async def test_valid_jwt_without_family_membership_returns_403_when_family_context_required(
        self,
        authorized_client,
        secondary_client,
        create_family_user,
        jwt_auth_settings,
    ):
        family_id = await _family_id_from_client(authorized_client)
        outsider = await create_family_user(
            family_name='Other Family',
            email='outsider@example.com',
            password='strongpass-outsider',
            display_name='Family Outsider',
            role='tutor',
        )
        token = _issue_token(
            jwt_auth_settings,
            roles=['Teacher'],
            family_id=family_id,
            user_id=outsider['user_id'],
            family_role='tutor',
        )

        response = await secondary_client.get(TEACHER_ROUTE, headers=_bearer_headers(token))

        assert response.status_code == 403, response.text

    def test_role_escalation_attempt_ignores_admin_group_fallback_when_roles_claim_present(self, monkeypatch):
        monkeypatch.setattr(settings, 'oidc_group_role_map', '{"group-admin": "Admin"}', raising=False)
        identity = extract_oidc_identity(
            {
                'sub': 'oidc-user',
                'email': 'oidc@example.com',
                'name': 'OIDC User',
                'roles': ['Teacher'],
                'groups': ['group-admin'],
            }
        )

        assert identity.roles == ('teacher',)

    def test_oidc_callback_manipulated_role_claims_are_normalized_not_trusted_raw(self, caplog):
        caplog.set_level(logging.WARNING)
        identity = extract_oidc_identity(
            {
                'sub': 'oidc-user',
                'email': 'oidc@example.com',
                'name': 'OIDC User',
                'roles': [' Teacher ', 'ADMIN', 'Unknown Role', 'student', 'Admin'],
            }
        )

        assert identity.roles == ('admin', 'teacher', 'student')
        assert 'Unknown Role' in caplog.text

    def test_saml_assertion_with_extra_role_attributes_combines_configured_and_common_attributes(
        self, monkeypatch
    ):
        monkeypatch.setattr('backend.config.settings.saml_role_attribute', 'CustomRole', raising=False)
        identity = extract_saml_identity(
            type(
                'SamlAuthStub',
                (),
                {
                    'get_attributes': lambda self: {
                        'email': ['saml@example.com'],
                        'displayName': ['SAML User'],
                        'CustomRole': ['Teacher'],
                        'Role': ['Admin'],
                        'role': ['Student'],
                    },
                    'get_nameid': lambda self: 'saml-user',
                },
            )()
        )

        assert identity.roles == ('admin', 'teacher', 'student')


class TestUnifiedRBACBackwardCompatibility:
    @pytest.mark.asyncio
    async def test_existing_local_family_roles_continue_to_authorize_current_users(self, authorized_client):
        response = await authorized_client.get(ADMIN_ROUTE)
        assert response.status_code == 200, response.text

    @pytest.mark.asyncio
    async def test_cookie_sessions_remain_valid_for_local_authentication(self, authorized_client):
        response = await authorized_client.get(AUTH['me'])
        assert response.status_code == 200, response.text
        assert response.json()['membership']['role'] == 'parent'

    def test_current_capability_checks_do_not_regress(self):
        parent = AuthSession(
            user_id=1,
            family_id=1,
            email='parent@example.com',
            display_name='Parent',
            auth_provider='local',
            family_role='parent',
            is_owner=True,
            family_name='Test Family',
        )
        student = AuthSession(
            user_id=2,
            family_id=1,
            email='student@example.com',
            display_name='Student',
            auth_provider='local',
            family_role='student_viewer',
            student_id=7,
            family_name='Test Family',
        )
        assert has_capability(parent, Capability.manage_family)
        assert has_capability(parent, Capability.manage_platform)
        assert has_capability(student, Capability.read_grades)
        assert not has_capability(student, Capability.manage_grading)
