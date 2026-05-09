from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

json_type = JSON().with_variant(JSONB, 'postgresql')


class ComplianceReportType(str, enum.Enum):
    annual_assessment = 'annual_assessment'
    quarterly_report = 'quarterly_report'
    notice_of_intent = 'notice_of_intent'
    attendance_log = 'attendance_log'
    portfolio_review = 'portfolio_review'


class ComplianceReportStatus(str, enum.Enum):
    draft = 'draft'
    final = 'final'
    submitted = 'submitted'


class ComplianceReport(Base):
    __tablename__ = 'compliance_reports'
    __table_args__ = (
        Index('ix_compliance_reports_family_student_year', 'family_id', 'student_id', 'school_year_id'),
        Index('ix_compliance_reports_state_type_status', 'state_code', 'report_type', 'status'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(ForeignKey('school_years.id', ondelete='CASCADE'), nullable=False, index=True)
    state_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    report_type: Mapped[ComplianceReportType] = mapped_column(
        Enum(ComplianceReportType, name='compliance_report_type'),
        nullable=False,
        index=True,
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    generated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    status: Mapped[ComplianceReportStatus] = mapped_column(
        Enum(ComplianceReportStatus, name='compliance_report_status'),
        nullable=False,
        default=ComplianceReportStatus.draft,
        server_default=ComplianceReportStatus.draft.value,
        index=True,
    )
    data: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    family = relationship('Family', back_populates='compliance_reports', lazy='selectin')
    student = relationship('Student', back_populates='compliance_reports', lazy='selectin')
    school_year = relationship('SchoolYear', back_populates='compliance_reports', lazy='selectin')
    generated_by = relationship('User', back_populates='generated_compliance_reports', lazy='selectin')
