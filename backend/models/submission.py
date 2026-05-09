from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Submission(TimestampMixin, Base):
    __tablename__ = 'submissions'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('assignments.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submission_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_submission_id: Mapped[int | None] = mapped_column(
        ForeignKey('submissions.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    assignment = relationship('Assignment', back_populates='submissions')
    student = relationship('Student', back_populates='submissions')
    parent_submission = relationship('Submission', remote_side='Submission.id', back_populates='version_history')
    version_history = relationship('Submission', back_populates='parent_submission')
    grade = relationship('Grade', back_populates='submission', uselist=False, cascade='all, delete-orphan')
    grading_job = relationship('GradingJob', back_populates='submission', uselist=False, cascade='all, delete-orphan')

    @property
    def file_url(self) -> str:
        return f"/uploads/{Path(self.file_path).as_posix().lstrip('/')}"

    @property
    def version_root_id(self) -> int:
        return self.parent_submission_id or self.id
