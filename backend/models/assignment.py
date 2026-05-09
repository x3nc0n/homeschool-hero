import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class AssignmentStatus(str, enum.Enum):
    pending = 'pending'
    complete = 'complete'
    graded = 'graded'


class Assignment(TimestampMixin, Base):
    __tablename__ = 'assignments'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name='assignment_status'), nullable=False, default=AssignmentStatus.pending
    )

    subject = relationship('Subject', back_populates='assignments')
    submissions = relationship('Submission', back_populates='assignment', cascade='all, delete-orphan')
