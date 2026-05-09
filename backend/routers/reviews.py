from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import (
    AuditAction,
    FamilyMembership,
    FamilyRole,
    GradedBy,
    GradingJobStatus,
    NotificationType,
    ReviewPriority,
    ReviewComment,
    ReviewItem,
    ReviewItemStatus,
    User,
)
from backend.schemas.reviews import (
    ReviewApproveRequest,
    ReviewAssignRequest,
    ReviewBulkApproveRequest,
    ReviewBulkAssignRequest,
    ReviewBulkResponse,
    ReviewCommentCreate,
    ReviewCommentRead,
    ReviewItemRead,
    ReviewReviewerRead,
    ReviewRejectRequest,
    ReviewRegradeRequest,
)
from backend.security import AuthSession
from backend.services.audit import log_event
from backend.services.authorization import Capability, require_capabilities
from backend.services.notifications import create_family_notifications, create_notification
from backend.services.reviews import (
    OPEN_REVIEW_STATUSES,
    REVIEWER_ROLES,
    clear_grade_for_review,
    ensure_review_access,
    get_review_item,
    mark_assignment_target_graded,
    review_item_query,
    resolve_reviewer,
    reset_job_for_regrade,
    serialize_review_comment,
    serialize_review_item,
    sync_review_item_for_job,
    upsert_grade_for_review,
)

router = APIRouter(prefix='/reviews', tags=['reviews'])


def _review_snapshot(item: ReviewItem) -> dict[str, object | None]:
    return {
        'id': item.id,
        'status': item.status.value,
        'priority': item.priority.value,
        'assigned_to_user_id': item.assigned_to_user_id,
        'reviewed_by_user_id': item.reviewed_by_user_id,
        'ai_suggested_grade': item.ai_suggested_grade,
        'ai_confidence': item.ai_confidence,
        'reviewer_notes': item.reviewer_notes,
        'reviewed_at': item.reviewed_at.isoformat() if item.reviewed_at else None,
    }


