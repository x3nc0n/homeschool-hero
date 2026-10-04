from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class AttendanceRecord(TimestampMixin, Base):
    __tablename__ = 'attendance_records'
    __table_args__ = (UniqueConstraint('family_id', 'student_id', 'date', name='uq_attendance_records_family_student_date'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_instructional_day: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text('true'),
        index=True,
    )
    instructional_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    student = relationship('Student', back_populates='attendance_records')
