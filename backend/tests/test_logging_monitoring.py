from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from backend.config import settings
from backend.services.capabilities import get_capability_registry


def _request_logs(caplog):
    return [
        record
        for record in caplog.records
        if getattr(record, 'action', None) == 'http_request' and isinstance(getattr(record, 'details', None), dict)
    ]


def test_request_logging_propagates_correlation_id(app, caplog) -> None:
    from fastapi.testclient import TestClient

    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        response = client.get('/api/capabilities', headers={'x-correlation-id': 'corr-123'})

    assert response.status_code == 200
    assert response.headers['X-Correlation-ID'] == 'corr-123'
    request_record = next(record for record in _request_logs(caplog) if record.details['path'] == '/api/capabilities')
    assert request_record.correlation_id == 'corr-123'
    assert request_record.details['status_code'] == 200
    assert request_record.details['method'] == 'GET'


def test_health_endpoints_are_not_request_logged(app, caplog) -> None:
    from fastapi.testclient import TestClient

    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        response = client.get('/api/health')

    assert response.status_code == 200
    assert not any(record.details.get('path') == '/api/health' for record in _request_logs(caplog))


@pytest.mark.asyncio
async def test_slow_requests_log_warning(async_client, caplog, monkeypatch) -> None:
    caplog.set_level(logging.INFO)
    registry = get_capability_registry()
    original = registry.check_all

    async def slow_check_all():
        await asyncio.sleep(1.05)
        return await original()

    monkeypatch.setattr(registry, 'check_all', slow_check_all)

    response = await async_client.get('/api/capabilities')

    assert response.status_code == 200
    request_record = next(record for record in _request_logs(caplog) if record.details['path'] == '/api/capabilities')
    assert request_record.levelno == logging.WARNING
    assert request_record.details['duration_ms'] > 1000


@pytest.mark.asyncio
async def test_metrics_endpoint_reports_request_grading_and_backup_state(
    authorized_client,
    seeded_submission,
    tmp_path: Path,
    monkeypatch,
) -> None:
    backup_dir = tmp_path / 'backups'
    backup_dir.mkdir()
    (backup_dir / '.last-success').write_text('2026-05-09T00:00:00Z', encoding='utf-8')
    (backup_dir / '.last-success-size').write_text('2048', encoding='utf-8')
    (backup_dir / 'homeschool-hero_20260509T000000Z_db.sql.gz').write_text('x', encoding='utf-8')
    monkeypatch.setattr(settings, 'enable_metrics_endpoint', True)
    monkeypatch.setattr(settings, 'backup_target', str(backup_dir))

    warmup = await authorized_client.get('/api/capabilities')
    assert warmup.status_code == 200

    response = await authorized_client.get('/api/metrics')

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['enabled'] is True
    assert payload['requests_total'] >= 1
    assert payload['grading_jobs_total'] >= 1
    assert payload['grading_jobs_by_status']['queued'] >= 1
    assert payload['backup_last_success']['size_bytes'] == 2048
