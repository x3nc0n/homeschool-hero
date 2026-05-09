from __future__ import annotations

import enum
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class AttendanceStatus(str, enum.Enum):
    present = 'present'
    absent = 'absent'
    tardy = 'tardy'
    excused = 'excused'


class AttendanceRecord(TimestampMixin, Base):
    __tablename__ = 'attendance_records'
    __table_args__ = (UniqueConstraint('family_id', 'student_id', 'date', name='uq_attendance_records_family_student_date'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name='attendance_status'),
        nullable=False,
        default=AttendanceStatus.present,
        server_default=AttendanceStatus.present.value,
        index=True,
    )
    check_in_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    check_out_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    instructional_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal('0'),
        server_default=text('0'),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    student = relationship('Student', back_populates='attendance_records')
    excuse = relationship(
        'AttendanceExcuse',
        back_populates='attendance_record',
        cascade='all, delete-orphan',
        uselist=False,
    )


class AttendanceExcuse(TimestampMixin, Base):
    __tablename__ = 'attendance_excuses'
    __table_args__ = (UniqueConstraint('attendance_record_id', name='uq_attendance_excuses_attendance_record_id'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    attendance_record_id: Mapped[int] = mapped_column(
        ForeignKey('attendance_records.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    document_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attendance_record = relationship('AttendanceRecord', back_populates='excuse')
    approved_by = relationship('User')

    @property
    def document_url(self) -> str | None:
        if not self.document_path:
            return None
        return f'/uploads/{Path(self.document_path).name}'