async def _load_item(review_id: int, family_id: int, db: AsyncSession) -> ReviewItem:
    item = await get_review_item(db, review_id, family_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review item not found')
    return item


async def _notify_review_status(
    db: AsyncSession,
    *,
    item: ReviewItem,
    title: str,
    message: str,
    roles: set[FamilyRole] | None = None,
    assignee_only: bool = False,
) -> None:
    link = f'/review/{item.id}'
    if assignee_only and item.assigned_to_user_id:
        await create_notification(
            db,
            item.assigned_to_user_id,
            NotificationType.grading_complete,
            title,
            message,
            link,
            family_id=item.family_id,
            suppress_duplicates_for=timedelta(minutes=5),
        )
        return
    await create_family_notifications(
        db,
        family_id=item.family_id,
        notification_type=NotificationType.grading_complete,
        title=title,
        message=message,
        link=link,
        roles=roles or REVIEWER_ROLES,
        suppress_duplicates_for=timedelta(minutes=5),
    )


async def _approve_item(
    item: ReviewItem,
    payload: ReviewApproveRequest,
    *,
    auth: AuthSession,
    request: Request,
    db: AsyncSession,
) -> ReviewItem:
    await ensure_review_access(item, auth)
    if item.status not in OPEN_REVIEW_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Review item is already resolved')
    job = item.grading_job
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grading job not found')

    before = _review_snapshot(item)
    score = payload.score if payload.score is not None else float(item.ai_suggested_grade or job.ai_grade or 0.0)
    grade = await upsert_grade_for_review(
        db,
        job=job,
        score=score,
        feedback=payload.feedback or payload.notes,
        graded_by=GradedBy.ai_human if payload.score is None and not payload.override_reason else GradedBy.human,
    )
    if item.submission is not None:
        await mark_assignment_target_graded(
            db,
            assignment_id=item.submission.assignment_id,
            student_id=item.submission.student_id,
        )
    if job.status == GradingJobStatus.review_needed:
        from backend.services.grading_pipeline import transition_job

        transition_job(job, GradingJobStatus.reviewed, detail='Review approved', payload={'review_item_id': item.id})
        transition_job(job, GradingJobStatus.final, detail='Review finalized', payload={'grade_id': grade.id, 'score': score})
    job.human_override_details = {
        'reviewed_at': datetime.now(UTC).isoformat(),
        'reviewed_by_user_id': auth.user_id,
        'action': 'approve',
        'override_reason': payload.override_reason,
        'notes': payload.notes,
        'feedback': payload.feedback,
        'final_score': score,
        'ai_score': job.ai_grade,
    }
    job.error_message = None
    job.completed_at = datetime.now(UTC)

    item.status = ReviewItemStatus.approved
    item.reviewed_by_user_id = auth.user_id
    item.reviewed_at = datetime.now(UTC)
    item.reviewer_notes = payload.notes or payload.override_reason or payload.feedback or item.reviewer_notes
    await sync_review_item_for_job(db, job)
    await log_event(
        db,
        action=AuditAction.grade_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='review_item',
        target_id=item.id,
        before=before,
        after=_review_snapshot(item),
        request=request,
    )
    await _notify_review_status(
        db,
        item=item,
        title=f'Review completed: {item.submission.assignment.title if item.submission and item.submission.assignment else "Submission"}',
        message=f'{auth.display_name} approved a review for {item.submission.student.name if item.submission and item.submission.student else "the student"}.',
    )
    return item


@router.get('', response_model=list[ReviewItemRead])
async def list_reviews(
    status_filter: ReviewItemStatus | None = Query(default=None, alias='status'),
    priority: ReviewPriority | None = Query(default=None),
    student_id: int | None = Query(default=None, gt=0),
    subject_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review submissions')),
) -> list[ReviewItemRead]:
    stmt = review_item_query().where(ReviewItem.family_id == auth.family_id)
    if status_filter is not None:
        stmt = stmt.where(ReviewItem.status == status_filter)
    if priority is not None:
        stmt = stmt.where(ReviewItem.priority == priority)
    items = (await db.execute(stmt)).scalars().all()

    filtered: list[ReviewItem] = []
    for item in items:
        submission = item.submission
        assignment = submission.assignment if submission else None
        if student_id is not None and (submission is None or submission.student_id != student_id):
            continue
        if subject_id is not None and (assignment is None or assignment.subject_id != subject_id):
            continue
        await ensure_review_access(item, auth)
        filtered.append(item)

    priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
    filtered.sort(
        key=lambda item: (
            priority_order.get(item.priority.value, 99),
            item.reviewed_at is not None,
            item.created_at,
            item.id,
        )
    )
    return [serialize_review_item(item) for item in filtered]


@router.get('/reviewers', response_model=list[ReviewReviewerRead])
async def list_reviewers(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='assign reviews')),
) -> list[ReviewReviewerRead]:
    rows = (
        await db.execute(
            select(FamilyMembership, User)
            .join(User, User.id == FamilyMembership.user_id)
            .where(
                FamilyMembership.family_id == auth.family_id,
                FamilyMembership.accepted_at.is_not(None),
                User.is_active.is_(True),
            )
            .order_by(User.display_name.asc(), User.id.asc())
        )
    ).all()
    return [
        ReviewReviewerRead(
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            role=membership.role.value,
        )
        for membership, user in rows
        if membership.role in REVIEWER_ROLES
    ]


@router.get('/{review_id:int}', response_model=ReviewItemRead)
async def get_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review submissions')),
) -> ReviewItemRead:
    item = await _load_item(review_id, auth.family_id, db)
    await ensure_review_access(item, auth)
    if item.status == ReviewItemStatus.pending_review:
        item.status = ReviewItemStatus.in_review
        await db.commit()
        await db.refresh(item)
    return serialize_review_item(item, include_comments=True)


