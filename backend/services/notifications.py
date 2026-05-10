from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import (
    Assignment,
    AssignmentStatus,
    AssignmentTarget,
    AssignmentTargetStatus,
    FamilyMembership,
    FamilyRole,
    Notification,
    NotificationPreference,
    NotificationType,
    Student,
    Subject,
    User,
)
from backend.services.email_service import email_enabled, send_email
from backend.services.monitoring import get_backup_last_success

logger = logging.getLogger(__name__)

DEFAULT_NOTIFICATION_PREFERENCES: dict[NotificationType, dict[str, bool]] = {
    notification_type: {'in_app_enabled': True, 'email_enabled': False}
    for notification_type in NotificationType
}
FAMILY_MANAGER_ROLES = {FamilyRole.parent, FamilyRole.co_parent}
GRADING_NOTIFICATION_ROLES = {FamilyRole.parent, FamilyRole.co_parent, FamilyRole.tutor}
DUE_SOON_WINDOW = timedelta(hours=24)
BACKUP_STALE_AFTER = timedelta(hours=48)

EMAIL_TEMPLATE_CONFIG: dict[NotificationType, dict[str, str]] = {
    NotificationType.due_date: {'headline': 'Assignment due soon', 'cta': 'Open assignments'},
    NotificationType.grading_complete: {'headline': 'Grading update', 'cta': 'Open grades'},
    NotificationType.backup_status: {'headline': 'Backup attention needed', 'cta': 'Open backup settings'},
    NotificationType.security_alert: {'headline': 'Security alert', 'cta': 'Review sign-in activity'},
    NotificationType.invitation: {'headline': 'Invitation update', 'cta': 'Open invitations'},
    NotificationType.compliance_reminder: {'headline': 'Compliance reminder', 'cta': 'Open dashboard'},
}


def _default_preference(notification_type: NotificationType) -> NotificationPreference:
    defaults = DEFAULT_NOTIFICATION_PREFERENCES[notification_type]
    return NotificationPreference(
        user_id=0,
        notification_type=notification_type,
        in_app_enabled=defaults['in_app_enabled'],
        email_enabled=defaults['email_enabled'],
    )


async def get_notification_preferences(db: AsyncSession, user_id: int) -> list[NotificationPreference]:
    rows = (
        await db.execute(
            select(NotificationPreference)
            .where(NotificationPreference.user_id == user_id)
            .order_by(NotificationPreference.notification_type)
        )
    ).scalars().all()
    by_type = {row.notification_type: row for row in rows}
    return [by_type.get(notification_type, _default_preference(notification_type)) for notification_type in NotificationType]


async def update_notification_preferences(
    db: AsyncSession,
    user_id: int,
    preferences: list[tuple[NotificationType, bool, bool]],
) -> list[NotificationPreference]:
    if not preferences:
        return await get_notification_preferences(db, user_id)

    existing = (
        await db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    ).scalars().all()
    by_type = {row.notification_type: row for row in existing}

    for notification_type, in_app_enabled, email_enabled in preferences:
        row = by_type.get(notification_type)
        if row is None:
            row = NotificationPreference(
                user_id=user_id,
                notification_type=notification_type,
                in_app_enabled=in_app_enabled,
                email_enabled=email_enabled,
            )
            db.add(row)
            by_type[notification_type] = row
            continue
        row.in_app_enabled = in_app_enabled
        row.email_enabled = email_enabled

    await db.flush()
    return await get_notification_preferences(db, user_id)


async def _get_effective_preference(db: AsyncSession, user_id: int, notification_type: NotificationType) -> NotificationPreference:
    row = (
        await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
        )
    ).scalar_one_or_none()
    return row or _default_preference(notification_type)


