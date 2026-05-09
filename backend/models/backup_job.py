from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, BIGINT, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class BackupType(str, enum.Enum):
    full = 'full'
    incremental = 'incremental'
    manual = 'manual'


class BackupJobStatus(str, enum.Enum):
    pending = 'pending'
    running = 'running'
    complete = 'complete'
    failed = 'failed'


class BackupDestination(str, enum.Enum):
    local = 'local'
    smb = 'smb'
    nfs = 'nfs'


class BackupJob(Base):
    __tablename__ = 'backup_jobs'
    __table_args__ = (
        Index('ix_backup_jobs_family_status_started_at', 'family_id', 'status', 'started_at'),
        Index('ix_backup_jobs_family_completed_at', 'family_id', 'completed_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    backup_type: Mapped[BackupType] = mapped_column(Enum(BackupType, name='backup_type'), nullable=False, index=True)
    status: Mapped[BackupJobStatus] = mapped_column(
        Enum(BackupJobStatus, name='backup_job_status'),
        nullable=False,
        default=BackupJobStatus.pending,
        server_default=BackupJobStatus.pending.value,
        index=True,
    )
    destination: Mapped[BackupDestination] = mapped_column(
        Enum(BackupDestination, name='backup_destination'),
        nullable=False,
        default=BackupDestination.local,
        server_default=BackupDestination.local.value,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, default='', server_default='')
    file_size: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0, server_default='0')
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
