import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import Assignment, GradingJob, GradingJobStatus, Student, Submission
from backend.schemas.submissions import SubmissionRead
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, ensure_student_scope, get_student_scope_id, require_capabilities
from backend.validation import sanitize_filename

router = APIRouter(prefix='/submissions', tags=['submissions'])


@router.get('', response_model=list[SubmissionRead])
async def list_submissions(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_submissions, action='view submissions')),
) -> list[Submission]:
    stmt = select(Submission).where(Submission.family_id == auth.family_id)
    if auth.role == 'student_viewer':
        stmt = stmt.where(Submission.student_id == get_student_scope_id(auth))
    stmt = stmt.order_by(Submission.uploaded_at.desc())
    submissions = (await db.execute(stmt)).scalars().all()
    return list(submissions)


@router.get('/{submission_id}', response_model=SubmissionRead)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_submissions, action='view submissions')),
) -> Submission:
    submission = await get_family_record(db, Submission, submission_id, auth.family_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    ensure_student_scope(auth, submission.student_id, action='view submissions')
    return submission


@router.post('', response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
async def upload_submission(
    assignment_id: int = Form(..., gt=0),
    student_id: int = Form(..., gt=0),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_submissions, action='upload submissions')),
) -> Submission:
    assignment = await get_family_record(db, Assignment, assignment_id, auth.family_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Assignment not found')
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    sanitized_name = sanitize_filename(file.filename or '')
    suffix = Path(sanitized_name).suffix.lower()
    expected_mime, _ = mimetypes.guess_type(sanitized_name)
    content_type = (file.content_type or expected_mime or 'application/octet-stream').lower()
    allowed_mime_types = settings.upload_allowed_mime_types
    if content_type not in allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported file type')
    if expected_mime and expected_mime.lower() not in allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported file type')

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f'{uuid4().hex}{suffix}'
    destination = upload_dir / safe_name

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is empty')
    if len(contents) > settings.upload_max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='Uploaded file exceeds size limit')
    destination.write_bytes(contents)

    submission = Submission(
        family_id=auth.family_id,
        assignment_id=assignment_id,
        student_id=student_id,
        file_path=str(destination),
        file_type=content_type,
    )
    db.add(submission)
    await db.flush()

    job = GradingJob(family_id=auth.family_id, submission_id=submission.id, status=GradingJobStatus.queued)
    db.add(job)
    await db.commit()
    await db.refresh(submission)
    return submission