async def _resolve_family_id(db: AsyncSession, user_id: int) -> int | None:
    return (
        await db.execute(
            select(FamilyMembership.family_id)
            .where(FamilyMembership.user_id == user_id, FamilyMembership.accepted_at.is_not(None))
            .order_by(FamilyMembership.family_id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def _notification_exists(
    db: AsyncSession,
    *,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    link: str | None,
    family_id: int,
    since: datetime,
) -> bool:
    existing = (
        await db.execute(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.family_id == family_id,
                Notification.type == notification_type,
                Notification.title == title,
                Notification.link == link,
                Notification.created_at >= since,
            )
        )
    ).scalar_one_or_none()
    return existing is not None


def render_email_template(
    notification_type: NotificationType,
    *,
    title: str,
    message: str,
    link: str | None,
) -> tuple[str, str]:
    template = EMAIL_TEMPLATE_CONFIG.get(notification_type, EMAIL_TEMPLATE_CONFIG[NotificationType.compliance_reminder])
    safe_title = escape(title)
    safe_message = escape(message).replace('\n', '<br />')
    safe_link = escape(link or '/')
    subject = f'Homeschool Hero: {title}'
    html = (
        '<html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:24px;">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;'
        'border-radius:12px;padding:24px;">'
        f'<p style="margin:0 0 8px;color:#64748b;font-size:12px;text-transform:uppercase;">{escape(template["headline"])}</p>'
        f'<h1 style="margin:0 0 12px;font-size:20px;color:#0f172a;">{safe_title}</h1>'
        f'<p style="margin:0 0 20px;color:#334155;line-height:1.6;">{safe_message}</p>'
        f'<p style="margin:0;"><a href="{safe_link}" '
        'style="display:inline-block;background:#2563eb;color:#ffffff;padding:10px 16px;'
        'border-radius:8px;text-decoration:none;font-weight:600;">'
        f'{escape(template["cta"])}</a></p>'
        '</div></body></html>'
    )
    return subject, html


async def create_notification(
    db: AsyncSession,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    message: str,
    link: str | None = None,
    *,
    family_id: int | None = None,
    suppress_duplicates_for: timedelta = timedelta(hours=20),
) -> Notification | None:
    resolved_family_id = family_id or await _resolve_family_id(db, user_id)
    if resolved_family_id is None:
        return None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None

    if await _notification_exists(
        db,
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        link=link,
        family_id=resolved_family_id,
        since=datetime.now(UTC) - suppress_duplicates_for,
    ):
        return None

    preference = await _get_effective_preference(db, user_id, notification_type)
    notification: Notification | None = None
    if preference.in_app_enabled:
        notification = Notification(
            family_id=resolved_family_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            link=link,
        )
        db.add(notification)
        await db.flush()

    if preference.email_enabled and email_enabled():
        try:
            subject, html = render_email_template(notification_type, title=title, message=message, link=link)
            send_email(to_email=user.email, subject=subject, html=html)
        except Exception:
            logger.exception('Failed to send notification email', extra={'user_id': user_id, 'type': notification_type.value})

    return notification


async def _family_recipients(
    db: AsyncSession,
    *,
    family_id: int,
    roles: set[FamilyRole] | None = None,
    student_id: int | None = None,
) -> list[int]:
    rows = (
        await db.execute(
            select(FamilyMembership.user_id, FamilyMembership.role, FamilyMembership.student_id)
            .join(User, User.id == FamilyMembership.user_id)
            .where(
                FamilyMembership.family_id == family_id,
                FamilyMembership.accepted_at.is_not(None),
                User.is_active.is_(True),
            )
            .order_by(FamilyMembership.user_id)
        )
    ).all()

    recipients: list[int] = []
    for user_id, role, scoped_student_id in rows:
        if roles and role not in roles:
            continue
        if student_id is not None and role == FamilyRole.student_viewer and scoped_student_id != student_id:
            continue
        recipients.append(int(user_id))
    return recipients


async def create_family_notifications(
    db: AsyncSession,
    *,
    family_id: int,
    notification_type: NotificationType,
    title: str,
    message: str,
    link: str | None = None,
    roles: set[FamilyRole] | None = None,
    student_id: int | None = None,
    suppress_duplicates_for: timedelta = timedelta(hours=20),
) -> list[Notification]:
    created: list[Notification] = []
    for user_id in await _family_recipients(db, family_id=family_id, roles=roles, student_id=student_id):
        notification = await create_notification(
            db,
            user_id,
            notification_type,
            title,
            message,
            link,
            family_id=family_id,
            suppress_duplicates_for=suppress_duplicates_for,
        )
        if notification is not None:
            created.append(notification)
    return created


async def create_security_alert_for_user(
    db: AsyncSession,
    *,
    user_id: int,
    title: str,
    message: str,
    link: str = '/login',
) -> None:
    memberships = (
        await db.execute(
            select(FamilyMembership.family_id, FamilyMembership.role)
            .where(FamilyMembership.user_id == user_id, FamilyMembership.accepted_at.is_not(None))
        )
    ).all()
    for family_id, role in memberships:
        await create_family_notifications(
            db,
            family_id=family_id,
            notification_type=NotificationType.security_alert,
            title=title,
            message=message,
            link=link,
            roles=FAMILY_MANAGER_ROLES,
            suppress_duplicates_for=timedelta(hours=1),
        )
        if role not in FAMILY_MANAGER_ROLES:
            await create_notification(
                db,
                user_id,
                NotificationType.security_alert,
                title,
                message,
                link,
                family_id=family_id,
                suppress_duplicates_for=timedelta(hours=1),
            )


async def create_grading_complete_notifications(
    db: AsyncSession,
    *,
    family_id: int,
    assignment_title: str,
    student_name: str,
    score: float | None,
    max_score: float | None,
    needs_review: bool = False,
) -> None:
    if needs_review:
        title = f'Grading ready for review: {assignment_title}'
        message = f'{student_name} needs a quick grading review before the score is finalized.'
        link = '/review'
    else:
        score_text = (
            f'{round(score, 2):g}/{round(max_score, 2):g}' if score is not None and max_score is not None else 'a new score'
        )
        title = f'Grading complete: {assignment_title}'
        message = f'{student_name} has {score_text} ready in the grade book.'
        link = '/grades'

    await create_family_notifications(
        db,
        family_id=family_id,
        notification_type=NotificationType.grading_complete,
        title=title,
        message=message,
        link=link,
        roles=GRADING_NOTIFICATION_ROLES,
        suppress_duplicates_for=timedelta(minutes=30),
    )


async def create_due_date_notifications(db: AsyncSession) -> None:
    now = datetime.now(UTC)
    window_end = now + DUE_SOON_WINDOW

    targeted_rows = (
        await db.execute(
            select(
                Assignment.family_id,
                AssignmentTarget.student_id,
                func.coalesce(AssignmentTarget.due_date, Assignment.due_date),
                Assignment.title,
                Student.name,
                Subject.name,
            )
            .join(Assignment, Assignment.id == AssignmentTarget.assignment_id)
            .join(Student, Student.id == AssignmentTarget.student_id)
            .join(Subject, Subject.id == Assignment.subject_id)
            .where(
                AssignmentTarget.status.in_((AssignmentTargetStatus.assigned, AssignmentTargetStatus.submitted)),
                func.coalesce(AssignmentTarget.due_date, Assignment.due_date).is_not(None),
                func.coalesce(AssignmentTarget.due_date, Assignment.due_date) <= window_end,
                func.coalesce(AssignmentTarget.due_date, Assignment.due_date) >= now - timedelta(hours=12),
            )
            .order_by(func.coalesce(AssignmentTarget.due_date, Assignment.due_date).asc())
        )
    ).all()

    for family_id, student_id, due_date, assignment_title, student_name, subject_name in targeted_rows:
        due_label = due_date.astimezone(UTC).strftime('%b %d at %I:%M %p UTC')
        await create_family_notifications(
            db,
            family_id=family_id,
            notification_type=NotificationType.due_date,
            title=f'Due soon: {assignment_title}',
            message=f'{student_name} has {subject_name} due {due_label}.',
            link='/assignments',
            student_id=student_id,
            suppress_duplicates_for=timedelta(hours=18),
        )

    untargeted_rows = (
        await db.execute(
            select(Assignment.family_id, Assignment.title, Assignment.due_date, Subject.name)
            .join(Subject, Subject.id == Assignment.subject_id)
            .where(
                Assignment.status == AssignmentStatus.pending,
                Assignment.due_date.is_not(None),
                Assignment.due_date <= window_end,
                Assignment.due_date >= now - timedelta(hours=12),
                ~select(AssignmentTarget.id).where(AssignmentTarget.assignment_id == Assignment.id).exists(),
            )
            .order_by(Assignment.due_date.asc())
        )
    ).all()

    for family_id, assignment_title, due_date, subject_name in untargeted_rows:
        due_label = due_date.astimezone(UTC).strftime('%b %d at %I:%M %p UTC')
        await create_family_notifications(
            db,
            family_id=family_id,
            notification_type=NotificationType.due_date,
            title=f'Due soon: {assignment_title}',
            message=f'{subject_name} is due {due_label}.',
            link='/assignments',
            roles=GRADING_NOTIFICATION_ROLES,
            suppress_duplicates_for=timedelta(hours=18),
        )


async def create_backup_status_notifications(db: AsyncSession) -> None:
    if not settings.backup_target:
        return

    backup_last_success = get_backup_last_success()
    if backup_last_success is None:
        message = 'No successful backup has been recorded yet. Verify the backup target and run a backup.'
    else:
        age_seconds = int(backup_last_success.get('age_seconds') or 0)
        if age_seconds <= int(BACKUP_STALE_AFTER.total_seconds()):
            return
        age_hours = round(age_seconds / 3600)
        message = f'The last successful backup was {age_hours} hours ago. Check your backup target and rerun the backup job.'

    family_ids = (
        await db.execute(
            select(FamilyMembership.family_id)
            .where(
                FamilyMembership.accepted_at.is_not(None),
                FamilyMembership.role.in_(tuple(FAMILY_MANAGER_ROLES)),
            )
            .group_by(FamilyMembership.family_id)
        )
    ).scalars().all()

    for family_id in family_ids:
        await create_family_notifications(
            db,
            family_id=family_id,
            notification_type=NotificationType.backup_status,
            title='Backup attention required',
            message=message,
            link='/settings/backups',
            roles=FAMILY_MANAGER_ROLES,
            suppress_duplicates_for=timedelta(hours=24),
        )


async def run_notification_maintenance(db: AsyncSession) -> None:
    await create_due_date_notifications(db)
    await create_backup_status_notifications(db)


async def get_unread_count(db: AsyncSession, *, user_id: int, family_id: int) -> int:
    unread_count = (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.family_id == family_id,
                Notification.read.is_(False),
            )
        )
    ).scalar_one()
    return int(unread_count or 0)
