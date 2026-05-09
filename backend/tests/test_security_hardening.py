from __future__ import annotations

from backend.config import settings
from backend.rate_limit import RateLimitRule
from tests.contracts import AUTH, STUDENTS, SUBMISSIONS, bootstrap_payload
from tests.helpers import response_id


async def test_cookie_security_and_headers(async_client) -> None:
    response = await async_client.post(
        AUTH['register'],
        json=bootstrap_payload(),
        headers={'x-forwarded-proto': 'https'},
    )
    assert response.status_code == 201, response.text
    set_cookie_headers = response.headers.get_list('set-cookie')
    assert any(settings.session_cookie_name in header and 'HttpOnly' in header and 'SameSite=lax' in header and 'Secure' in header for header in set_cookie_headers)
    assert any(settings.csrf_cookie_name in header and 'SameSite=lax' in header and 'Secure' in header for header in set_cookie_headers)
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert 'frame-ancestors' in response.headers['content-security-policy']
    assert response.headers['strict-transport-security'].startswith('max-age=')


async def test_csrf_protection_blocks_state_changes(authorized_client):
    authorized_client.headers['x-csrf-token'] = 'wrong-token'
    response = await authorized_client.post(STUDENTS['collection'], json={'name': 'Blocked Student'})
    assert response.status_code == 403, response.text
    assert response.json()['error']['code'] == 'csrf_failed'


async def test_password_policy_rejects_weak_password(async_client):
    response = await async_client.post(
        AUTH['register'],
        json=bootstrap_payload(password='short'),
    )
    assert response.status_code == 422, response.text
    assert response.json()['error']['code'] == 'validation_error'


async def test_account_lockout_after_failed_logins(authorized_client, secondary_client, monkeypatch):
    monkeypatch.setattr('backend.main.AUTH_RATE_LIMIT', RateLimitRule('auth', settings.auth_lockout_threshold + 2, 60))
    for _ in range(settings.auth_lockout_threshold):
        response = await secondary_client.post(
            AUTH['login'],
            json={'email': 'owner@example.com', 'password': 'wrong-password-123'},
        )
        assert response.status_code == 401, response.text

    locked = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': bootstrap_payload()['password']},
    )
    assert locked.status_code == 423, locked.text


async def test_auth_rate_limit_returns_429(async_client):
    for attempt in range(1, 7):
        response = await async_client.post(
            AUTH['login'],
            json={'email': 'missing@example.com', 'password': 'missing-password-123'},
        )
        if attempt <= 5:
            assert response.status_code == 401, response.text
        else:
            assert response.status_code == 429, response.text
            assert response.json()['error']['code'] == 'rate_limited'


async def test_upload_validation_rejects_oversized_and_invalid_mime(authorized_client, seeded_assignment, seeded_student):
    oversized = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('large.txt', b'a' * (settings.upload_max_bytes + 1), 'text/plain')},
    )
    assert oversized.status_code == 413, oversized.text

    invalid_type = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('malware.exe', b'1234', 'application/x-msdownload')},
    )
    assert invalid_type.status_code == 400, invalid_type.text


async def test_general_rate_limit_applies_to_api_requests(authorized_client, monkeypatch):
    monkeypatch.setattr('backend.main.GENERAL_RATE_LIMIT', RateLimitRule('general', 3, 60))
    for attempt in range(1, 5):
        response = await authorized_client.get(STUDENTS['collection'])
        if attempt <= 3:
            assert response.status_code == 200, response.text
        else:
            assert response.status_code == 429, response.text
