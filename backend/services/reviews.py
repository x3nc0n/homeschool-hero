from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    AssignmentTarget,
    AssignmentTargetStatus,
    FamilyMembership,
    FamilyRole,
    Grade,
    GradedBy,
    GradingJob,
    GradingJobStatus,
    ReviewComment,
    ReviewItem,
    ReviewItemStatus,
    ReviewPriority,
    Submission,
    User,
)
from backend.security import AuthSession
from backend.services.authorization import ensure_student_scope
from backend.services.grading_pipeline import transition_job

REVIEWER_ROLES = {FamilyRole.parent, FamilyRole.co_parent, FamilyRole.tutor}
OPEN_REVIEW_STATUSES = {
    ReviewItemStatus.pending_review,
    ReviewItemStatus.in_review,
    ReviewItemStatus.needs_regrade,
}
REVIEW_REOPEN_STATUSES = {
    ReviewItemStatus.approved,
    ReviewItemStatus.rejected,
    ReviewItemStatus.needs_regrade,
}


def _to_letter_grade(score: float) -> str:
    if score >= 90:
        return 'A'
    if score >= 80:
        return 'B'
    if score >= 70:
        return 'C'
    if score >= 60:
        return 'D'
    return 'F'


def _priority_for_job(job: GradingJob) -> ReviewPriority:
    confidence = float(job.ai_confidence or 0.0)
    reason = (job.manual_review_reason or '').lower()
    if any(term in reason for term in ('flag', 'failed', 'unavailable', 'timeout', 'error')):
        return ReviewPriority.urgent
    if confidence < 0.35:
        return ReviewPriority.urgent
    if confidence < 0.55:
        return ReviewPriority.high
    if confidence < 0.75:
        return ReviewPriority.medium
    return ReviewPriority.low


def review_item_query() -> Select[tuple[ReviewItem]]:
    return select(ReviewItem).options(
        selectinload(ReviewItem.submission).selectinload(Submission.assignment),
        selectinload(ReviewItem.submission).selectinload(Submission.student),
        selectinload(ReviewItem.grading_job),
        selectinload(ReviewItem.assignee),
        selectinload(ReviewItem.reviewer),
        selectinload(ReviewItem.comments).selectinload(ReviewComment.author),
    )


async def get_review_item(db: AsyncSession, review_id: int, family_id: int) -> ReviewItem | None:
    return (
        await db.execute(
            review_item_query().where(
                ReviewItem.id == review_id,
                ReviewItem.family_id == family_id,
            )
        )
    ).scalar_one_or_none()


async def get_review_item_by_job_id(db: AsyncSession, grading_job_id: int, family_id: int) -> ReviewItem | None:
    return (
        await db.execute(
            review_item_query().where(
                ReviewItem.grading_job_id == grading_job_id,
                ReviewItem.family_id == family_id,
            )
        )
    ).scalar_one_or_none()


def serialize_review_comment(comment: ReviewComment) -> dict[str, Any]:
    return {
        'id': comment.id,
        'family_id': comment.family_id,
        'review_item_id': comment.review_item_id,
        'author_user_id': comment.author_user_id,
        'author_name': comment.author.display_name if comment.author else 'Reviewer',
        'body': comment.body,
        'created_at': comment.created_at,
        'updated_at': comment.updated_at,
    }


def serialize_review_item(item: ReviewItem, *, include_comments: bool = False) -> dict[str, Any]:
    submission = item.submission
    assignment = submission.assignment if submission else None
    subject = assignment.subject if assignment else None
    student = submission.student if submission else None
    job = item.grading_job
    return {
        'id': item.id,
        'family_id': item.family_id,
        'submission_id': item.submission_id,
        'grading_job_id': item.grading_job_id,
        'assignment_id': assignment.id if assignment else None,
        'assignment_title': assignment.title if assignment else None,
        'subject_id': subject.id if subject else None,
        'subject_name': subject.name if subject else None,
        'student_id': student.id if student else None,
        'student_name': student.name if student else None,
        'assigned_to_user_id': item.assigned_to_user_id,
        'assigned_to_name': item.assignee.display_name if item.assignee else None,
        'reviewed_by_user_id': item.reviewed_by_user_id,
        'reviewed_by_name': item.reviewer.display_name if item.reviewer else None,
        'status': item.status,
        'priority': item.priority,
        'ai_suggested_grade': item.ai_suggested_grade,
        'ai_confidence': item.ai_confidence,
        'reviewer_notes': item.reviewer_notes,
        'reviewed_at': item.reviewed_at,
        'created_at': item.created_at,
        'updated_at': item.updated_at,
        'submission_file_url': submission.file_url if submission else None,
        'submission_file_path': submission.file_path if submission else None,
        'submission_file_type': submission.file_type if submission else None,
        'submission_image_url': submission.file_url if submission else None,
        'ocr_text': job.ocr_result if job else (submission.ocr_text if submission else None),
        'ai_feedback': job.ai_feedback if job else None,
        'ai_response': job.ai_response if job else None,
        'manual_review_reason': job.manual_review_reason if job else None,
        'answer_key_result': job.answer_key_result if job else None,
        'status_history': list(job.status_history or []) if job else [],
        'comments': [serialize_review_comment(comment) for comment in item.comments] if include_comments else [],
    }


