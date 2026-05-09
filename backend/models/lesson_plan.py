from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class LessonPlanStatus(str, enum.Enum):
    planned = 'planned'
    in_progress = 'in_progress'
    completed = 'completed'
    skipped = 'skipped'
    rescheduled = 'rescheduled'


class LessonPlan(TimestampMixin, Base):
    __tablename__ = 'lesson_plans'
    __table_args__ = (
        UniqueConstraint(
            'student_id',
            'curriculum_lesson_id',
            name='uq_lesson_plans_student_id_curriculum_lesson_id',
        ),
        Index('ix_lesson_plans_family_student_status_target_date', 'family_id', 'student_id', 'status', 'target_date'),
        Index('ix_lesson_plans_family_status_target_date', 'family_id', 'status', 'target_date'),
        Index(
            'ix_lesson_plans_family_student_active_target_date',
            'family_id',
            'student_id',
            'target_date',
            postgresql_where=text("status NOT IN ('completed', 'skipped')"),
            sqlite_where=text("status NOT IN ('completed', 'skipped')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    curriculum_lesson_id: Mapped[int] = mapped_column(
        ForeignKey('curriculum_lessons.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(
        ForeignKey('school_years.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[LessonPlanStatus] = mapped_column(
        Enum(LessonPlanStatus, name='lesson_plan_status'),
        nullable=False,
        default=LessonPlanStatus.planned,
        server_default=LessonPlanStatus.planned.value,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    curriculum_lesson = relationship('CurriculumLesson', back_populates='lesson_plans', lazy='selectin')
    student = relationship('Student', back_populates='lesson_plans', lazy='selectin')
    school_year = relationship('SchoolYear', back_populates='lesson_plans', lazy='selectin')
    assignments = relationship(
        'Assignment',
        primaryjoin='LessonPlan.id == foreign(Assignment.lesson_plan_id)',
        viewonly=True,
        lazy='selectin',
    )

    @property
    def assignment_ids(self) -> list[int]:
        return [assignment.id for assignment in self.assignments]


class PacingTarget(TimestampMixin, Base):
    __tablename__ = 'pacing_targets'
    __table_args__ = (
        UniqueConstraint(
            'student_id',
            'curriculum_unit_id',
            name='uq_pacing_targets_student_id_curriculum_unit_id',
        ),
        Index('ix_pacing_targets_family_student_window', 'family_id', 'student_id', 'target_start_date', 'target_end_date'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    curriculum_unit_id: Mapped[int] = mapped_column(
        ForeignKey('curriculum_units.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    target_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    curriculum_unit = relationship('CurriculumUnit', back_populates='pacing_targets', lazy='selectin')
    student = relationship('Student', back_populates='pacing_targets', lazy='selectin')
