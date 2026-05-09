from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.export_job import ExportEntityType, ExportFormat, ExportJobStatus, ExportType


class ExportJobCreateRequest(BaseModel):
    export_type: ExportType = ExportType.full
    format: ExportFormat = ExportFormat.json
    entity_types: list[ExportEntityType] = Field(default_factory=list)
    date_from: datetime | None = None

    @field_validator('entity_types')
    @classmethod
    def validate_entity_types(cls, value: list[ExportEntityType]) -> list[ExportEntityType]:
        return list(dict.fromkeys(value))

    @model_validator(mode='after')
    def validate_request(self) -> 'ExportJobCreateRequest':
        if self.export_type == ExportType.incremental and self.date_from is None:
            raise ValueError('Incremental exports require date_from')
        if self.export_type == ExportType.entity and not self.entity_types:
            raise ValueError('Entity exports require at least one entity type')
        return self


class ExportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    user_id: int
    export_type: ExportType
    format: ExportFormat
    status: ExportJobStatus
    file_path: str
    file_size: int
    entity_types: list[ExportEntityType]
    date_from: datetime | None
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime
