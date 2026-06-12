from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from backend.services.logging_config import JsonFormatter, RequestContextFilter
from backend.services.security_events import AuthFailureEvent, SecurityActor, SecurityTarget, emit_security_event
from tests.contracts import AUTH, STUDENTS, bootstrap_payload, student_payload
from tests.helpers import response_id, sync_csrf_header


def _security_records(caplog):
    return [record for record in caplog.records if getattr(record, 'event_category', None) == 'security']


def test_emit_security_event_writes_structured_json_payload() -> None:
    stream = StringIO()
    logger = logging.getLogger('tests.security-events.structured')
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    try:
        emit_security_event(
            logger,
            AuthFailureEvent(
                actor=SecurityActor(user_id=42, email='owner@example.com'),
                target=SecurityTarget(resource='/api/auth/login', id='42', type='auth_endpoint'),
                source_ip='203.0.113.10',
                user_agent='pytest-agent/1.0',
                correlation_id='corr-123',
                details={'reason': 'bad_password'},
            ),
        )
    finally:
        logger.removeHandler(handler)
        logger.propagate = True

    payload = json.loads(stream.getvalue())
    assert payload['event_category'] == 'security'
    assert payload['event_type'] == 'auth_failure'
    assert payload['result'] == 'failure'
    assert payload['actor'] == {'user_id': 42, 'email': 'owner@example.com'}
    assert payload['target'] == {'resource': '/api/auth/login', 'id': '42', 'type': 'auth_endpoint'}
    assert payload['source_ip'] == '203.0.113.10'
    assert payload['user_agent'] == 'pytest-agent/1.0'
    assert payload['correlation_id'] == 'corr-123'
    assert payload['details'] == {'reason': 'bad_password'}
    assert payload['timestamp']


def test_emit_security_event_sanitizes_nested_values() -> None:
    stream = StringIO()
    logger = logging.getLogger('tests.security-events.sanitization')
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    try:
        emit_security_event(
            logger,
            AuthFailureEvent(
                actor=SecurityActor(email='owner@example.com\nforged'),
                target=SecurityTarget(resource='/api/auth/login', type='auth_endpoint'),
                correlation_id='corr-123\rforged',
                details={'reason': 'bad\npassword'},
            ),
        )
    finally:
        logger.removeHandler(handler)
        logger.propagate = True

    payload = json.loads(stream.getvalue())
    assert payload['actor']['email'] == 'owner@example.com\\nforged'
    assert payload['correlation_id'] == 'corr-123\\rforged'
    assert payload['details']['reason'] == 'bad\\npassword'


@pytest.mark.asyncio
async def test_login_emits_auth_success_and_session_created(authorized_client, secondary_client, caplog) -> None:
    await authorized_client.post(AUTH['logout'])
    caplog.clear()
    caplog.set_level(logging.INFO)

    response = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': bootstrap_payload()['password']},
    )

    assert response.status_code == 200, response.text
    records = _security_records(caplog)
    event_types = [record.event_type for record in records]
    assert 'auth_success' in event_types
    assert 'session_created' in event_types


@pytest.mark.asyncio
async def test_login_failure_emits_auth_failure(authorized_client, secondary_client, caplog) -> None:
    caplog.clear()
    caplog.set_level(logging.WARNING)

    response = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'definitely-wrong'},
    )

    assert response.status_code == 401, response.text
    auth_failure = next(record for record in _security_records(caplog) if record.event_type == 'auth_failure')
    assert auth_failure.result == 'failure'
    assert auth_failure.actor['email'] == 'owner@example.com'
    assert auth_failure.details['reason'] == 'bad_password'


@pytest.mark.asyncio
async def test_student_scope_denial_emits_rbac_event(
    authorized_client,
    secondary_client,
    create_family_user,
    seeded_student,
    caplog,
) -> None:
    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']
    scoped_student_id = response_id(seeded_student)
    extra_student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Unauthorized Access'))
    assert extra_student.status_code == 201, extra_student.text
    extra_student_id = response_id(extra_student.json())

    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='viewer@example.com',
        password='strongpass456',
        display_name='Viewer User',
        role='student_viewer',
        student_id=scoped_student_id,
    )

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'viewer@example.com', 'password': 'strongpass456', 'family_id': family_id},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    caplog.clear()
    caplog.set_level(logging.WARNING)
    forbidden = await secondary_client.get(STUDENTS['detail'].format(student_id=extra_student_id))

    assert forbidden.status_code == 403, forbidden.text
    denial = next(record for record in _security_records(caplog) if record.event_type == 'rbac_denial')
    assert denial.result == 'failure'
    assert denial.details['reason'] == 'student_scope_mismatch'
