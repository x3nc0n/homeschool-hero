from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.models.backup_job import BackupDestination, BackupType
from backend.models.export_job import ExportEntityType


class RestoreValidationCheckRead(BaseModel):
    name: str
    valid: bool
    expected: int | str | None = None
    actual: int | str | None = None
    message: str


class AvailableBackupRead(BaseModel):
    backup_id: str
    label: str
    file_path: str
    destination: BackupDestination
    backup_type: BackupType | None = None
    storage_mode: str
    created_at: datetime | None = None
    completed_at: datetime | None = None
    size_bytes: int = Field(default=0, ge=0)
    manifest_present: bool
    manifest_version: str | None = None
    available_entities: list[ExportEntityType] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestoreValidationRead(BaseModel):
    backup_id: str
    valid: bool
    can_restore: bool
    confirmation_token: str | None = None
    expires_at: datetime | None = None
    checks: list[RestoreValidationCheckRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestoreExecuteRequest(BaseModel):
    confirmation_token: str = Field(min_length=8)
    include_database: bool = True
    include_files: bool = True
    auto_backup: bool = True


class SelectiveRestoreRequest(BaseModel):
    confirmation_token: str = Field(min_length=8)
    entity_types: list[ExportEntityType] = Field(min_length=1)
    overwrite_existing: bool = False
    auto_backup: bool = True


class RestoreExecutionRead(BaseModel):
    backup_id: str
    mode: str
    restored_database: bool = False
    restored_files: bool = False
    restored_entities: dict[str, dict[str, int]] = Field(default_factory=dict)
    safety_snapshot_job_id: int | None = None
    completed_at: datetime
    message: str


class RetentionPolicyRead(BaseModel):
    retention_days: int = Field(ge=1)
    retention_count: int = Field(ge=1)


class RetentionCleanupRead(BaseModel):
    retention_days: int = Field(ge=1)
    retention_count: int = Field(ge=1)
    deleted: list[str] = Field(default_factory=list)
    kept: list[str] = Field(default_factory=list)
