from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import AuditAction, Grade, GradedBy, GradingJob, GradingJobStatus, Submission
from backend.schemas.grading import GradingJobRead
from backend.security import AuthSession
from backend.services.audit import log_event
from backend.services.authorization import Capability, require_capabilities
from backend.services.grading_pipeline import transition_job
from backend.services.notifications import create_grading_complete_notifications

router = APIRouter(prefix='/grading', tags=['grading'])


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


def _job_snapshot(job: GradingJob) -> dict[str, object | None]:
    return {
        'id': job.id,
        'submission_id': job.submission_id,
        'status': job.status.value,
        'ai_grade': job.ai_grade,
        'ai_feedback': job.ai_feedback,
        'ai_confidence': job.ai_confidence,
        'answer_key_result': job.answer_key_result,
        'manual_review_reason': job.manual_review_reason,
        'human_override_details': job.human_override_details,
        'status_history': job.status_history,
    }


def _serialize_job(job: GradingJob) -> dict[str, object | None]:
    submission = job.submission
    assignment = submission.assignment if submission else None
    student = submission.student if submission else None
    return {
        'id': job.id,
        'family_id': job.family_id,
        'created_by_user_id': job.created_by_user_id,
        'submission_id': job.submission_id,
        'assignment_id': submission.assignment_id if submission else None,
        'assignment_title': assignment.title if assignment else None,
        'student_id': submission.student_id if submission else None,
        'student_name': student.name if student else None,
        'file_path': submission.file_path if submission else None,
        'file_url': submission.file_url if submission else None,
        'file_type': submission.file_type if submission else None,
        'status': job.status,
        'ocr_result': job.ocr_result,
        'ai_grade': job.ai_grade,
        'ai_feedback': job.ai_feedback,
        'ai_confidence': job.ai_confidence,
        'ai_response': job.ai_response,
        'answer_key_result': job.answer_key_result,
        'status_history': job.status_history,
        'human_override_details': job.human_override_details,
        'manual_review_reason': job.manual_review_reason,
        'ocr_retry_count': job.ocr_retry_count,
        'ai_retry_count': job.ai_retry_count,
        'error_message': job.error_message,
        'created_at': job.created_at,
        'completed_at': job.completed_at,
    }


