from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from backend.models.backup_job import BackupDestination, BackupJobStatus, BackupType


class BackupTriggerRequest(BaseModel):
    backup_type: BackupType = BackupType.manual


class BackupJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    user_id: int
    backup_type: BackupType
    status: BackupJobStatus
    destination: BackupDestination
    file_path: str
    file_size: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    manifest: dict[str, Any] | None


class BackupConfigRead(BaseModel):
    configured: bool
    scheduler_enabled: bool
    destination: BackupDestination
    target_path: str | None
    target_uri: str | None
    schedule: str
    next_scheduled: datetime | None
    retention_days: int
    retention_count: int
    filename_prefix: str
    encryption_configured: bool
    restic_installed: bool
    restic_enabled: bool
    restic_repository: str | None
    validation: dict[str, Any]
    smb: dict[str, Any] | None = None
    nfs: dict[str, Any] | None = None


class BackupStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    configured: bool
    scheduler_enabled: bool
    destination: BackupDestination
    next_scheduled: datetime | None
    restic_enabled: bool
    validation: dict[str, Any]
    last_backup: BackupJobRead | None
    last_success: BackupJobRead | None
