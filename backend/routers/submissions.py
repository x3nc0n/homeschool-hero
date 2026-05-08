from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import Assignment, GradingJob, GradingJobStatus, Student, Submission
from backend.schemas.submissions import SubmissionRead

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.get("", response_model=list[SubmissionRead])
async def list_submissions(db: AsyncSession = Depends(get_db)) -> list[Submission]:
    submissions = (await db.execute(select(Submission).order_by(Submission.uploaded_at.desc()))).scalars().all()
    return list(submissions)


@router.get("/{submission_id}", response_model=SubmissionRead)
async def get_submission(submission_id: int, db: AsyncSession = Depends(get_db)) -> Submission:
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


@router.post("", response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
async def upload_submission(
    assignment_id: int = Form(...),
    student_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Submission:
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename).suffix
    safe_name = f"{uuid4().hex}{suffix}"
    destination = upload_dir / safe_name

    contents = await file.read()
    destination.write_bytes(contents)

    submission = Submission(
        assignment_id=assignment_id,
        student_id=student_id,
        file_path=str(destination),
        file_type=file.content_type or "application/octet-stream",
    )
    db.add(submission)
    await db.flush()

    job = GradingJob(submission_id=submission.id, status=GradingJobStatus.queued)
    db.add(job)
    await db.commit()
    await db.refresh(submission)
    return submission
