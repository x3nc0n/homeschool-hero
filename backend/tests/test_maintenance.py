from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.config import settings
from tests.contracts import AUTH, STUDENTS, bootstrap_payload
from tests.helpers import sync_csrf_header

MAINTENANCE = '/api/admin/maintenance'
MAINTENANCE_SCHEDULE = '/api/admin/maintenance/schedule'


@pytest.mark.asyncio
async def test_admin_can_toggle_and_read_maintenance_status(authorized_client):
    enable = await authorized_client.post(MAINTENANCE, json={'enabled': True, 'message': 'Scheduled upgrades underway.'})
    assert enable.status_code == 200, enable.text
    assert enable.json()['active'] is True
    assert enable.json()['message'] == 'Scheduled upgrades underway.'

    status = await authorized_client.get(MAINTENANCE)
    assert status.status_code == 200, status.text
    assert status.json()['enabled'] is True
    assert status.json()['source'] == 'manual'


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_maintenance(authorized_client, secondary_client, create_family_user):
    await create_family_user(
        family_id=1,
        family_name='Test Family',
        email='tutor@example.com',
        password='strongpass456',
        display_name='Tutor User',
        role='tutor',
    )
    login = await secondary_client.post(AUTH['login'], json={'email': 'tutor@example.com', 'password': 'strongpass456'})
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    response = await secondary_client.get(MAINTENANCE)
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_maintenance_blocks_non_admin_requests_but_allows_admin_bypass(authorized_client, secondary_client, create_family_user):
    await create_family_user(
        family_id=1,
        family_name='Test Family',
        email='tutor@example.com',
        password='strongpass456',
        display_name='Tutor User',
        role='tutor',
    )
    login = await secondary_client.post(AUTH['login'], json={'email': 'tutor@example.com', 'password': 'strongpass456'})
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    enabled = await authorized_client.post(MAINTENANCE, json={'enabled': True, 'message': 'Platform maintenance in progress.'})
    assert enabled.status_code == 200, enabled.text

    blocked = await secondary_client.get(STUDENTS['collection'])
    assert blocked.status_code == 503, blocked.text
    assert blocked.json()['error']['code'] == 'maintenance_mode'

    allowed = await authorized_client.get(STUDENTS['collection'])
    assert allowed.status_code == 200, allowed.text


@pytest.mark.asyncio
async def test_non_admin_login_is_blocked_during_maintenance_but_admin_login_still_works(
    authorized_client,
    secondary_client,
    tertiary_client,
    create_family_user,
):
    await create_family_user(
        family_id=1,
        family_name='Test Family',
        email='tutor@example.com',
        password='strongpass456',
        display_name='Tutor User',
        role='tutor',
    )
    await authorized_client.post(MAINTENANCE, json={'enabled': True, 'message': 'Platform maintenance in progress.'})

    tutor_login = await secondary_client.post(AUTH['login'], json={'email': 'tutor@example.com', 'password': 'strongpass456'})
    assert tutor_login.status_code == 503, tutor_login.text

    admin_login = await tertiary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': bootstrap_payload()['password']},
    )
    assert admin_login.status_code == 200, admin_login.text


@pytest.mark.asyncio
async def test_scheduled_maintenance_activates_automatically(monkeypatch, authorized_client, secondary_client, create_family_user):
    await create_family_user(
        family_id=1,
        family_name='Test Family',
        email='tutor@example.com',
        password='strongpass456',
        display_name='Tutor User',
        role='tutor',
    )
    login = await secondary_client.post(AUTH['login'], json={'email': 'tutor@example.com', 'password': 'strongpass456'})
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    start = datetime.now(timezone.utc) - timedelta(minutes=5)
    end = datetime.now(timezone.utc) + timedelta(minutes=15)
    scheduled = await authorized_client.put(
        MAINTENANCE_SCHEDULE,
        json={'start_at': start.isoformat(), 'end_at': end.isoformat(), 'message': 'Scheduled maintenance window.'},
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()['scheduled'] is True
    assert scheduled.json()['schedule_active'] is True

    blocked = await secondary_client.get(STUDENTS['collection'])
    assert blocked.status_code == 503, blocked.text

    future = end + timedelta(minutes=5)
    monkeypatch.setattr('backend.services.maintenance._utcnow', lambda: future)
    status = await authorized_client.get(MAINTENANCE)
    assert status.status_code == 200, status.text
    assert status.json()['active'] is False
    assert status.json()['source'] == 'off'


@pytest.mark.asyncio
async def test_https_redirect_applies_when_tls_enabled(monkeypatch, async_client):
    monkeypatch.setattr(settings, 'tls_enabled', True)
    monkeypatch.setattr(settings, 'https_redirect_enabled', True)

    redirect = await async_client.get('/api/capabilities', follow_redirects=False)
    assert redirect.status_code == 307, redirect.text
    assert redirect.headers['location'] == 'https://testserver/api/capabilities'

    health = await async_client.get('/health', follow_redirects=False)
    assert health.status_code in {200, 503}, health.text
