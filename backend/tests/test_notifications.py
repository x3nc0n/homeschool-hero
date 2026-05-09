from __future__ import annotations

import smtplib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import Assignment, AssignmentStatus, Notification, NotificationType
from backend.services.notifications import create_notification, run_notification_maintenance, update_notification_preferences
from tests.contracts import AUTH, NOTIFICATIONS, SUBJECTS, assignment_payload, subject_payload


async def _current_session(authorized_client):
    response = await authorized_client.get(AUTH['me'])
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload['user']['id'], payload['family']['id']


@pytest.mark.asyncio
async def test_notifications_crud_and_filters(authorized_client):
    user_id, family_id = await _current_session(authorized_client)

    async with AsyncSessionLocal() as db:
        await create_notification(
            db,
            user_id,
            NotificationType.due_date,
            'Due soon: Reading log',
            'Reading log is due tomorrow.',
            '/assignments',
            family_id=family_id,
        )
        await create_notification(
            db,
            user_id,
            NotificationType.grading_complete,
            'Grading complete: Fractions',
            'A new grade is ready to review.',
            '/grades',
            family_id=family_id,
        )
        await db.commit()

    response = await authorized_client.get(f"{NOTIFICATIONS['collection']}?read=false&page=1&page_size=10")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['total'] == 2
    assert payload['unread_count'] == 2

    first_notification_id = payload['items'][0]['id']
    mark_read = await authorized_client.patch(
        NOTIFICATIONS['detail_read'].format(notification_id=first_notification_id),
        json={'read': True},
    )
    assert mark_read.status_code == 200, mark_read.text
    assert mark_read.json()['read'] is True

    unread = await authorized_client.get(f"{NOTIFICATIONS['collection']}?read=false&page=1&page_size=10")
    assert unread.status_code == 200, unread.text
    assert unread.json()['total'] == 1

    mark_all = await authorized_client.post(NOTIFICATIONS['read_all'])
    assert mark_all.status_code == 200, mark_all.text
    assert mark_all.json()['updated'] == 1

    read_only = await authorized_client.get(f"{NOTIFICATIONS['collection']}?read=true&page=1&page_size=10")
    assert read_only.status_code == 200, read_only.text
    assert read_only.json()['total'] == 2


@pytest.mark.asyncio
async def test_notification_preferences_and_in_app_without_smtp(authorized_client):
    user_id, family_id = await _current_session(authorized_client)

    response = await authorized_client.get(NOTIFICATIONS['preferences'])
    assert response.status_code == 200, response.text
    preferences = {item['notification_type']: item for item in response.json()}
    assert preferences['due_date']['in_app_enabled'] is True
    assert preferences['due_date']['email_enabled'] is False

    update = await authorized_client.put(
        NOTIFICATIONS['preferences'],
        json={
            'preferences': [
                {'notification_type': 'due_date', 'in_app_enabled': True, 'email_enabled': True},
            ]
        },
    )
    assert update.status_code == 200, update.text

    original_host = settings.smtp_host
    original_from_email = settings.smtp_from_email
    settings.smtp_host = None
    settings.smtp_from_email = None
    try:
        async with AsyncSessionLocal() as db:
            notification = await create_notification(
                db,
                user_id,
                NotificationType.due_date,
                'Due soon: Science lab',
                'Science lab notebook is due this evening.',
                '/assignments',
                family_id=family_id,
            )
            await db.commit()
            assert notification is not None

            stored = (
                await db.execute(
                    select(Notification).where(
                        Notification.user_id == user_id,
                        Notification.family_id == family_id,
                        Notification.type == NotificationType.due_date,
                    )
                )
            ).scalars().all()
            assert len(stored) == 1
    finally:
        settings.smtp_host = original_host
        settings.smtp_from_email = original_from_email