@router.post('/{review_id:int}/comments', response_model=ReviewCommentRead, status_code=status.HTTP_201_CREATED)
async def add_review_comment(
    review_id: int,
    payload: ReviewCommentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='comment on reviews')),
) -> ReviewCommentRead:
    item = await _load_item(review_id, auth.family_id, db)
    await ensure_review_access(item, auth)
    before = _review_snapshot(item)
    comment = ReviewComment(
        family_id=auth.family_id,
        review_item_id=item.id,
        author_user_id=auth.user_id,
        body=payload.body.strip(),
    )
    db.add(comment)
    if item.status == ReviewItemStatus.pending_review:
        item.status = ReviewItemStatus.in_review
    await log_event(
        db,
        action=AuditAction.grade_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='review_item',
        target_id=item.id,
        before=before,
        after=_review_snapshot(item),
        request=request,
    )
    await _notify_review_status(
        db,
        item=item,
        title='Review comment added',
        message=f'{auth.display_name} added a note to a review item.',
        assignee_only=bool(item.assigned_to_user_id and item.assigned_to_user_id != auth.user_id),
    )
    await db.commit()
    await db.refresh(comment)
    return serialize_review_comment(comment)


@router.post('/{review_id:int}/approve', response_model=ReviewItemRead)
async def approve_review(
    review_id: int,
    payload: ReviewApproveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='approve reviews')),
) -> ReviewItemRead:
    item = await _load_item(review_id, auth.family_id, db)
    await _approve_item(item, payload, auth=auth, request=request, db=db)
    await db.commit()
    await db.refresh(item)
    return serialize_review_item(item, include_comments=True)


@router.post('/{review_id:int}/reject', response_model=ReviewItemRead)
async def reject_review(
    review_id: int,
    payload: ReviewRejectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='reject reviews')),
) -> ReviewItemRead:
    item = await _load_item(review_id, auth.family_id, db)
    await ensure_review_access(item, auth)
    if item.status not in OPEN_REVIEW_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Review item is already resolved')
    job = item.grading_job
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grading job not found')

    before = _review_snapshot(item)
    from backend.services.grading_pipeline import transition_job

    if job.status == GradingJobStatus.review_needed:
        transition_job(job, GradingJobStatus.reviewed, detail='Review rejected', payload={'review_item_id': item.id})
        transition_job(job, GradingJobStatus.final, detail='Resubmission requested', payload={'review_item_id': item.id})
    job.human_override_details = {
        'reviewed_at': datetime.now(UTC).isoformat(),
        'reviewed_by_user_id': auth.user_id,
        'action': 'reject',
        'notes': payload.notes,
        'reason': payload.reason,
    }
    job.manual_review_reason = payload.reason or 'Reviewer requested a resubmission.'
    job.error_message = job.manual_review_reason
    job.completed_at = datetime.now(UTC)

    await clear_grade_for_review(db, family_id=item.family_id, submission_id=item.submission_id)
    item.status = ReviewItemStatus.rejected
    item.reviewed_by_user_id = auth.user_id
    item.reviewed_at = datetime.now(UTC)
    item.reviewer_notes = payload.notes or payload.reason or item.reviewer_notes
    await log_event(
        db,
        action=AuditAction.grade_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='review_item',
        target_id=item.id,
        before=before,
        after=_review_snapshot(item),
        request=request,
    )
    await _notify_review_status(
        db,
        item=item,
        title='Resubmission requested',
        message=f'{auth.display_name} rejected a grading review and requested a resubmission.',
    )
    await db.commit()
    await db.refresh(item)
    return serialize_review_item(item, include_comments=True)


