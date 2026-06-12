from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from backend.config import settings
from backend.rate_limit import RateLimitRule
from backend.security import get_request_ip, is_secure_request
from backend.services.capabilities import get_capability_registry
from backend.services.storage import _resolve_safe_upload_destination
from tests.contracts import AUTH, STUDENTS, SUBMISSIONS, bootstrap_payload
from tests.helpers import assert_validation_error, response_id


async def test_cookie_security_and_headers(async_client) -> None:
    original = settings.trust_proxy_headers
    settings.trust_proxy_headers = True
    try:
        response = await async_client.post(
            AUTH['register'],
            json=bootstrap_payload(),
            headers={'x-forwarded-proto': 'https'},
        )
    finally:
        settings.trust_proxy_headers = original
    assert response.status_code == 201, response.text
    set_cookie_headers = response.headers.get_list('set-cookie')
    assert any(settings.session_cookie_name in header and 'HttpOnly' in header and 'SameSite=lax' in header and 'Secure' in header for header in set_cookie_headers)
    assert any(settings.csrf_cookie_name in header and 'SameSite=lax' in header and 'Secure' in header for header in set_cookie_headers)
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert 'frame-ancestors' in response.headers['content-security-policy']
    assert response.headers['strict-transport-security'].startswith('max-age=')


def test_is_secure_request_ignores_forwarded_proto_without_proxy_trust(monkeypatch):
    monkeypatch.setattr(settings, 'trust_proxy_headers', False)
    request = Request(
        {
            'type': 'http',
            'scheme': 'http',
            'path': '/',
            'headers': [(b'x-forwarded-proto', b'https')],
            'client': ('10.0.0.10', 5000),
        }
    )
    assert is_secure_request(request) is False


def test_get_request_ip_defaults_to_client_host_when_proxy_headers_untrusted(monkeypatch):
    monkeypatch.setattr(settings, 'trust_proxy_headers', False)
    request = Request(
        {
            'type': 'http',
            'scheme': 'http',
            'path': '/',
            'headers': [(b'x-forwarded-for', b'203.0.113.10, 10.0.0.2')],
            'client': ('10.0.0.2', 5000),
        }
    )
    assert get_request_ip(request) == '10.0.0.2'


def test_get_request_ip_uses_forwarded_for_when_proxy_headers_trusted(monkeypatch):
    monkeypatch.setattr(settings, 'trust_proxy_headers', True)
    request = Request(
        {
            'type': 'http',
            'scheme': 'http',
            'path': '/',
            'headers': [(b'x-forwarded-for', b'203.0.113.10, 10.0.0.2')],
            'client': ('10.0.0.2', 5000),
        }
    )
    assert get_request_ip(request) == '203.0.113.10'


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


async def test_password_policy_rejects_common_password(async_client):
    response = await async_client.post(
        AUTH['register'],
        json=bootstrap_payload(password='Password1234'),
    )
    assert_validation_error(response)
    assert 'too common' in response.text


async def test_password_policy_rejects_passwords_over_bcrypt_limit(async_client):
    response = await async_client.post(
        AUTH['register'],
        json=bootstrap_payload(password='a' * 72 + '1'),
    )
    assert_validation_error(response)
    assert '72 bytes or fewer' in response.text


async def test_login_rejects_passwords_over_bcrypt_limit(authorized_client, secondary_client):
    response = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'a' * 72 + '1'},
    )
    assert_validation_error(response)
    assert '72 bytes or fewer' in response.text


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
        files={'file': ('large.png', b'a' * (settings.upload_max_bytes + 1), 'image/png')},
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
            assert response.json()['error']['code'] == 'rate_limited'


async def test_http_500_errors_do_not_expose_exception_details(app, monkeypatch):
    registry = get_capability_registry()

    async def _http_500():
        raise HTTPException(status_code=500, detail='sensitive\nstack trace')

    monkeypatch.setattr(registry, 'check_all', _http_500)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        response = await client.get('/api/capabilities')

    assert response.status_code == 500, response.text
    payload = response.json()
    assert payload['error']['code'] == 'internal_error'
    assert payload['detail'] == 'An unexpected error occurred.'
    assert payload['error']['message'] == 'An unexpected error occurred.'
    assert 'details' not in payload['error']
    assert 'sensitive' not in response.text


async def test_internal_errors_do_not_expose_exception_details(app, monkeypatch):
    registry = get_capability_registry()

    async def _boom():
        raise RuntimeError('sensitive\ntraceback details')

    monkeypatch.setattr(registry, 'check_all', _boom)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        response = await client.get('/api/capabilities')

    assert response.status_code == 500, response.text
    payload = response.json()
    assert payload['error']['code'] == 'internal_error'
    assert payload['detail'] == 'An unexpected error occurred.'
    assert payload['error']['message'] == 'An unexpected error occurred.'
    assert 'details' not in payload['error']
    assert 'sensitive' not in response.text


# ── Path Traversal Protection ─────────────────────────────────────────────


def test_path_traversal_dotdot_in_path_rejected(tmp_path):
    with pytest.raises(ValueError):
        _resolve_safe_upload_destination(str(tmp_path), Path('../evil'))


def test_path_traversal_dotdot_escaping_root_rejected(tmp_path):
    # 1/../../evil normalizes to ../evil — one level above upload root.
    with pytest.raises(ValueError):
        _resolve_safe_upload_destination(str(tmp_path), Path('1/../../evil'))