@pytest.mark.asyncio
async def test_notification_email_delivery_respects_preferences(authorized_client):
    user_id, family_id = await _current_session(authorized_client)
    sent_messages: list[object] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):  # noqa: ANN001, ANN204
            self.host = host
            self.port = port
            self.timeout = timeout

        def ehlo(self):  # noqa: ANN201
            return 250, b'ok'

        def starttls(self):  # noqa: ANN201
            return 220, b'ready'

        def login(self, username, password):  # noqa: ANN001, ANN201
            return 235, f'{username}:{password}'.encode()

        def send_message(self, message):  # noqa: ANN001, ANN201
            sent_messages.append(message)

        def quit(self):  # noqa: ANN201
            return 221, b'bye'

    smtp_originals = (
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_from_email,
        settings.smtp_use_tls,
        settings.smtp_username,
        settings.smtp_password,
    )
    settings.smtp_host = 'smtp.example.test'
    settings.smtp_port = 587
    settings.smtp_from_email = 'notifications@example.test'
    settings.smtp_use_tls = True
    settings.smtp_username = 'mailer'
    settings.smtp_password = 'secret'

    smtp_original = smtplib.SMTP
    smtplib.SMTP = FakeSMTP
    try:
        async with AsyncSessionLocal() as db:
            await update_notification_preferences(
                db,
                user_id,
                [(NotificationType.invitation, True, True)],
            )
            await create_notification(
                db,
                user_id,
                NotificationType.invitation,
                'Invitation accepted',
                'A new family member joined the workspace.',
                '/invitations',
                family_id=family_id,
            )
            await db.commit()

        assert len(sent_messages) == 1
        assert sent_messages[0]['To']
        assert 'Invitation accepted' in sent_messages[0]['Subject']

        async with AsyncSessionLocal() as db:
            await update_notification_preferences(
                db,
                user_id,
                [(NotificationType.invitation, True, False)],
            )
            await create_notification(
                db,
                user_id,
                NotificationType.invitation,
                'Invitation reminder',
                'Reminder that a family invitation is still pending.',
                '/invitations',
                family_id=family_id,
            )
            await db.commit()

            notifications = (
                await db.execute(
                    select(Notification).where(
                        Notification.user_id == user_id,
                        Notification.family_id == family_id,
                        Notification.type == NotificationType.invitation,
                    )
                )
            ).scalars().all()
            assert len(notifications) == 2

        assert len(sent_messages) == 1
    finally:
        smtplib.SMTP = smtp_original
        (
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_from_email,
            settings.smtp_use_tls,
            settings.smtp_username,
            settings.smtp_password,
        ) = smtp_originals


@pytest.mark.asyncio
async def test_background_checks_generate_due_date_and_backup_notifications(authorized_client):
    user_id, family_id = await _current_session(authorized_client)

    subject_response = await authorized_client.post(SUBJECTS['collection'], json=subject_payload(name='Science'))
    assert subject_response.status_code in {200, 201}, subject_response.text
    subject_id = subject_response.json()['id']

    backup_dir = Path(__file__).resolve().parents[1] / '.pytest-state' / 'backup-notifications'
    backup_dir.mkdir(parents=True, exist_ok=True)
    original_backup_target = settings.backup_target
    settings.backup_target = str(backup_dir)
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                Assignment(
                    family_id=family_id,
                    subject_id=subject_id,
                    title='Lab reflection',
                    due_date=datetime.now(UTC) + timedelta(hours=2),
                    status=AssignmentStatus.pending,
                )
            )
            await db.flush()
            await run_notification_maintenance(db)
            await db.commit()

            notifications = (
                await db.execute(
                    select(Notification.type, Notification.link).where(
                        Notification.user_id == user_id,
                        Notification.family_id == family_id,
                    )
                )
            ).all()

        payload = {(notification_type.value, link) for notification_type, link in notifications}
        assert ('due_date', '/assignments') in payload
        assert ('backup_status', '/settings/backups') in payload
    finally:
        settings.backup_target = original_backup_target


@pytest.mark.asyncio
async def test_login_lockout_creates_security_alert(create_family_user, secondary_client):
    user = await create_family_user(
        family_name='Security Family',
        email='security-parent@example.com',
        password='correct-password-123',
        display_name='Security Parent',
        role='parent',
        is_owner=True,
    )

    last_response = None
    for _ in range(settings.auth_lockout_threshold):
        last_response = await secondary_client.post(
            AUTH['login'],
            json={'email': user['email'], 'password': 'wrong-password'},
        )

    assert last_response is not None
    assert last_response.status_code in {401, 423}, last_response.text

    async with AsyncSessionLocal() as db:
        notifications = (
            await db.execute(
                select(Notification).where(
                    Notification.family_id == user['family_id'],
                    Notification.type == NotificationType.security_alert,
                )
            )
        ).scalars().all()

    assert notifications
    assert notifications[0].link == '/login'
