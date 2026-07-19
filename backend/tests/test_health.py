from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import settings


from tests.contracts import password_for_test
def _service(name: str, status: str, *, required: bool, configured: bool = True, message: str = 'ok') -> dict[str, object]:
    return {
        'name': name,
        'label': name.replace('_', ' ').title(),
        'required': required,
        'configured': configured,
        'status': status,
        'message': message,
        'checked_at': '2026-05-10T00:00:00Z',
        'response_time_ms': 1.23,
        'details': {},
    }


async def _wait_for_backup(client, job_id: int, *, timeout: float = 10.0) -> dict[str, object]:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(f'/api/backups/{job_id}')
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload['status'] in {'complete', 'failed'}:
            return payload
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail(f'Backup job {job_id} did not finish in time: {payload}')
        await asyncio.sleep(0.05)


def test_health_endpoint_reports_degraded_when_optional_service_is_down(app, monkeypatch) -> None:
    async def fake_collect(_config=settings):
        return {
            'database': _service('database', 'healthy', required=True),
            'ai_service': _service('ai_service', 'degraded', required=False, message='AI unavailable'),
            'smtp': _service('smtp', 'healthy', required=False),
            'backup_destination': _service('backup_destination', 'healthy', required=False),
            'disk_space': _service('disk_space', 'healthy', required=True),
        }

    monkeypatch.setattr('backend.services.health.collect_service_health', fake_collect)

    with TestClient(app) as client:
        response = client.get('/api/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload == {'status': 'ok', 'ready': True, 'maintenance': False}


def test_summarize_health_ignores_optional_not_configured_services() -> None:
    from backend.services.health import summarize_health

    services = {
        'database': _service('database', 'healthy', required=True),
        'ai_service': _service('ai_service', 'healthy', required=False),
        'disk_space': _service('disk_space', 'healthy', required=True),
        'smtp': _service('smtp', 'not_configured', required=False, configured=False),
        'backup_destination': _service('backup_destination', 'not_configured', required=False, configured=False),
    }

    overall, counts = summarize_health(services)

    assert overall == 'healthy'
    assert counts == {'healthy': 3, 'degraded': 0, 'unhealthy': 0, 'not_configured': 2}


def test_summarize_health_degrades_when_required_service_not_configured() -> None:
    from backend.services.health import summarize_health

    services = {
        'database': _service('database', 'not_configured', required=True, configured=False),
        'disk_space': _service('disk_space', 'healthy', required=True),
    }

    overall, _counts = summarize_health(services)

    assert overall == 'degraded'


def test_summarize_health_degrades_when_optional_service_degraded() -> None:
    from backend.services.health import summarize_health

    services = {
        'database': _service('database', 'healthy', required=True),
        'ai_service': _service('ai_service', 'degraded', required=False),
    }

    overall, _counts = summarize_health(services)

    assert overall == 'degraded'


def test_health_endpoint_reports_unhealthy_when_required_service_fails(app, monkeypatch) -> None:
    async def fake_collect(_config=settings):
        return {
            'database': _service('database', 'unhealthy', required=True, message='db down'),
            'ai_service': _service('ai_service', 'healthy', required=False),
            'smtp': _service('smtp', 'healthy', required=False),
            'backup_destination': _service('backup_destination', 'healthy', required=False),
            'disk_space': _service('disk_space', 'healthy', required=True),
        }

    monkeypatch.setattr('backend.services.health.collect_service_health', fake_collect)

    with TestClient(app) as client:
        response = client.get('/api/health')

    assert response.status_code == 503
    payload = response.json()
    assert payload == {'status': 'error', 'ready': False, 'maintenance': False}


def test_detailed_health_requires_authentication(app) -> None:
    with TestClient(app) as client:
        response = client.get('/api/health/detailed')
    assert response.status_code == 401


def test_readiness_probe_reports_ready(app) -> None:
    with TestClient(app) as client:
        response = client.get('/api/health/ready')
    assert response.status_code == 200
    payload = response.json()
    assert payload['ready'] is True
    assert payload['status'] == 'ready'


@pytest.mark.asyncio
async def test_detailed_health_scopes_backup_status_by_family(
    authorized_client,
    tertiary_client,
    create_family_user,
    tmp_path: Path,
    monkeypatch,
) -> None:
    backup_dir = tmp_path / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, 'backup_target', str(backup_dir))
    monkeypatch.setattr(settings, 'backup_destination', 'local')
    monkeypatch.setattr(settings, 'backup_scheduler_enabled', True)

    trigger = await authorized_client.post('/api/backups/trigger', json={'backup_type': 'manual'})
    assert trigger.status_code == 201, trigger.text
    job = await _wait_for_backup(authorized_client, trigger.json()['id'])
    assert job['status'] == 'complete'

    owner = await create_family_user(
        family_name='Other Family',
        email='owner-status@example.com',
        password=password_for_test('strongpass901'),
        display_name='Owner Status',
        role='parent',
        is_owner=True,
    )
    login = await tertiary_client.post(
        '/api/auth/login',
        json={'email': owner['email'], 'password': owner['password'], 'family_id': owner['family_id']},
    )
    assert login.status_code == 200, login.text

    primary_detail = await authorized_client.get('/api/health/detailed')
    assert primary_detail.status_code == 200, primary_detail.text
    primary_payload = primary_detail.json()
    assert primary_payload['backup']['last_backup']['id'] == job['id']

    secondary_detail = await tertiary_client.get('/api/health/detailed')
    assert secondary_detail.status_code == 200, secondary_detail.text
    secondary_payload = secondary_detail.json()
    assert secondary_payload['backup']['last_backup'] is None
