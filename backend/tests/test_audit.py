from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from tests.contracts import AUDIT, AUTH, GRADES, INVITATIONS, STUDENTS, bootstrap_payload, grade_payload, student_payload
from tests.helpers import response_id, sync_csrf_header, update_resource


async def _list_audit_events():
    from backend.database import AsyncSessionLocal
    from backend.models import AuditEvent

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditEvent).order_by(AuditEvent.id))
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_auth_events_are_audited(async_client, secondary_client):
    register = await async_client.post(AUTH['register'], json=bootstrap_payload(family_name='Audit Family'))
    assert register.status_code == 201, register.text
    sync_csrf_header(async_client)

    logout = await async_client.post(AUTH['logout'])
    assert logout.status_code == 200, logout.text

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': bootstrap_payload()['password']},
    )
    assert login.status_code == 200, login.text

    events = await _list_audit_events()
    actions = [event.action.value for event in events]
    assert actions == ['logout', 'login']
    assert events[0].before_snapshot == {
        'authenticated': True,
        'family_id': 1,
        'user_id': 1,
        'role': 'parent',
        'auth_provider': 'local',
    }
    assert events[0].after_snapshot == {'authenticated': False}
    assert events[0].ip_address
    assert events[0].user_agent
    assert events[1].after_snapshot['role'] == 'parent'


@pytest.mark.asyncio
async def test_grade_create_and_update_are_audited(authorized_client, seeded_submission, seeded_student):
    create = await authorized_client.post(
        GRADES['collection'],
        json=grade_payload(response_id(seeded_submission), response_id(seeded_student)),
    )
    assert create.status_code == 201, create.text
    grade_id = response_id(create.json())

    update = await update_resource(
        authorized_client,
        GRADES['detail'].format(grade_id=grade_id),
        {
            **grade_payload(response_id(seeded_submission), response_id(seeded_student)),
            'score': 94,
            'letter_grade': 'A',
        },
    )
    assert update.status_code == 200, update.text

    events = await _list_audit_events()
    grade_events = [event for event in events if event.target_entity_type == 'grade']
    assert [event.action.value for event in grade_events] == ['grade_create', 'grade_update']
    assert grade_events[0].after_snapshot['score'] == 88
    assert grade_events[0].before_snapshot is None
    assert grade_events[1].before_snapshot['score'] == 88
    assert grade_events[1].after_snapshot['score'] == 94


@pytest.mark.asyncio
async def test_invitation_create_and_accept_are_audited(authorized_client, secondary_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Audit Student'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    create = await authorized_client.post(
        INVITATIONS['collection'],
        json={'email': 'invitee@example.com', 'role': 'student_viewer', 'student_id': student_id, 'expires_in_days': 7},
    )
    assert create.status_code == 201, create.text
    invitation = create.json()

    accept = await secondary_client.post(
        INVITATIONS['accept'].format(invitation_id=invitation['id']),
        json={
            'token': invitation['invite_code'],
            'email': 'invitee@example.com',
            'display_name': 'Invited Viewer',
            'password': 'strongpass890',
        },
    )
    assert accept.status_code == 200, accept.text

    events = await _list_audit_events()
    invite_events = [event for event in events if event.target_entity_type == 'invitation']
    assert [event.action.value for event in invite_events] == ['invitation_create', 'invitation_accept']
    assert invite_events[0].after_snapshot['student_id'] == student_id
    assert invite_events[1].before_snapshot['accepted_at'] is None
    assert invite_events[1].after_snapshot['accepted_by_user_id'] == accept.json()['user']['id']


@pytest.mark.asyncio
async def test_audit_api_supports_filters_and_pagination(authorized_client, seeded_submission, seeded_student):
    create = await authorized_client.post(
        GRADES['collection'],
        json=grade_payload(response_id(seeded_submission), response_id(seeded_student)),
    )
    assert create.status_code == 201, create.text
    grade_id = response_id(create.json())

    update = await update_resource(
        authorized_client,
        GRADES['detail'].format(grade_id=grade_id),
        {
            **grade_payload(response_id(seeded_submission), response_id(seeded_student)),
            'score': 93,
            'letter_grade': 'A',
        },
    )
    assert update.status_code == 200, update.text

    listing = await authorized_client.get(AUDIT['collection'], params={'page': 1, 'page_size': 1})
    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert payload['total'] >= 2
    assert payload['page'] == 1
    assert payload['page_size'] == 1
    assert len(payload['items']) == 1

    date_from = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    filtered = await authorized_client.get(
        AUDIT['collection'],
        params={
            'action': 'grade_update',
            'entity_type': 'grade',
            'entity_id': str(grade_id),
            'actor': 'Parent User',
            'date_from': date_from,
        },
    )
    assert filtered.status_code == 200, filtered.text
    filtered_payload = filtered.json()
    assert filtered_payload['total'] == 1
    assert filtered_payload['items'][0]['action'] == 'grade_update'
    assert filtered_payload['items'][0]['target_entity_id'] == str(grade_id)
    assert filtered_payload['items'][0]['actor_display_name'] == 'Parent User'


@pytest.mark.asyncio
async def test_audit_api_blocks_non_admin_roles(authorized_client, secondary_client, create_family_user):
    me = await authorized_client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    family_id = me.json()['family']['id']

    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='tutor@example.com',
        password='strongpass456',
        display_name='Tutor User',
        role='tutor',
    )
    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'tutor@example.com', 'password': 'strongpass456', 'family_id': family_id},
    )
    assert login.status_code == 200, login.text

    audit_response = await secondary_client.get(AUDIT['collection'])
    assert audit_response.status_code == 403, audit_response.text
