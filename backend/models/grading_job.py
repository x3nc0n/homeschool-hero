import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class GradingJobStatus(str, enum.Enum):
    queued = 'queued'
    processing = 'processing'
    needs_review = 'needs_review'
    complete = 'complete'
    failed = 'failed'


class GradingJob(Base):
    __tablename__ = 'grading_jobs'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False, unique=True, index=True
    )
    status: Mapped[GradingJobStatus] = mapped_column(
        Enum(GradingJobStatus, name='grading_job_status'), nullable=False, default=GradingJobStatus.queued
    )
    ocr_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submission = relationship('Submission', back_populates='grading_job')
