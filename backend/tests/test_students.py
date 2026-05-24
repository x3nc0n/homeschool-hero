from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.config import settings
from tests.contracts import AUTH, STUDENTS, student_payload
from tests.helpers import assert_validation_error, response_id, sync_csrf_header, update_resource


@pytest.mark.asyncio
async def test_students_crud_happy_path(authorized_client):
    create = await authorized_client.post(STUDENTS["collection"], json=student_payload())
    assert create.status_code in {200, 201}, create.text
    created = create.json()
    student_id = response_id(created)

    listing = await authorized_client.get(STUDENTS["collection"])
    assert listing.status_code == 200, listing.text
    assert any(response_id(item) == student_id for item in listing.json())

    detail = await authorized_client.get(STUDENTS["detail"].format(student_id=student_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "Ada Lovelace"

    update = await update_resource(
        authorized_client,
        STUDENTS["detail"].format(student_id=student_id),
        student_payload(name="Grace Hopper"),
    )
    assert update.status_code == 200, update.text
    assert update.json()["name"] == "Grace Hopper"

    delete = await authorized_client.delete(STUDENTS["detail"].format(student_id=student_id))
    assert delete.status_code == 204, delete.text


@pytest.mark.asyncio
async def test_students_reject_invalid_payload(authorized_client):
    response = await authorized_client.post(STUDENTS["collection"], json={})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_students_return_404_for_missing_id(authorized_client):
    response = await authorized_client.get(STUDENTS["detail"].format(student_id=999999))

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_students_require_authentication(async_client):
    response = await async_client.get(STUDENTS["collection"])

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_tutor_cannot_create_students(authorized_client, secondary_client, create_family_user):
    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']
    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='tutor@example.com',
        password='strongpass789',
        display_name='Tutor',
        role='tutor',
    )

    login = await secondary_client.post(AUTH['login'], json={'email': 'tutor@example.com', 'password': 'strongpass789', 'family_id': family_id})
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    response = await secondary_client.post(STUDENTS['collection'], json=student_payload(name='Tutor Blocked Student'))

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_app_role_can_create_students_via_student_management_capability(
    authorized_client,
    secondary_client,
    create_family_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, 'jwt_enabled', True, raising=False)
    monkeypatch.setattr(settings, 'jwt_secret', 'students-jwt-secret-with-32-char-minimum', raising=False)
    monkeypatch.setattr(settings, 'jwt_jwks_url', '', raising=False)
    monkeypatch.setattr(settings, 'jwt_algorithm', 'HS256', raising=False)
    monkeypatch.setattr(settings, 'jwt_issuer', 'https://issuer.example.test', raising=False)
    monkeypatch.setattr(settings, 'jwt_audience', 'homeschool-hero-tests', raising=False)

    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']
    admin_user = await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='admin-student-manager@example.com',
        password='strongpass789',
        display_name='Admin Student Manager',
        role='tutor',
    )

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            'iss': settings.jwt_issuer,
            'aud': settings.jwt_audience,
            'sub': str(admin_user['user_id']),
            'user_id': admin_user['user_id'],
            'family_id': family_id,
            'family_role': 'tutor',
            'email': 'admin-student-manager@example.com',
            'name': 'Admin Student Manager',
            'roles': ['Admin'],
            'iat': int(now.timestamp()),
            'nbf': int((now - timedelta(seconds=30)).timestamp()),
            'exp': int((now + timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await secondary_client.post(
        STUDENTS['collection'],
        json=student_payload(name='Admin Managed Student'),
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code in {200, 201}, response.text
    assert response.json()['name'] == 'Admin Managed Student'
