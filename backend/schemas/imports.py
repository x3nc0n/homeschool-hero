from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.models.import_job import ImportEntityType, ImportJobStatus


class ImportJobErrorRead(BaseModel):
    row: int | None = None
    field: str | None = None
    message: str
    suggestion: str | None = None


class ImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    user_id: int
    file_path: str
    entity_type: ImportEntityType
    status: ImportJobStatus
    total_rows: int
    processed_rows: int
    error_count: int
    errors: list[ImportJobErrorRead]
    created_at: datetime
    completed_at: datetime | None
