from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from backend.validation import normalize_text


class MaintenanceToggleRequest(BaseModel):
    enabled: bool
    message: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode='after')
    def normalize_values(self) -> 'MaintenanceToggleRequest':
        if self.message is not None:
            self.message = normalize_text(self.message, field_name='Maintenance message')
        return self


class MaintenanceScheduleRequest(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None
    message: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode='after')
    def validate_window(self) -> 'MaintenanceScheduleRequest':
        if self.message is not None:
            self.message = normalize_text(self.message, field_name='Maintenance message')
        if self.start_at is None and self.end_at is None:
            return self
        if self.start_at is None or self.end_at is None:
            raise ValueError('Both start_at and end_at are required when scheduling maintenance.')
        if self.end_at <= self.start_at:
            raise ValueError('Maintenance end time must be after the start time.')
        return self


class MaintenanceStatusRead(BaseModel):
    enabled: bool
    env_enabled: bool
    active: bool
    scheduled: bool
    schedule_active: bool
    message: str
    source: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    updated_at: datetime | None = None
    updated_by_user_id: int | None = None
    bypass_roles: list[str] = Field(default_factory=lambda: ['parent', 'co-parent'])
