from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import Assignment, GradingJob, GradingJobStatus, Student, Submission
from backend.schemas.submissions import SubmissionRead
from backend.security import AuthSession, get_auth_session, get_family_record

router = APIRouter(prefix='/submissions', tags=['submissions'])


@router.get('', response_model=list[SubmissionRead])
async def list_submissions(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> list[Submission]:
    submissions = (
        await db.execute(
            select(Submission).where(Submission.family_id == auth.family_id).order_by(Submission.uploaded_at.desc())
        )
    ).scalars().all()
    return list(submissions)


@router.get('/{submission_id}', response_model=SubmissionRead)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Submission:
    submission = await get_family_record(db, Submission, submission_id, auth.family_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')
    return submission


@router.post('', response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
async def upload_submission(
    assignment_id: int = Form(...),
    student_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> Submission:
    assignment = await get_family_record(db, Assignment, assignment_id, auth.family_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Assignment not found')
    student = await get_family_record(db, Student, student_id, auth.family_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Student not found')
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Filename is required')

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename).suffix
    safe_name = f'{uuid4().hex}{suffix}'
    destination = upload_dir / safe_name

    contents = await file.read()
    destination.write_bytes(contents)

    submission = Submission(
        family_id=auth.family_id,
        assignment_id=assignment_id,
        student_id=student_id,
        file_path=str(destination),
        file_type=file.content_type or 'application/octet-stream',
    )
    db.add(submission)
    await db.flush()

    job = GradingJob(family_id=auth.family_id, submission_id=submission.id, status=GradingJobStatus.queued)
    db.add(job)
    await db.commit()
    await db.refresh(submission)
    return submission