async def sync_review_item_for_job(db: AsyncSession, job: GradingJob) -> ReviewItem | None:
    existing = await get_review_item_by_job_id(db, job.id, job.family_id)
    if job.status == GradingJobStatus.review_needed:
        item = existing or ReviewItem(
            family_id=job.family_id,
            submission_id=job.submission_id,
            grading_job_id=job.id,
        )
        if existing is None:
            db.add(item)
        item.ai_suggested_grade = job.ai_grade
        item.ai_confidence = job.ai_confidence
        item.priority = _priority_for_job(job)
        if item.status in REVIEW_REOPEN_STATUSES:
            item.status = ReviewItemStatus.pending_review
            item.reviewed_at = None
            item.reviewed_by_user_id = None
        elif item.status not in OPEN_REVIEW_STATUSES:
            item.status = ReviewItemStatus.pending_review
        await db.flush()
        return item

    if existing is None:
        return None

    existing.ai_suggested_grade = job.ai_grade
    existing.ai_confidence = job.ai_confidence
    existing.priority = _priority_for_job(job)
    if job.status == GradingJobStatus.pending:
        existing.status = ReviewItemStatus.needs_regrade
        existing.reviewed_at = None
        existing.reviewed_by_user_id = None
    elif job.status == GradingJobStatus.final and existing.status == ReviewItemStatus.needs_regrade:
        existing.status = ReviewItemStatus.approved
        existing.reviewed_at = datetime.now(UTC)
    await db.flush()
    return existing


async def resolve_reviewer(
    db: AsyncSession,
    *,
    family_id: int,
    assigned_to_user_id: int,
) -> tuple[User, FamilyMembership]:
    row = (
        await db.execute(
            select(User, FamilyMembership)
            .join(FamilyMembership, FamilyMembership.user_id == User.id)
            .where(
                User.id == assigned_to_user_id,
                User.is_active.is_(True),
                FamilyMembership.family_id == family_id,
                FamilyMembership.accepted_at.is_not(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Reviewer not found')
    user, membership = row
    if membership.role not in REVIEWER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Reviewer role cannot be assigned review work')
    return user, membership


async def ensure_review_access(item: ReviewItem, auth: AuthSession) -> None:
    submission = item.submission
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    ensure_student_scope(auth, submission.student_id, action='review submission')


async def upsert_grade_for_review(
    db: AsyncSession,
    *,
    job: GradingJob,
    score: float,
    feedback: str | None,
    graded_by: GradedBy,
) -> Grade:
    existing = (
        await db.execute(select(Grade).where(Grade.family_id == job.family_id, Grade.submission_id == job.submission_id))
    ).scalar_one_or_none()
    submission = job.submission
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    if not submission.is_current:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Only the current submission version can be graded')

    max_score = float(
        job.answer_key_result.get('max_score')
        if job.answer_key_result
        else existing.max_score if existing else 100.0
    )
    notes = feedback or job.ai_feedback
    if existing is None:
        grade = Grade(
            family_id=job.family_id,
            submission_id=job.submission_id,
            student_id=submission.student_id,
            score=score,
            max_score=max_score,
            letter_grade=_to_letter_grade(score),
            notes=notes,
            graded_by=graded_by,
            ai_confidence=job.ai_confidence,
        )
        db.add(grade)
        await db.flush()
        return grade

    existing.score = score
    existing.max_score = max_score
    existing.letter_grade = _to_letter_grade(score)
    existing.notes = notes
    existing.graded_by = graded_by
    existing.ai_confidence = job.ai_confidence
    await db.flush()
    return existing


async def clear_grade_for_review(db: AsyncSession, *, family_id: int, submission_id: int) -> None:
    existing = (
        await db.execute(select(Grade).where(Grade.family_id == family_id, Grade.submission_id == submission_id))
    ).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.flush()


async def mark_assignment_target_graded(db: AsyncSession, *, assignment_id: int, student_id: int) -> None:
    target = (
        await db.execute(
            select(AssignmentTarget).where(
                AssignmentTarget.assignment_id == assignment_id,
                AssignmentTarget.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    if target is not None:
        target.status = AssignmentTargetStatus.graded
        await db.flush()


async def reset_job_for_regrade(job: GradingJob, *, reason: str | None) -> None:
    clear_reason = reason or 'Manual re-grade requested.'
    if job.status == GradingJobStatus.review_needed:
        transition_job(job, GradingJobStatus.pending, detail='Reviewer requested re-grade', payload={'reason': clear_reason})
    elif job.status == GradingJobStatus.final:
        transition_job(job, GradingJobStatus.pending, detail='Reviewer requested re-grade', payload={'reason': clear_reason})
    else:
        job.status = GradingJobStatus.pending
    job.ocr_result = None
    job.ai_grade = None
    job.ai_feedback = None
    job.ai_confidence = None
    job.ai_response = None
    job.answer_key_result = None
    job.human_override_details = None
    job.manual_review_reason = clear_reason
    job.error_message = None
    job.completed_at = None