def test_path_traversal_absolute_path_rejected(tmp_path):
    with pytest.raises(ValueError):
        _resolve_safe_upload_destination(str(tmp_path), Path('/etc/passwd'))


def test_path_traversal_empty_path_rejected(tmp_path):
    with pytest.raises(ValueError):
        _resolve_safe_upload_destination(str(tmp_path), Path(''))


def test_path_traversal_dot_path_rejected(tmp_path):
    with pytest.raises(ValueError):
        _resolve_safe_upload_destination(str(tmp_path), Path('.'))


def test_path_traversal_url_encoded_dotdot_does_not_escape_upload_root(tmp_path):
    # %2e%2e is a literal directory name at the filesystem level; os.path.normpath does
    # NOT decode URL encoding, so this path stays safely within the upload root.
    safe_rel, dest = _resolve_safe_upload_destination(str(tmp_path), Path('%2e%2e/file.png'))
    assert str(dest).startswith(str(tmp_path))


def test_path_traversal_double_encoded_dotdot_does_not_escape_upload_root(tmp_path):
    # %252e%252e stays within the upload root; double-encoding is not decoded at path level.
    safe_rel, dest = _resolve_safe_upload_destination(str(tmp_path), Path('%252e%252e/file.png'))
    assert str(dest).startswith(str(tmp_path))


@pytest.mark.xfail(reason="Null byte rejection in storage depends on OS/Python behavior; regression target for Ray's fix.")
def test_path_traversal_null_byte_in_filename_rejected(tmp_path):
    # Null bytes in paths should be rejected to prevent OS-level truncation attacks.
    with pytest.raises((ValueError, TypeError, OSError)):
        _resolve_safe_upload_destination(str(tmp_path), Path('file\x00.png'))


def test_path_traversal_valid_nested_path_accepted(tmp_path):
    safe_rel, dest = _resolve_safe_upload_destination(
        str(tmp_path), Path('1/2/3/4/file.png')
    )
    assert str(dest).startswith(str(tmp_path))
    assert dest.name == 'file.png'


def test_path_traversal_single_filename_accepted(tmp_path):
    safe_rel, dest = _resolve_safe_upload_destination(str(tmp_path), Path('file.png'))
    assert str(dest).startswith(str(tmp_path))
    assert dest.name == 'file.png'


def test_path_traversal_dotdot_staying_in_root_normalizes_safely(tmp_path):
    # 1/2/../../etc normalizes to etc/ — still within the upload root. This is allowed.
    safe_rel, dest = _resolve_safe_upload_destination(str(tmp_path), Path('1/2/../../etc'))
    assert str(dest).startswith(str(tmp_path))


# ── Stack Trace Exposure ───────────────────────────────────────────────────


async def test_auth_login_500_does_not_expose_stack_trace(app):
    from backend.database import get_db as _real_get_db

    async def _broken_db():
        raise RuntimeError('password=s3cr3t host=internal-db.corp.local')

    app.dependency_overrides[_real_get_db] = _broken_db
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            response = await client.post(
                AUTH['login'],
                json={'email': 'test@example.com', 'password': 'TestPass123'},
            )
    finally:
        app.dependency_overrides.pop(_real_get_db, None)

    assert response.status_code == 500, response.text
    assert 'Traceback' not in response.text
    assert 'password=s3cr3t' not in response.text
    assert 'internal-db.corp.local' not in response.text
    assert response.json()['error']['code'] == 'internal_error'
    assert response.json()['error']['message'] == 'An unexpected error occurred.'


async def test_health_endpoint_500_does_not_expose_stack_trace(app, monkeypatch):
    import backend.routers.health as health_router_module

    async def _broken(*args, **kwargs):
        raise RuntimeError('db password=secret123 host=10.0.0.5')

    monkeypatch.setattr(health_router_module, 'build_simple_health_payload', _broken)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        response = await client.get('/api/health')

    # Health endpoint may return 500 or 503 on unexpected failure — either is a server error.
    assert response.status_code in {500, 503}, response.text
    assert 'Traceback' not in response.text
    assert 'password=secret123' not in response.text
    assert '10.0.0.5' not in response.text
    # Runtime exception details must not appear in any form in the response body.
    assert 'RuntimeError' not in response.text


async def test_error_response_never_contains_internal_file_path(app, monkeypatch):
    registry = get_capability_registry()

    async def _path_leak():
        raise RuntimeError(
            'error in /home/deploy/.source/GitHub/homeschool-hero/backend/services/storage.py line 99'
        )

    monkeypatch.setattr(registry, 'check_all', _path_leak)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        response = await client.get('/api/capabilities')

    assert response.status_code == 500, response.text
    assert '/home/deploy' not in response.text
    assert 'homeschool-hero' not in response.text
    assert 'storage.py' not in response.text
    assert response.json()['error']['code'] == 'internal_error'


async def test_http_500_exception_detail_not_forwarded_from_auth(app):
    from backend.database import get_db as _real_get_db

    async def _raises_http500():
        raise HTTPException(status_code=500, detail='DB trace: table users col password_hash')

    app.dependency_overrides[_real_get_db] = _raises_http500
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url='http://testserver') as client:
            response = await client.post(
                AUTH['login'],
                json={'email': 'test@example.com', 'password': 'TestPass123'},
            )
    finally:
        app.dependency_overrides.pop(_real_get_db, None)

    assert response.status_code == 500, response.text
    assert 'password_hash' not in response.text
    assert 'table users' not in response.text
    assert response.json()['error']['code'] == 'internal_error'
