from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, BIGINT, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ExportType(str, enum.Enum):
    full = 'full'
    incremental = 'incremental'
    entity = 'entity'


class ExportFormat(str, enum.Enum):
    json = 'json'
    csv = 'csv'
    zip = 'zip'


class ExportJobStatus(str, enum.Enum):
    pending = 'pending'
    processing = 'processing'
    complete = 'complete'
    failed = 'failed'


class ExportEntityType(str, enum.Enum):
    family = 'family'
    students = 'students'
    subjects = 'subjects'
    assignments = 'assignments'
    submissions = 'submissions'
    grades = 'grades'
    attendance = 'attendance'
    report_cards = 'report_cards'
    transcripts = 'transcripts'
    portfolio_entries = 'portfolio_entries'
    compliance_reports = 'compliance_reports'
    audit_events = 'audit_events'


class ExportJob(Base):
    __tablename__ = 'export_jobs'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    export_type: Mapped[ExportType] = mapped_column(
        Enum(ExportType, name='export_type'),
        nullable=False,
        index=True,
    )
    format: Mapped[ExportFormat] = mapped_column(
        Enum(ExportFormat, name='export_format'),
        nullable=False,
        index=True,
    )
    status: Mapped[ExportJobStatus] = mapped_column(
        Enum(ExportJobStatus, name='export_job_status'),
        nullable=False,
        default=ExportJobStatus.pending,
        server_default=ExportJobStatus.pending.value,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0, server_default='0')
    entity_types: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), nullable=False, default=list)
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
