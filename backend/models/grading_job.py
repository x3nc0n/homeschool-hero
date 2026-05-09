import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, Text, func
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class GradingJobStatus(str, enum.Enum):
    pending = 'pending'
    ocr_processing = 'ocr_processing'
    ocr_complete = 'ocr_complete'
    ai_grading = 'ai_grading'
    ai_complete = 'ai_complete'
    review_needed = 'review_needed'
    reviewed = 'reviewed'
    final = 'final'
    queued = 'pending'
    processing = 'ai_grading'
    needs_review = 'review_needed'
    complete = 'final'
    failed = 'review_needed'

    @classmethod
    def _missing_(cls, value: object):
        legacy_map = {
            'queued': cls.pending,
            'processing': cls.ai_grading,
            'needs_review': cls.review_needed,
            'complete': cls.final,
            'failed': cls.review_needed,
        }
        if isinstance(value, str):
            return legacy_map.get(value.lower())
        return None


class GradingJob(Base):
    __tablename__ = 'grading_jobs'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False, unique=True, index=True
    )
    status: Mapped[GradingJobStatus] = mapped_column(
        Enum(GradingJobStatus, name='grading_job_status'), nullable=False, default=GradingJobStatus.pending
    )
    ocr_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_key_result: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    status_history: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    human_override_details: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    manual_review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submission = relationship('Submission', back_populates='grading_job')
