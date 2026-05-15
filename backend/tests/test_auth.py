from __future__ import annotations

import pytest

from tests.contracts import AUTH, STUDENTS, bootstrap_payload, student_payload
from tests.helpers import response_id, sync_csrf_header


@pytest.mark.asyncio
async def test_bootstrap_register_creates_owner_session(async_client):
    status_before = await async_client.get(AUTH['bootstrap'])
    assert status_before.status_code == 200, status_before.text
    assert status_before.json()['bootstrap_required'] is True

    response = await async_client.post(AUTH['register'], json=bootstrap_payload())

    assert response.status_code == 201, response.text
    sync_csrf_header(async_client)
    payload = response.json()
    assert payload['authenticated'] is True
    assert payload['user']['email'] == 'owner@example.com'
    assert payload['family']['name'] == 'Test Family'
    assert payload['family']['enabled_features'] == {}
    assert payload['membership']['is_owner'] is True
    assert payload['app_roles'] == ['admin', 'teacher']
    assert 'manage_security' in payload['effective_capabilities']

    status_after = await async_client.get(AUTH['bootstrap'])
    assert status_after.status_code == 200, status_after.text
    assert status_after.json()['bootstrap_required'] is False


@pytest.mark.asyncio
async def test_register_is_disabled_after_bootstrap(authorized_client, async_client):
    response = await async_client.post(AUTH['register'], json=bootstrap_payload(email='second@example.com'))

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(authorized_client, secondary_client):
    response = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'definitely-wrong'},
    )

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_me_requires_authentication(async_client):
    response = await async_client.get(AUTH['me'])

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_logout_invalidates_session(authorized_client):
    logout = await authorized_client.post(AUTH['logout'])

    assert logout.status_code in {200, 204}, logout.text

    me = await authorized_client.get(AUTH['me'])
    assert me.status_code == 401, me.text


@pytest.mark.asyncio
async def test_family_feature_flags_flow_through_session_and_login(authorized_client, secondary_client):
    update = await authorized_client.put(
        '/api/family-settings/features',
        json={'enabled_features': {'attendance': False, 'planner': True, 'quizzes': False}},
    )

    assert update.status_code == 200, update.text
    assert update.json()['enabled_features'] == {'attendance': False, 'planner': True, 'quizzes': False}

    me = await authorized_client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    assert me.json()['family']['enabled_features'] == {'attendance': False, 'planner': True, 'quizzes': False}

    logout = await authorized_client.post(AUTH['logout'])
    assert logout.status_code in {200, 204}, logout.text

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'strongpass123'},
    )
    assert login.status_code == 200, login.text
    assert login.json()['family']['enabled_features'] == {'attendance': False, 'planner': True, 'quizzes': False}


@pytest.mark.asyncio
async def test_tenant_isolation_blocks_cross_family_reads(authorized_client, secondary_client, create_family_user):
    created = await authorized_client.post(STUDENTS['collection'], json=student_payload('Ada Primary'))
    assert created.status_code == 201, created.text
    student_id = response_id(created.json())

    await create_family_user(
        family_name='Other Family',
        email='other@example.com',
        password='strongpass456',
        display_name='Other Parent',
    )
    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'other@example.com', 'password': 'strongpass456'},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    collection = await secondary_client.get(STUDENTS['collection'])
    assert collection.status_code == 200, collection.text
    assert collection.json() == []

    detail = await secondary_client.get(STUDENTS['detail'].format(student_id=student_id))
    assert detail.status_code == 404, detail.text