@router.post('/{review_id:int}/regrade', response_model=ReviewItemRead)
async def regrade_review(
    review_id: int,
    payload: ReviewRegradeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='request re-grades')),
) -> ReviewItemRead:
    item = await _load_item(review_id, auth.family_id, db)
    await ensure_review_access(item, auth)
    job = item.grading_job
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Grading job not found')

    before = _review_snapshot(item)
    await reset_job_for_regrade(job, reason=payload.reason)
    item.status = ReviewItemStatus.needs_regrade
    item.reviewed_by_user_id = None
    item.reviewed_at = None
    item.reviewer_notes = payload.reason or item.reviewer_notes
    await sync_review_item_for_job(db, job)
    await log_event(
        db,
        action=AuditAction.grade_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='review_item',
        target_id=item.id,
        before=before,
        after=_review_snapshot(item),
        request=request,
    )
    await _notify_review_status(
        db,
        item=item,
        title='Re-grade requested',
        message=f'{auth.display_name} requested a re-grade for a review item.',
    )
    await db.commit()
    await db.refresh(item)
    return serialize_review_item(item, include_comments=True)


@router.post('/{review_id:int}/assign', response_model=ReviewItemRead)
async def assign_review(
    review_id: int,
    payload: ReviewAssignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='assign reviews')),
) -> ReviewItemRead:
    item = await _load_item(review_id, auth.family_id, db)
    await ensure_review_access(item, auth)
    reviewer, _ = await resolve_reviewer(db, family_id=auth.family_id, assigned_to_user_id=payload.assigned_to_user_id)
    before = _review_snapshot(item)
    item.assigned_to_user_id = reviewer.id
    if item.status == ReviewItemStatus.pending_review:
        item.status = ReviewItemStatus.in_review
    await log_event(
        db,
        action=AuditAction.grade_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='review_item',
        target_id=item.id,
        before=before,
        after=_review_snapshot(item),
        request=request,
    )
    await _notify_review_status(
        db,
        item=item,
        title='Review assigned',
        message=f'{auth.display_name} assigned this review to {reviewer.display_name}.',
        assignee_only=True,
    )
    await db.commit()
    await db.refresh(item)
    return serialize_review_item(item, include_comments=True)


@router.post('/bulk/approve', response_model=ReviewBulkResponse)
async def bulk_approve_reviews(
    payload: ReviewBulkApproveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='bulk approve reviews')),
) -> ReviewBulkResponse:
    items: list[ReviewItem] = []
    for review_id in dict.fromkeys(payload.review_ids):
        item = await _load_item(review_id, auth.family_id, db)
        items.append(
            await _approve_item(
                item,
                ReviewApproveRequest(notes=payload.notes, override_reason=payload.override_reason),
                auth=auth,
                request=request,
                db=db,
            )
        )
    await db.commit()
    for item in items:
        await db.refresh(item)
    return ReviewBulkResponse(updated=len(items), items=[serialize_review_item(item) for item in items])


@router.post('/bulk/assign', response_model=ReviewBulkResponse)
async def bulk_assign_reviews(
    payload: ReviewBulkAssignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='bulk assign reviews')),
) -> ReviewBulkResponse:
    reviewer, _ = await resolve_reviewer(db, family_id=auth.family_id, assigned_to_user_id=payload.assigned_to_user_id)
    items: list[ReviewItem] = []
    for review_id in dict.fromkeys(payload.review_ids):
        item = await _load_item(review_id, auth.family_id, db)
        await ensure_review_access(item, auth)
        before = _review_snapshot(item)
        item.assigned_to_user_id = reviewer.id
        if item.status == ReviewItemStatus.pending_review:
            item.status = ReviewItemStatus.in_review
        await log_event(
            db,
            action=AuditAction.grade_update,
            actor=auth,
            family_id=auth.family_id,
            target_type='review_item',
            target_id=item.id,
            before=before,
            after=_review_snapshot(item),
            request=request,
        )
        items.append(item)
    await db.commit()
    for item in items:
        await db.refresh(item)
    return ReviewBulkResponse(updated=len(items), items=[serialize_review_item(item) for item in items])
