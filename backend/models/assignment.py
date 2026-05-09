import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class AssignmentStatus(str, enum.Enum):
    pending = 'pending'
    complete = 'complete'
    graded = 'graded'


class AssignmentCategory(str, enum.Enum):
    homework = 'homework'
    quiz = 'quiz'
    test = 'test'
    project = 'project'
    participation = 'participation'
    extra_credit = 'extra_credit'
    other = 'other'


class AssignmentRecurrence(str, enum.Enum):
    none = 'none'
    daily = 'daily'
    weekly = 'weekly'


class AssignmentTargetStatus(str, enum.Enum):
    assigned = 'assigned'
    submitted = 'submitted'
    graded = 'graded'
    excused = 'excused'


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
    category: Mapped[AssignmentCategory] = mapped_column(
        Enum(AssignmentCategory, name='assignment_category'),
        nullable=False,
        default=AssignmentCategory.homework,
        server_default=AssignmentCategory.homework.value,
    )
    grading_period_id: Mapped[int | None] = mapped_column(ForeignKey('grading_periods.id', ondelete='SET NULL'), nullable=True, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default='1')
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0, server_default='100')
    recurrence: Mapped[AssignmentRecurrence] = mapped_column(
        Enum(AssignmentRecurrence, name='assignment_recurrence'),
        nullable=False,
        default=AssignmentRecurrence.none,
        server_default=AssignmentRecurrence.none.value,
    )
    recurrence_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rubric_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    lesson_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status_history: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)

    subject = relationship('Subject', back_populates='assignments', lazy='selectin')
    grading_period = relationship('GradingPeriod', back_populates='assignments', lazy='selectin')
    answer_key = relationship('AnswerKey', back_populates='assignment', cascade='all, delete-orphan', uselist=False, lazy='selectin')
    targets = relationship(
        'AssignmentTarget',
        back_populates='assignment',
        cascade='all, delete-orphan',
        order_by='AssignmentTarget.id',
        lazy='selectin',
    )
    submissions = relationship('Submission', back_populates='assignment', cascade='all, delete-orphan')
    portfolio_entries = relationship('PortfolioEntry', back_populates='assignment')


class AssignmentTarget(TimestampMixin, Base):
    __tablename__ = 'assignment_targets'
    __table_args__ = (UniqueConstraint('assignment_id', 'student_id', name='uq_assignment_targets_assignment_id_student_id'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('assignments.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AssignmentTargetStatus] = mapped_column(
        Enum(AssignmentTargetStatus, name='assignment_target_status'),
        nullable=False,
        default=AssignmentTargetStatus.assigned,
        server_default=AssignmentTargetStatus.assigned.value,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignment = relationship('Assignment', back_populates='targets')
    student = relationship('Student', back_populates='assignment_targets', lazy='selectin')
