from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB, 'postgresql')


class ComplianceRuleType(str, enum.Enum):
    attendance_hours = 'attendance_hours'
    attendance_days = 'attendance_days'
    subjects_required = 'subjects_required'
    assessment_required = 'assessment_required'
    notification_required = 'notification_required'
    portfolio_required = 'portfolio_required'


class ComplianceState(str, enum.Enum):
    compliant = 'compliant'
    warning = 'warning'
    non_compliant = 'non_compliant'


class ComplianceRule(TimestampMixin, Base):
    __tablename__ = 'compliance_rules'
    __table_args__ = (
        UniqueConstraint('family_id', 'state_code', 'rule_name', name='uq_compliance_rules_family_state_name'),
        Index('ix_compliance_rules_family_state_active', 'family_id', 'state_code', 'is_active'),
        Index('ix_compliance_rules_state_type_active', 'state_code', 'rule_type', 'is_active'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=True, index=True)
    state_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    rule_type: Mapped[ComplianceRuleType] = mapped_column(
        Enum(ComplianceRuleType, name='compliance_rule_type'),
        nullable=False,
        index=True,
    )
    rule_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal('0'))
    threshold_unit: Mapped[str] = mapped_column(String(32), nullable=False, default='count', server_default='count')
    subjects_list: Mapped[list[str] | None] = mapped_column(json_type, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text('true'))

    family = relationship('Family', back_populates='compliance_rules')
    statuses = relationship('ComplianceStatus', back_populates='rule', cascade='all, delete-orphan')

    @property
    def is_custom(self) -> bool:
        return self.family_id is not None


class ComplianceStatus(Base):
    __tablename__ = 'compliance_statuses'
    __table_args__ = (
        UniqueConstraint(
            'family_id',
            'student_id',
            'school_year_id',
            'rule_id',
            name='uq_compliance_statuses_family_student_year_rule',
        ),
        Index('ix_compliance_statuses_family_status_school_year', 'family_id', 'status', 'school_year_id'),
        Index('ix_compliance_statuses_student_status', 'student_id', 'status'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(ForeignKey('school_years.id', ondelete='CASCADE'), nullable=False, index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey('compliance_rules.id', ondelete='CASCADE'), nullable=False, index=True)
    status: Mapped[ComplianceState] = mapped_column(
        Enum(ComplianceState, name='compliance_state'),
        nullable=False,
        default=ComplianceState.compliant,
        server_default=ComplianceState.compliant.value,
        index=True,
    )
    current_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal('0'))
    required_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal('0'))
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    family = relationship('Family', back_populates='compliance_statuses')
    student = relationship('Student', back_populates='compliance_statuses')
    school_year = relationship('SchoolYear', back_populates='compliance_statuses')
    rule = relationship('ComplianceRule', back_populates='statuses')
