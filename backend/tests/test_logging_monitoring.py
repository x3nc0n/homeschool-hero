from __future__ import annotations

import asyncio
import json
import logging
from io import StringIO
from pathlib import Path

import pytest

from backend.config import settings
from backend.services.capabilities import get_capability_registry
from backend.services.logging_config import (
    ConsoleFormatter,
    JsonFormatter,
    RequestContextFilter,
    _sanitize_log_text,
    bind_context,
    clear_context,
    get_context,
    log_action,
)


def _request_logs(caplog):
    return [
        record
        for record in caplog.records
        if getattr(record, 'action', None) == 'http_request' and isinstance(getattr(record, 'details', None), dict)
    ]


def test_log_action_sanitizes_control_characters() -> None:
    stream = StringIO()
    logger = logging.getLogger('tests.logging.sanitization')
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    try:
        log_action(
            logger,
            logging.INFO,
            'message\nwith\rcontrol\x00chars',
            action='upload\nrequest',
            correlation_id='corr\r123',
            details={
                'filename': 'bad\nname.png',
                'nested': ['tab\tvalue', 'null\x00byte'],
            },
        )
    finally:
        logger.removeHandler(handler)
        logger.propagate = True

    payload = json.loads(stream.getvalue())
    assert payload['message'] == 'message\\nwith\\rcontrol\\x00chars'
    assert payload['action'] == 'upload\\nrequest'
    assert payload['correlation_id'] == 'corr\\r123'
    assert payload['details']['filename'] == 'bad\\nname.png'
    assert payload['details']['nested'] == ['tab\\tvalue', 'null\\x00byte']


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
    assert payload['grading_jobs_by_status']['pending'] >= 1
    assert payload['backup_last_success']['size_bytes'] == 2048


# ── Log Injection Prevention ───────────────────────────────────────────────


def test_sanitize_log_text_escapes_newlines() -> None:
    result = _sanitize_log_text('user\ninput\r')
    assert '\n' not in result
    assert '\r' not in result
    assert result == r'user\ninput\r'


def test_sanitize_log_text_escapes_null_bytes() -> None:
    result = _sanitize_log_text('file\x00.txt')
    assert '\x00' not in result
    assert r'\x00' in result


def test_sanitize_log_text_escapes_arbitrary_control_characters() -> None:
    result = _sanitize_log_text('data\x01\x1b\x7f')
    assert '\x01' not in result
    assert '\x1b' not in result
    assert '\x7f' not in result


def test_bind_context_sanitizes_newlines_in_correlation_id() -> None:
    # A malicious correlation ID containing newlines must not forge additional log lines.
    clear_context()
    bind_context(correlation_id='legit-id\nFAKE level=CRITICAL action=privilege_escalation')
    ctx = get_context()
    # The raw newline character must be escaped; the value must not contain a literal \n.
    assert '\n' not in str(ctx['correlation_id'])


def test_bind_context_sanitizes_control_characters_in_action() -> None:
    clear_context()
    bind_context(action='upload\x00file\rrequest')
    ctx = get_context()
    assert '\x00' not in str(ctx['action'])
    assert '\r' not in str(ctx['action'])


def test_json_formatter_produces_single_line_per_record_despite_injected_newlines() -> None:
    stream = StringIO()
    logger = logging.getLogger('tests.logging.injection')
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    try:
        log_action(
            logger,
            logging.INFO,
            'upload started',
            action='upload',
            correlation_id='corr-1\n{"level": "CRITICAL", "message": "forged entry"}',
        )
    finally:
        logger.removeHandler(handler)
        logger.propagate = True

    output = stream.getvalue().strip()
    # json.dumps escapes \n inside string values, so only one JSON line should exist.
    lines = [line for line in output.split('\n') if line.strip()]
    assert len(lines) == 1, f'Expected 1 log line, got {len(lines)}: {output!r}'
    payload = json.loads(lines[0])
    assert payload['level'] == 'INFO'
    # The injected content must appear only as escaped text inside the correlation_id value.
    assert '\n' not in payload.get('correlation_id', '')


def test_console_formatter_sanitizes_injected_newlines() -> None:
    """Newlines injected via user input must not produce extra lines in console output."""
    stream = StringIO()
    logger = logging.getLogger('tests.logging.console_inject')
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(ConsoleFormatter())
    logger.addHandler(handler)

    try:
        log_action(
            logger,
            logging.INFO,
            'message\nFAKE LOG ENTRY level=CRITICAL injected=true',
            action='upload\nINJECTED_ACTION',
        )
    finally:
        logger.removeHandler(handler)
        logger.propagate = True

    output = stream.getvalue()
    lines = output.rstrip('\n').split('\n')
    # No line should begin with "FAKE" — the injected content must be escaped.
    assert not any(line.startswith('FAKE') for line in lines), (
        f'Injected line found in console output: {output!r}'
    )
    assert 'INJECTED_ACTION' not in output.split('\\n')[0] if '\\n' in output else True


def test_log_action_sanitizes_details_dict_values() -> None:
    stream = StringIO()
    logger = logging.getLogger('tests.logging.details_inject')
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    try:
        log_action(
            logger,
            logging.INFO,
            'file processed',
            action='upload',
            details={
                'filename': 'legit.png\nINJECTED=true level=CRITICAL',
                'size': 1024,
            },
        )
    finally:
        logger.removeHandler(handler)
        logger.propagate = True

    output = stream.getvalue().strip()
    payload = json.loads(output)
    filename_logged = payload['details']['filename']
    assert '\n' not in filename_logged
    assert 'INJECTED=true' not in filename_logged.split('\\n')[0] if '\\n' in filename_logged else True
