from __future__ import annotations

import enum
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class TermType(str, enum.Enum):
    semester = 'semester'
    quarter = 'quarter'
    trimester = 'trimester'
    custom = 'custom'


class CalendarEventType(str, enum.Enum):
    holiday = 'holiday'
    closure = 'closure'
    custom = 'custom'


class SchoolYear(TimestampMixin, Base):
    __tablename__ = 'school_years'
    __table_args__ = (UniqueConstraint('family_id', 'name', name='uq_school_years_family_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('false'))

    terms = relationship(
        'Term',
        back_populates='school_year',
        cascade='all, delete-orphan',
        order_by='Term.start_date',
    )
    calendar_events = relationship(
        'CalendarEvent',
        back_populates='school_year',
        cascade='all, delete-orphan',
        order_by='CalendarEvent.date',
    )


class Term(TimestampMixin, Base):
    __tablename__ = 'terms'
    __table_args__ = (UniqueConstraint('school_year_id', 'name', name='uq_terms_school_year_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_year_id: Mapped[int] = mapped_column(
        ForeignKey('school_years.id', ondelete='CASCADE'), nullable=False, index=True
    )
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    term_type: Mapped[TermType] = mapped_column(
        Enum(TermType, name='term_type'), nullable=False, default=TermType.semester
    )

    school_year = relationship('SchoolYear', back_populates='terms')
    grading_periods = relationship(
        'GradingPeriod',
        back_populates='term',
        cascade='all, delete-orphan',
        order_by='GradingPeriod.start_date',
    )


class GradingPeriod(TimestampMixin, Base):
    __tablename__ = 'grading_periods'
    __table_args__ = (UniqueConstraint('term_id', 'name', name='uq_grading_periods_term_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    term_id: Mapped[int] = mapped_column(ForeignKey('terms.id', ondelete='CASCADE'), nullable=False, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    term = relationship('Term', back_populates='grading_periods')


class CalendarEvent(TimestampMixin, Base):
    __tablename__ = 'calendar_events'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(
        ForeignKey('school_years.id', ondelete='CASCADE'), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_type: Mapped[CalendarEventType] = mapped_column(
        Enum(CalendarEventType, name='calendar_event_type'), nullable=False, default=CalendarEventType.holiday
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_instructional_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text('false')
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    school_year = relationship('SchoolYear', back_populates='calendar_events')
