from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
from sqlalchemy import select

from backend.models import FamilyRole
from backend.services import invitations
from tests.contracts import AUTH, INVITATIONS, STUDENTS, student_payload
from tests.helpers import response_id


@pytest.mark.asyncio
async def test_invitation_create_list_accept_and_revoke(authorized_client, secondary_client, create_family_user, backend_module):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Invited Student'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    create_response = await authorized_client.post(
        INVITATIONS['collection'],
        json={
            'email': 'invitee@example.com',
            'role': 'student_viewer',
            'student_id': student_id,
            'expires_in_days': 7,
        },
    )
    assert create_response.status_code == 201, create_response.text
    invite = create_response.json()
    assert invite['delivery_method'] == 'link'
    assert invite['invite_link']
    assert invite['invite_code']

    listing = await authorized_client.get(INVITATIONS['collection'])
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 1

    accept_response = await secondary_client.post(
        INVITATIONS['accept'].format(invitation_id=invite['id']),
        json={
            'token': invite['invite_code'],
            'email': 'invitee@example.com',
            'display_name': 'Invited Viewer',
            'password': 'strongpass890',
        },
    )
    assert accept_response.status_code == 200, accept_response.text
    assert accept_response.json()['membership']['role'] == 'student_viewer'
    assert accept_response.json()['membership']['student_id'] == student_id

    me = await secondary_client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    assert me.json()['user']['email'] == 'invitee@example.com'

    revoked = await authorized_client.post(
        INVITATIONS['collection'],
        json={
            'email': 'revoke@example.com',
            'role': 'tutor',
            'expires_in_days': 7,
        },
    )
    assert revoked.status_code == 201, revoked.text
    revoke_id = revoked.json()['id']

    delete_response = await authorized_client.delete(INVITATIONS['revoke'].format(invitation_id=revoke_id))
    assert delete_response.status_code == 204, delete_response.text

    accept_revoked = await secondary_client.post(
        INVITATIONS['accept'].format(invitation_id=revoke_id),
        json={
            'token': revoked.json()['invite_code'],
            'email': 'revoke@example.com',
            'display_name': 'Revoked User',
            'password': 'strongpass901',
        },
    )
    assert accept_revoked.status_code == 404, accept_revoked.text


@pytest.mark.asyncio
async def test_invitation_expiry_blocks_acceptance(authorized_client, secondary_client):
    create_response = await authorized_client.post(
        INVITATIONS['collection'],
        json={
            'email': 'expired@example.com',
            'role': 'tutor',
            'expires_in_days': 7,
        },
    )
    assert create_response.status_code == 201, create_response.text
    invite = create_response.json()

    from backend.database import AsyncSessionLocal
    from backend.models import Invitation

    async with AsyncSessionLocal() as session:
        invitation = await session.get(Invitation, invite['id'])
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    accept_response = await secondary_client.post(
        INVITATIONS['accept'].format(invitation_id=invite['id']),
        json={
            'token': invite['invite_code'],
            'email': 'expired@example.com',
            'display_name': 'Expired User',
            'password': 'strongpass012',
        },
    )
    assert accept_response.status_code == 410, accept_response.text
    assert 'expired' in accept_response.json()['detail']


def test_dispatch_invitation_uses_configured_email_provider(monkeypatch) -> None:
    sent: dict[str, object] = {}

    monkeypatch.setattr(invitations, 'email_enabled', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        invitations,
        'send_email',
        lambda **kwargs: sent.update(kwargs),
    )

    delivery_method, delivered, invite_link = invitations.dispatch_invitation(
        email='invitee@example.com',
        family_name='Example Family',
        role=FamilyRole.tutor,
        invitation_id=42,
        token='token+value',
        expires_at=datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc),
    )

    assert delivery_method == 'email'
    assert delivered is True
    assert invite_link == f'/accept-invite/42?token={quote("token+value")}'
    assert sent['to_email'] == 'invitee@example.com'
    assert sent['subject'] == 'Join Example Family on Homeschool Hero'
    assert 'Accept invitation' in str(sent['html'])
