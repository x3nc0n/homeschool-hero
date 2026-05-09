from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import Grade, GradedBy, GradingJob, GradingJobStatus, Submission
from backend.security import AuthSession
from backend.services.authorization import Capability, require_capabilities
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


def _serialize_review_job(job: GradingJob) -> dict:
    submission = job.submission
    assignment = submission.assignment if submission else None
    student = submission.student if submission else None
    return {
        'id': job.id,
        'submission_id': job.submission_id,
        'assignment_id': submission.assignment_id if submission else None,
        'assignment_title': assignment.title if assignment else None,
        'student_id': submission.student_id if submission else None,
        'student_name': student.name if student else None,
        'file_path': submission.file_path if submission else None,
        'file_url': submission.file_url if submission else None,
        'file_type': submission.file_type if submission else None,
        'ocr_text': (submission.ocr_text if submission else None) or job.ocr_result,
        'ai_grade': job.ai_grade,
        'ai_feedback': job.ai_feedback,
        'ai_confidence': job.ai_confidence,
        'status': job.status.value,
        'created_at': job.created_at,
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


async def _upsert_grade(job: GradingJob, family_id: int, score: float, feedback: str | None, graded_by: GradedBy, db: AsyncSession) -> None:
    existing = (
        await db.execute(select(Grade).where(Grade.family_id == family_id, Grade.submission_id == job.submission_id))
    ).scalar_one_or_none()
    submission = job.submission
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    if not submission.is_current:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Only the current submission version can be graded')

    max_score = existing.max_score if existing else 100.0
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
        return

    existing.score = score
    existing.letter_grade = _to_letter_grade(score)
    existing.notes = notes
    existing.graded_by = graded_by
    existing.ai_confidence = job.ai_confidence


class ReviewApprovePayload(BaseModel):
    score: float = Field(ge=0)
    feedback: str | None = None
    graded_by: GradedBy = GradedBy.ai_human


class ReviewRejectPayload(BaseModel):
    reason: str | None = None
    graded_by: GradedBy = GradedBy.human


class ReviewDecisionPayload(BaseModel):
    action: Literal['approve', 'modify', 'reject']
    score: float | None = Field(default=None, ge=0)
    feedback: str | None = None
    notes: str | None = None


@router.get('/review-queue')
async def review_queue(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review grading jobs')),
):
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
                GradingJob.status == GradingJobStatus.needs_review,
                Submission.is_current.is_(True),
            )
            .order_by(GradingJob.created_at)
        )
    ).scalars()
    return [_serialize_review_job(job) for job in jobs]


@router.post('/review/{job_id}')
async def submit_review(
    job_id: int,
    payload: ReviewDecisionPayload,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review grading jobs')),
):
    job = await _load_job(job_id, auth.family_id, db)

    if payload.action == 'reject':
        job.status = GradingJobStatus.queued
        job.error_message = payload.notes or 'Rejected during human review; re-queued for grading.'
        job.completed_at = None
        await db.commit()
        await db.refresh(job)
        return _serialize_review_job(job)

    score = payload.score if payload.score is not None else float(job.ai_grade or 0.0)
    await _upsert_grade(
        job=job,
        family_id=auth.family_id,
        score=score,
        feedback=payload.feedback or payload.notes,
        graded_by=GradedBy.ai_human,
        db=db,
    )
    job.status = GradingJobStatus.complete
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = None
    await create_grading_complete_notifications(
        db,
        family_id=auth.family_id,
        assignment_title=job.submission.assignment.title if job.submission and job.submission.assignment else 'Assignment',
        student_name=job.submission.student.name if job.submission and job.submission.student else 'Student',
        score=score,
        max_score=job.submission.assignment.max_score if job.submission and job.submission.assignment else 100.0,
    )
    await db.commit()
    await db.refresh(job)
    return {'status': 'complete', 'job_id': job.id}


@router.post('/review-queue/{job_id}/approve')
async def approve_review(
    job_id: int,
    payload: ReviewApprovePayload,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review grading jobs')),
):
    job = await _load_job(job_id, auth.family_id, db)
    await _upsert_grade(
        job=job,
        family_id=auth.family_id,
        score=payload.score,
        feedback=payload.feedback,
        graded_by=payload.graded_by,
        db=db,
    )
    job.status = GradingJobStatus.complete
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = None
    await create_grading_complete_notifications(
        db,
        family_id=auth.family_id,
        assignment_title=job.submission.assignment.title if job.submission and job.submission.assignment else 'Assignment',
        student_name=job.submission.student.name if job.submission and job.submission.student else 'Student',
        score=payload.score,
        max_score=job.submission.assignment.max_score if job.submission and job.submission.assignment else 100.0,
    )
    await db.commit()
    return {'status': 'complete', 'job_id': job.id}


@router.post('/review-queue/{job_id}/reject')
async def reject_review(
    job_id: int,
    payload: ReviewRejectPayload,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_grading, action='review grading jobs')),
):
    job = await _load_job(job_id, auth.family_id, db)
    job.status = GradingJobStatus.queued
    job.error_message = payload.reason
    job.completed_at = None
    await db.commit()
    return {'status': 'queued', 'job_id': job.id}
