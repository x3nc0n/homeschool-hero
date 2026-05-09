from __future__ import annotations

import enum
from datetime import date, time

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class ScheduleOverrideType(str, enum.Enum):
    cancel = 'cancel'
    reschedule = 'reschedule'
    add = 'add'


class Schedule(TimestampMixin, Base):
    __tablename__ = 'schedules'
    __table_args__ = (UniqueConstraint('student_id', 'school_year_id', 'name', name='uq_schedules_student_id_school_year_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(ForeignKey('school_years.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    student = relationship('Student', back_populates='schedules')
    school_year = relationship('SchoolYear', back_populates='schedules')
    blocks = relationship(
        'ScheduleBlock',
        back_populates='schedule',
        cascade='all, delete-orphan',
        order_by=lambda: (ScheduleBlock.day_of_week, ScheduleBlock.start_time, ScheduleBlock.end_time),
    )
    overrides = relationship(
        'ScheduleOverride',
        back_populates='schedule',
        cascade='all, delete-orphan',
        order_by=lambda: (ScheduleOverride.date, ScheduleOverride.start_time, ScheduleOverride.id),
    )


class ScheduleBlock(TimestampMixin, Base):
    __tablename__ = 'schedule_blocks'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey('schedules.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    schedule = relationship('Schedule', back_populates='blocks')
    subject = relationship('Subject', back_populates='schedule_blocks')
    overrides = relationship('ScheduleOverride', back_populates='original_block')


class ScheduleOverride(TimestampMixin, Base):
    __tablename__ = 'schedule_overrides'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey('schedules.id', ondelete='CASCADE'), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    original_block_id: Mapped[int | None] = mapped_column(
        ForeignKey('schedule_blocks.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    override_type: Mapped[ScheduleOverrideType] = mapped_column(
        Enum(ScheduleOverrideType, name='schedule_override_type'),
        nullable=False,
    )
    subject_id: Mapped[int | None] = mapped_column(ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True, index=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    schedule = relationship('Schedule', back_populates='overrides')
    original_block = relationship('ScheduleBlock', back_populates='overrides')
    subject = relationship('Subject', back_populates='schedule_overrides')
