from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base

json_type = JSON().with_variant(JSONB, 'postgresql')


class ImportEntityType(str, enum.Enum):
    students = 'students'
    subjects = 'subjects'
    assignments = 'assignments'
    grades = 'grades'
    attendance = 'attendance'
    curriculum_packages = 'curriculum_packages'


class ImportJobStatus(str, enum.Enum):
    pending = 'pending'
    validating = 'validating'
    importing = 'importing'
    complete = 'complete'
    failed = 'failed'


class ImportJob(Base):
    __tablename__ = 'import_jobs'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[ImportEntityType] = mapped_column(
        Enum(ImportEntityType, name='import_entity_type'),
        nullable=False,
        index=True,
    )
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, name='import_job_status'),
        nullable=False,
        default=ImportJobStatus.pending,
        server_default=ImportJobStatus.pending.value,
        index=True,
    )
    total_rows: Mapped[int] = mapped_column(nullable=False, default=0, server_default='0')
    processed_rows: Mapped[int] = mapped_column(nullable=False, default=0, server_default='0')
    error_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default='0')
    errors: Mapped[list[dict[str, Any]]] = mapped_column(json_type, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
