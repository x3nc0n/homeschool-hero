from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import jwt
import pytest
from sqlalchemy import select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import ApiToken
from backend.services.curriculum_ai_import import ExtractedSource
from tests.contracts import AUTH, CURRICULUM, SUBMISSIONS
from tests.helpers import response_id

PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0'
    b'\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82'
)


@pytest.fixture
def api_token_jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, 'jwt_enabled', True, raising=False)
    monkeypatch.setattr(settings, 'jwt_secret', 'api-token-jwt-secret-with-32-char-minimum', raising=False)
    monkeypatch.setattr(settings, 'jwt_jwks_url', '', raising=False)
    monkeypatch.setattr(settings, 'jwt_algorithm', 'HS256', raising=False)
    monkeypatch.setattr(settings, 'jwt_issuer', 'https://issuer.example.test', raising=False)
    monkeypatch.setattr(settings, 'jwt_audience', 'homeschool-hero-tests', raising=False)
    monkeypatch.setattr(settings, 'api_token_default_expiry_days', 90, raising=False)
    monkeypatch.setattr(settings, 'api_token_max_expiry_days', 365, raising=False)
    monkeypatch.setattr(settings, 'api_token_max_active_per_family', 10, raising=False)


def _curriculum_import_payload(name: str = 'API Token Curriculum') -> dict[str, object]:
    return {
        'schema_version': '1.0',
        'name': name,
        'description': 'Imported through API token.',
        'source': 'manual',
        'metadata': {
            'grade_levels': ['6'],
            'standards_alignment': ['ROOT-1'],
            'estimated_hours': 12,
            'prerequisites': ['Foundational reading'],
        },
        'subjects': [
            {
                'name': 'Math',
                'metadata': {
                    'grade_levels': ['6'],
                    'standards_alignment': ['MATH-1'],
                },
                'units': [
                    {
                        'name': 'Unit 1',
                        'metadata': {'standards_alignment': ['MATH-U1']},
                        'lessons': [
                            {
                                'name': 'Lesson 1',
                                'description': 'Intro lesson',
                                'estimated_minutes': 45,
                                'objectives': ['Understand ratios'],
                                'resources': [],
                                'metadata': {'standards_alignment': ['MATH-L1']},
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _bearer_headers(token: str, *, family_id_header: int | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {token}'}
    if family_id_header is not None:
        headers['X-Family-Id'] = str(family_id_header)
    return headers


async def _create_api_token(client, *, name: str, capabilities: list[str], expires_in_days: int = 30):
    return await client.post(
        AUTH['api_tokens'],
        json={
            'name': name,
            'capabilities': capabilities,
            'expires_in_days': expires_in_days,
        },
    )


def _issue_headless_token(
    *,
    user_id: int,
    family_id: int,
    email: str,
    name: str,
    capabilities: list[str],
    token_type: str | None = 'api_token',
    jti: str | None = None,
    expires_in_seconds: int = 3600,
) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, object] = {
        'iss': settings.jwt_issuer,
        'aud': settings.jwt_audience,
        'sub': str(user_id),
        'user_id': user_id,
        'family_id': family_id,
        'family_role': 'parent',
        'email': email,
        'name': name,
        'roles': ['Teacher'],
        'capabilities': capabilities,
        'iat': int(now.timestamp()),
        'nbf': int((now - timedelta(seconds=30)).timestamp()),
        'exp': int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    if token_type is not None:
        claims['token_type'] = token_type
    if jti is not None:
        claims['jti'] = jti
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.mark.asyncio
async def test_api_token_creation_requires_manage_security(api_token_jwt_settings, authorized_client, secondary_client, create_family_user):
    me = await authorized_client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    family_id = me.json()['family']['id']
    tutor = await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='token-tutor@example.com',
        password='strongpass-tutor',
        display_name='Token Tutor',
        role='tutor',
    )
    login = await secondary_client.post(
        AUTH['login'],
        json={'email': tutor['email'], 'password': tutor['password'], 'family_id': tutor['family_id']},
    )
    assert login.status_code == 200, login.text

    response = await _create_api_token(
        secondary_client,
        name='tutor-issuer',
        capabilities=['manage_curriculum'],
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_api_token_creation_returns_once_and_list_hides_digest(api_token_jwt_settings, authorized_client):
    created = await _create_api_token(
        authorized_client,
        name='curriculum-automation',
        capabilities=['manage_curriculum'],
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload['token']
    assert payload['capabilities'] == ['manage_curriculum']
    token_id = payload['id']

    listing = await authorized_client.get(AUTH['api_tokens'])
    assert listing.status_code == 200, listing.text
    items = listing.json()
    assert any(item['id'] == token_id for item in items)
    item = next(item for item in items if item['id'] == token_id)
    assert 'token' not in item
    assert 'token_digest' not in item


@pytest.mark.asyncio
async def test_api_token_creation_validates_payload(api_token_jwt_settings, authorized_client, monkeypatch):
    empty_caps = await _create_api_token(authorized_client, name='empty', capabilities=[])
    assert empty_caps.status_code == 422, empty_caps.text

    forbidden_cap = await _create_api_token(authorized_client, name='security', capabilities=['manage_security'])
    assert forbidden_cap.status_code == 422, forbidden_cap.text

    monkeypatch.setattr(settings, 'api_token_max_expiry_days', 5, raising=False)
    too_long = await _create_api_token(
        authorized_client,
        name='too-long',
        capabilities=['manage_curriculum'],
        expires_in_days=6,
    )
    assert too_long.status_code == 422, too_long.text


@pytest.mark.asyncio
async def test_api_token_duplicate_name_and_active_limit(api_token_jwt_settings, authorized_client, monkeypatch):
    monkeypatch.setattr(settings, 'api_token_max_active_per_family', 1, raising=False)
    first = await _create_api_token(authorized_client, name='limited-1', capabilities=['manage_curriculum'])
    assert first.status_code == 201, first.text

    duplicate = await _create_api_token(authorized_client, name='limited-1', capabilities=['manage_curriculum'])
    assert duplicate.status_code == 409, duplicate.text

    limit = await _create_api_token(authorized_client, name='limited-2', capabilities=['manage_curriculum'])
    assert limit.status_code == 409, limit.text


@pytest.mark.asyncio
async def test_api_token_missing_or_unregistered_jti_returns_401(api_token_jwt_settings, authorized_client, secondary_client):
    me = await authorized_client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    me_payload = me.json()
    user_id = me_payload['user']['id']
    family_id = me_payload['family']['id']
    email = me_payload['user']['email']
    display_name = me_payload['user']['display_name']

    missing_jti = _issue_headless_token(
        user_id=user_id,
        family_id=family_id,
        email=email,
        name=display_name,
        capabilities=['manage_curriculum'],
        jti=None,
    )
    response_missing = await secondary_client.post(
        CURRICULUM['import_create'],
        json=_curriculum_import_payload('Missing JTI'),
        headers=_bearer_headers(missing_jti),
    )
    assert response_missing.status_code == 401, response_missing.text

    unregistered = _issue_headless_token(
        user_id=user_id,
        family_id=family_id,
        email=email,
        name=display_name,
        capabilities=['manage_curriculum'],
        jti=str(uuid.uuid4()),
    )
    response_unregistered = await secondary_client.post(
        CURRICULUM['import_create'],
        json=_curriculum_import_payload('Unregistered JTI'),
        headers=_bearer_headers(unregistered),
    )
    assert response_unregistered.status_code == 401, response_unregistered.text


@pytest.mark.asyncio
async def test_api_token_revoked_expired_and_digest_mismatch_return_401(
    api_token_jwt_settings,
    authorized_client,
    secondary_client,
):
    created = await _create_api_token(authorized_client, name='revoked-token', capabilities=['manage_curriculum'])
    assert created.status_code == 201, created.text
    token_payload = created.json()
    token_id = token_payload['id']
    token = token_payload['token']

    revoke = await authorized_client.delete(f"{AUTH['api_tokens']}/{token_id}")
    assert revoke.status_code == 204, revoke.text
    revoked_use = await secondary_client.post(
        CURRICULUM['import_create'],
        json=_curriculum_import_payload('Revoked use'),
        headers=_bearer_headers(token),
    )
    assert revoked_use.status_code == 401, revoked_use.text

    digest_created = await _create_api_token(authorized_client, name='digest-token', capabilities=['manage_curriculum'])
    assert digest_created.status_code == 201, digest_created.text
    digest_payload = digest_created.json()
    async with AsyncSessionLocal() as session:
        digest_row = (await session.execute(select(ApiToken).where(ApiToken.id == digest_payload['id']))).scalar_one()
        digest_row.token_digest = '0' * 64
        await session.commit()
    digest_use = await secondary_client.post(
        CURRICULUM['import_create'],
        json=_curriculum_import_payload('Digest mismatch'),
        headers=_bearer_headers(digest_payload['token']),
    )
    assert digest_use.status_code == 401, digest_use.text

    expired_created = await _create_api_token(authorized_client, name='expired-token', capabilities=['manage_curriculum'])
    assert expired_created.status_code == 201, expired_created.text
    expired_payload = expired_created.json()
    async with AsyncSessionLocal() as session:
        expired_row = (await session.execute(select(ApiToken).where(ApiToken.id == expired_payload['id']))).scalar_one()
        expired_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        await session.commit()
    expired_use = await secondary_client.post(
        CURRICULUM['import_create'],
        json=_curriculum_import_payload('Expired token'),
        headers=_bearer_headers(expired_payload['token']),
    )
    assert expired_use.status_code == 401, expired_use.text


@pytest.mark.asyncio
async def test_api_token_capability_intersection_and_family_header_override(
    api_token_jwt_settings,
    authorized_client,
    secondary_client,
    create_family_user,
    seeded_assignment,
    seeded_student,
):
    me = await authorized_client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    family_id = me.json()['family']['id']
    other_family = await create_family_user(
        family_name='Another Family',
        email='other-family-owner@example.com',
        password='other-family-pass',
        display_name='Other Family Owner',
        role='parent',
        is_owner=True,
    )

    created = await _create_api_token(
        authorized_client,
        name='curriculum-only',
        capabilities=['manage_curriculum'],
    )
    assert created.status_code == 201, created.text
    token = created.json()['token']

    me_with_forged_header = await secondary_client.get(
        AUTH['me'],
        headers=_bearer_headers(token, family_id_header=other_family['family_id']),
    )
    assert me_with_forged_header.status_code == 200, me_with_forged_header.text
    assert me_with_forged_header.json()['family']['id'] == family_id

    import_response = await secondary_client.post(
        CURRICULUM['import_create'],
        json=_curriculum_import_payload('Scoped curriculum'),
        headers=_bearer_headers(token),
    )
    assert import_response.status_code == 201, import_response.text

    upload = await secondary_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('fractions.png', PNG_BYTES, 'image/png')},
        headers=_bearer_headers(token),
    )
    assert upload.status_code == 403, upload.text


@pytest.mark.asyncio
async def test_api_token_management_is_family_scoped(
    api_token_jwt_settings,
    authorized_client,
    secondary_client,
    create_family_user,
):
    created = await _create_api_token(
        authorized_client,
        name='family-a-token',
        capabilities=['manage_curriculum'],
    )
    assert created.status_code == 201, created.text
    token_id = created.json()['id']

    other_family = await create_family_user(
        family_name='Family B',
        email='family-b-owner@example.com',
        password='family-b-pass',
        display_name='Family B Owner',
        role='parent',
        is_owner=True,
    )
    login = await secondary_client.post(
        AUTH['login'],
        json={'email': other_family['email'], 'password': other_family['password'], 'family_id': other_family['family_id']},
    )
    assert login.status_code == 200, login.text

    listing = await secondary_client.get(AUTH['api_tokens'])
    assert listing.status_code == 200, listing.text
    assert all(item['id'] != token_id for item in listing.json())

    revoke = await secondary_client.delete(f"{AUTH['api_tokens']}/{token_id}")
    assert revoke.status_code == 404, revoke.text


@pytest.mark.asyncio
async def test_external_jwt_without_api_token_type_skips_registry_lookup(
    api_token_jwt_settings,
    authorized_client,
    secondary_client,
):
    me = await authorized_client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    me_payload = me.json()
    token = _issue_headless_token(
        user_id=me_payload['user']['id'],
        family_id=me_payload['family']['id'],
        email=me_payload['user']['email'],
        name=me_payload['user']['display_name'],
        capabilities=['manage_curriculum'],
        token_type=None,
        jti=str(uuid.uuid4()),
    )

    response = await secondary_client.get(AUTH['me'], headers=_bearer_headers(token))
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_api_token_supports_curriculum_ai_import_and_confirm(
    api_token_jwt_settings,
    authorized_client,
    secondary_client,
    monkeypatch,
):
    class _FakeAIImportService:
        async def build_draft_from_upload(self, _upload):
            raise AssertionError('upload flow not used in this test')

        async def build_draft_from_url(self, _url):
            return (
                _curriculum_import_payload('AI Draft'),
                ExtractedSource(
                    source_kind='url',
                    source_name='ai-draft.txt',
                    content_type='text/plain',
                    text='Generated curriculum text.',
                    source_url='https://example.com/ai-draft.txt',
                    warnings=[],
                ),
            )

    monkeypatch.setattr('backend.routers.curriculum.get_ai_curriculum_import_service', lambda: _FakeAIImportService())

    created = await _create_api_token(
        authorized_client,
        name='ai-importer',
        capabilities=['manage_curriculum'],
    )
    assert created.status_code == 201, created.text
    token = created.json()['token']

    draft = await secondary_client.post(
        CURRICULUM['ai_import'],
        json={'url': 'https://example.com/ai-draft.txt'},
        headers=_bearer_headers(token),
    )
    assert draft.status_code == 200, draft.text
    draft_payload = draft.json()['draft']
    draft_payload['name'] = 'AI Confirmed Curriculum'

    confirm = await secondary_client.post(
        CURRICULUM['ai_import_confirm'],
        json={'draft': draft_payload},
        headers=_bearer_headers(token),
    )
    assert confirm.status_code == 201, confirm.text
    assert confirm.json()['name'] == 'AI Confirmed Curriculum'


@pytest.mark.asyncio
async def test_api_token_supports_submission_upload_and_grading_job_access(
    api_token_jwt_settings,
    authorized_client,
    secondary_client,
    seeded_assignment,
    seeded_student,
):
    created = await _create_api_token(
        authorized_client,
        name='grading-automation',
        capabilities=['manage_submissions', 'manage_grading'],
    )
    assert created.status_code == 201, created.text
    token = created.json()['token']

    upload = await secondary_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('grading-upload.png', PNG_BYTES, 'image/png')},
        headers=_bearer_headers(token),
    )
    assert upload.status_code == 201, upload.text

    jobs = await secondary_client.get('/api/grading/jobs', headers=_bearer_headers(token))
    assert jobs.status_code == 200, jobs.text

    submissions_only = await _create_api_token(
        authorized_client,
        name='submissions-only',
        capabilities=['manage_submissions'],
    )
    assert submissions_only.status_code == 201, submissions_only.text
    denied_jobs = await secondary_client.get(
        '/api/grading/jobs',
        headers=_bearer_headers(submissions_only.json()['token']),
    )
    assert denied_jobs.status_code == 403, denied_jobs.text