async def _load_job(job_id: int, family_id: int, db: AsyncSession) -> GradingJob:
    result = await db.execute(
        select(GradingJob)
        .options(
            selectinload(GradingJob.submission).selectinload(Submission.assignment),
            selectinload(GradingJob.submission).selectinload(Submission.student),
        )
        .where(GradingJob.id == job_id, GradingJob.family_id == family_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found')
    return job


async def _upsert_grade(job: GradingJob, family_id: int, score: float, feedback: str | None, graded_by: GradedBy, db: AsyncSession) -> Grade:
    existing = (
        await db.execute(select(Grade).where(Grade.family_id == family_id, Grade.submission_id == job.submission_id))
    ).scalar_one_or_none()
    submission = job.submission
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    if not submission.is_current:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Only the current submission version can be graded')

    max_score = float(job.answer_key_result.get('max_score') if job.answer_key_result else existing.max_score if existing else 100.0)
    notes = feedback or job.ai_feedback
    if existing is None:
        grade = Grade(
            family_id=family_id,
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


class ReviewDecisionPayload(BaseModel):
    action: Literal['approve', 'modify', 'reject']
    score: float | None = Field(default=None, ge=0)
    feedback: str | None = None
    notes: str | None = None
    override_reason: str | None = None


class ReviewApprovePayload(BaseModel):
    score: float = Field(ge=0)
    feedback: str | None = None
    graded_by: GradedBy = GradedBy.ai_human
    override_reason: str | None = None


class ReviewRejectPayload(BaseModel):
    reason: str | None = None
    graded_by: GradedBy = GradedBy.human


@router.get('/jobs', response_model=list[GradingJobRead])
async def list_grading_jobs(
    status_filter: GradingJobStatus | None = Query(default=None, alias='status'),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='view grading jobs')),
) -> list[GradingJobRead]:
    stmt = (
        select(GradingJob)
        .options(
            selectinload(GradingJob.submission).selectinload(Submission.assignment),
            selectinload(GradingJob.submission).selectinload(Submission.student),
        )
        .where(GradingJob.family_id == auth.family_id)
        .order_by(GradingJob.created_at.desc(), GradingJob.id.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(GradingJob.status == status_filter)
    return [_serialize_job(job) for job in (await db.execute(stmt)).scalars().all()]


@router.get('/review-queue', response_model=list[GradingJobRead])
async def review_queue(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review grading jobs')),
) -> list[GradingJobRead]:
    jobs = (
        await db.execute(
            select(GradingJob)
            .options(
                selectinload(GradingJob.submission).selectinload(Submission.assignment),
                selectinload(GradingJob.submission).selectinload(Submission.student),
            )
            .join(Submission, Submission.id == GradingJob.submission_id)
            .where(
                GradingJob.family_id == auth.family_id,
                GradingJob.status == GradingJobStatus.review_needed,
                Submission.is_current.is_(True),
            )
            .order_by(GradingJob.created_at)
        )
    ).scalars()
    return [_serialize_job(job) for job in jobs]


@router.post('/review/{job_id}', response_model=GradingJobRead)
async def submit_review(
    job_id: int,
    payload: ReviewDecisionPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review grading jobs')),
) -> GradingJobRead:
    job = await _load_job(job_id, auth.family_id, db)
    if job.status != GradingJobStatus.review_needed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Only review-needed jobs can be reviewed')

    before_snapshot = _job_snapshot(job)
    if payload.action == 'reject':
        transition_job(
            job,
            GradingJobStatus.pending,
            detail='Human reviewer requested re-grade',
            payload={'reason': payload.override_reason or payload.notes},
        )
        job.manual_review_reason = payload.override_reason or payload.notes or 'Rejected during human review; re-queued for grading.'
        job.error_message = job.manual_review_reason
        job.completed_at = None
        await log_event(
            db,
            action=AuditAction.grade_update,
            actor=auth,
            family_id=auth.family_id,
            target_type='grading_job',
            target_id=job.id,
            before=before_snapshot,
            after=_job_snapshot(job),
            request=request,
        )
        await db.commit()
        await db.refresh(job)
        return _serialize_job(job)

    score = payload.score if payload.score is not None else float(job.ai_grade or 0.0)
    grade = await _upsert_grade(
        job=job,
        family_id=auth.family_id,
        score=score,
        feedback=payload.feedback or payload.notes,
        graded_by=GradedBy.ai_human if payload.action == 'approve' else GradedBy.human,
        db=db,
    )
    transition_job(
        job,
        GradingJobStatus.reviewed,
        detail='Human review completed',
        payload={'action': payload.action, 'score': score},
    )
    job.human_override_details = {
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'reviewed_by_user_id': auth.user_id,
        'action': payload.action,
        'override_reason': payload.override_reason,
        'notes': payload.notes,
        'feedback': payload.feedback,
        'final_score': score,
        'ai_score': job.ai_grade,
    }
    transition_job(
        job,
        GradingJobStatus.final,
        detail='Manual review finalized grade',
        payload={'grade_id': grade.id, 'score': score},
    )
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = None
    await create_grading_complete_notifications(
        db,
        family_id=auth.family_id,
        assignment_title=job.submission.assignment.title if job.submission and job.submission.assignment else 'Assignment',
        student_name=job.submission.student.name if job.submission and job.submission.student else 'Student',
        score=score,
        max_score=grade.max_score,
    )
    await log_event(
        db,
        action=AuditAction.grade_update,
        actor=auth,
        family_id=auth.family_id,
        target_type='grading_job',
        target_id=job.id,
        before=before_snapshot,
        after=_job_snapshot(job),
        request=request,
    )
    await db.commit()
    await db.refresh(job)
    return _serialize_job(job)


@router.post('/review-queue/{job_id}/approve', response_model=GradingJobRead)
async def approve_review(
    job_id: int,
    payload: ReviewApprovePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review grading jobs')),
) -> GradingJobRead:
    return await submit_review(
        job_id,
        ReviewDecisionPayload(
            action='approve',
            score=payload.score,
            feedback=payload.feedback,
            override_reason=payload.override_reason,
        ),
        request,
        db,
        auth,
    )


@router.post('/review-queue/{job_id}/reject', response_model=GradingJobRead)
async def reject_review(
    job_id: int,
    payload: ReviewRejectPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review grading jobs')),
) -> GradingJobRead:
    return await submit_review(
        job_id,
        ReviewDecisionPayload(action='reject', notes=payload.reason, override_reason=payload.reason),
        request,
        db,
        auth,
    )
