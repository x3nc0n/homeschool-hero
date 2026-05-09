from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import AuditEvent, GradingJob, Submission, User
from backend.security import AuthSession, get_auth_session
from backend.services.authorization import Capability, get_student_scope_id, has_capability
from backend.services.monitoring import collect_metrics_payload

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


@router.get('/summary')
async def dashboard_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> dict[str, object]:
    items: list[dict[str, object]] = []

    if has_capability(auth, Capability.manage_family):
        audit_rows = (
            await db.execute(
                select(AuditEvent, User.display_name)
                .join(User, User.id == AuditEvent.actor_user_id)
                .where(AuditEvent.family_id == auth.family_id)
                .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
                .limit(6)
            )
        ).all()
        for event, actor_display_name in audit_rows:
            items.append(
                {
                    'id': f'audit-{event.id}',
                    'type': 'audit',
                    'timestamp': event.timestamp,
                    'title': event.action.value.replace('_', ' ').title(),
                    'subtitle': actor_display_name or f'User {event.actor_user_id}',
                    'status': 'ok',
                    'details': {
                        'action': event.action.value,
                        'entity_type': event.target_entity_type,
                        'entity_id': event.target_entity_id,
                    },
                }
            )

    job_stmt = (
        select(GradingJob)
        .options(
            selectinload(GradingJob.submission).selectinload(Submission.assignment),
            selectinload(GradingJob.submission).selectinload(Submission.student),
        )
        .where(GradingJob.family_id == auth.family_id)
        .order_by(GradingJob.created_at.desc(), GradingJob.id.desc())
        .limit(6)
    )
    if auth.role == 'student_viewer':
        job_stmt = job_stmt.join(Submission, Submission.id == GradingJob.submission_id).where(
            Submission.student_id == get_student_scope_id(auth)
        )

    jobs = (await db.execute(job_stmt)).scalars().all()
    for job in jobs:
        submission = job.submission
        duration_ms = None
        if job.completed_at is not None:
            duration_ms = round((job.completed_at - job.created_at).total_seconds() * 1000, 2)
        items.append(
            {
                'id': f'grading-{job.id}',
                'type': 'grading_job',
                'timestamp': job.completed_at or job.created_at,
                'title': f"Grading job {job.status.value.replace('_', ' ')}",
                'subtitle': submission.assignment.title if submission and submission.assignment else 'Submission',
                'status': job.status.value,
                'details': {
                    'job_id': job.id,
                    'student_name': submission.student.name if submission and submission.student else None,
                    'submission_id': job.submission_id,
                    'duration_ms': duration_ms,
                    'error_message': job.error_message,
                },
            }
        )

    items.sort(key=lambda item: item.get('timestamp') or datetime.min.replace(tzinfo=UTC), reverse=True)
    metrics = await collect_metrics_payload(request.app, db)
    backup_last_success = metrics.get('backup_last_success')
    health_summary = {
        'status': 'degraded' if metrics['slow_requests_total'] or metrics['grading_jobs_by_status'].get('failed', 0) else 'ok',
        'requests_total': metrics['requests_total'],
        'slow_requests_total': metrics['slow_requests_total'],
        'grading_jobs_by_status': metrics['grading_jobs_by_status'],
        'active_users': metrics['active_users'],
        'backup_last_success': backup_last_success,
        'metrics_enabled': metrics['enabled'],
        'generated_at': datetime.now(UTC).isoformat(),
    }
    return {
        'recent_activity': items[:8],
        'system_health': health_summary,
    }
