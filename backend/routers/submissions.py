import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.models import Assignment, AssignmentTarget, AssignmentTargetStatus, GradingJob, GradingJobStatus, Student, Submission
from backend.schemas.submissions import SubmissionDetail, SubmissionRead, SubmissionVersionRead
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.services.logging_config import log_action
from backend.services.storage import normalize_upload_type, store_submission_file

router = APIRouter(prefix='/submissions', tags=['submissions'])
logger = logging.getLogger(__name__)


def _version_root_id(submission: Submission) -> int:
    return submission.parent_submission_id or submission.id


async def _load_version_history(db: AsyncSession, family_id: int, submission: Submission) -> list[Submission]:
    root_id = _version_root_id(submission)
    result = await db.execute(
        select(Submission)
        .where(
            Submission.family_id == family_id,
            or_(Submission.id == root_id, Submission.parent_submission_id == root_id),
        )
        .order_by(Submission.submission_version.desc(), Submission.uploaded_at.desc())
    )
    return list(result.scalars().all())


def _serialize_submission(submission: Submission) -> SubmissionVersionRead:
    return SubmissionVersionRead.model_validate(submission)


async def _serialize_submission_detail(db: AsyncSession, family_id: int, submission: Submission) -> SubmissionDetail:
    history = await _load_version_history(db, family_id, submission)
    payload = SubmissionRead.model_validate(submission).model_dump()
    payload['version_history'] = [entry.model_dump() for entry in (_serialize_submission(item) for item in history)]
    return SubmissionDetail.model_validate(payload)


async def _validate_assignment_target(
    db: AsyncSession,
    *,
    assignment_id: int,
    student_id: int,
) -> AssignmentTarget | None:
    target = (
        await db.execute(
            select(AssignmentTarget).where(
                AssignmentTarget.assignment_id == assignment_id,
                AssignmentTarget.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    target_exists = (
        await db.execute(select(AssignmentTarget.id).where(AssignmentTarget.assignment_id == assignment_id).limit(1))
    ).scalars().first()
    if target_exists is not None and not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Student is not assigned to this assignment',
        )
    return target


async def _mark_superseded_versions(
    db: AsyncSession,
    *,
    family_id: int,
    current_submission: Submission,
) -> None:
    root_id = _version_root_id(current_submission)
    prior_versions = (
        await db.execute(
            select(Submission)
            .options(selectinload(Submission.grading_job))
            .where(
                Submission.family_id == family_id,
                Submission.id != current_submission.id,
                or_(Submission.id == root_id, Submission.parent_submission_id == root_id),
                Submission.is_current.is_(True),
            )
        )
    ).scalars().all()
    for prior in prior_versions:
        prior.is_current = False
        job = prior.grading_job
        if job and job.status in {
            GradingJobStatus.queued,
            GradingJobStatus.processing,
            GradingJobStatus.needs_review,
        }:
            job.status = GradingJobStatus.failed
            job.error_message = f'Superseded by submission version {current_submission.submission_version}.'
            job.completed_at = datetime.now(timezone.utc)


@router.get('', response_model=list[SubmissionRead])
async def list_submissions(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_submissions, action='view submissions')),
) -> list[Submission]:
    stmt = select(Submission).where(Submission.family_id == auth.family_id, Submission.is_current.is_(True))
    if auth.role == 'student_viewer':
        stmt = stmt.where(Submission.student_id == get_student_scope_id(auth))
    stmt = stmt.order_by(Submission.uploaded_at.desc())
    submissions = (await db.execute(stmt)).scalars().all()
    return list(submissions)


@router.get('/{submission_id}', response_model=SubmissionDetail)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_submissions, action='view submissions')),
) -> SubmissionDetail:
    submission = await get_family_record(db, Submission, submission_id, auth.family_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    ensure_student_scope(auth, submission.student_id, action='view submissions')
    return await _serialize_submission_detail(db, auth.family_id, submission)


@router.post('', response_model=SubmissionDetail, status_code=status.HTTP_201_CREATED)
async def upload_submission(
    assignment_id: int = Form(..., gt=0),
    student_id: int = Form(..., gt=0),
    resubmission_of_submission_id: int | None = Form(default=None, gt=0),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_submissions, action='upload submissions')),
) -> SubmissionDetail:
    assignment = await get_family_record(db, Assignment, assignment_id, auth.family_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Assignment not found')
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    if assignment.family_id != auth.family_id or student.family_id != auth.family_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Family ownership validation failed')

    target = await _validate_assignment_target(db, assignment_id=assignment_id, student_id=student_id)
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is empty')
    if len(contents) > settings.upload_max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='Uploaded file exceeds size limit')

    try:
        sanitized_name, content_type = normalize_upload_type(
            file.filename or '',
            file.content_type or '',
            settings.upload_allowed_mime_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    parent_submission_id: int | None = None
    submission_version = 1
    if resubmission_of_submission_id is not None:
        prior_submission = await get_family_record(db, Submission, resubmission_of_submission_id, auth.family_id)
        if not prior_submission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
        if prior_submission.assignment_id != assignment_id or prior_submission.student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Resubmission must use the same assignment and student as the prior version',
            )
        parent_submission_id = _version_root_id(prior_submission)
        history = await _load_version_history(db, auth.family_id, prior_submission)
        submission_version = max(item.submission_version for item in history) + 1

    submission = Submission(
        family_id=auth.family_id,
        assignment_id=assignment_id,
        student_id=student_id,
        file_path='',
        original_filename=sanitized_name,
        file_name=sanitized_name,
        file_type=content_type,
        file_size_bytes=len(contents),
        submission_version=submission_version,
        parent_submission_id=parent_submission_id,
        is_current=True,
    )
    db.add(submission)
    await db.flush()

    stored_upload = store_submission_file(
        upload_root=settings.upload_dir,
        family_id=auth.family_id,
        student_id=student_id,
        assignment_id=assignment_id,
        submission_id=submission.id,
        original_filename=sanitized_name,
        content_type=content_type,
        contents=contents,
    )
    submission.file_path = stored_upload.relative_path
    submission.file_name = stored_upload.file_name
    submission.original_filename = stored_upload.file_name
    submission.file_size_bytes = stored_upload.file_size_bytes
    submission.image_width = stored_upload.image_width
    submission.image_height = stored_upload.image_height
    submission.page_count = stored_upload.page_count

    await _mark_superseded_versions(db, family_id=auth.family_id, current_submission=submission)

    if target:
        target.status = AssignmentTargetStatus.submitted
        target.completed_at = datetime.now(timezone.utc)

    job = GradingJob(family_id=auth.family_id, submission_id=submission.id, status=GradingJobStatus.queued)
    db.add(job)
    await db.commit()
    await db.refresh(submission)
    await db.refresh(job)
    log_action(
        logger,
        logging.INFO,
        'Queued grading job',
        action='grading_job_queued',
        user_id=auth.user_id,
        family_id=auth.family_id,
        details={
            'job_id': job.id,
            'submission_id': submission.id,
            'assignment_id': assignment_id,
            'student_id': student_id,
            'submission_version': submission.submission_version,
        },
    )
    return await _serialize_submission_detail(db, auth.family_id, submission)
