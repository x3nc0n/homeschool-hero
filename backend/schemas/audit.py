from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.models import AuditAction


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    actor_user_id: int
    actor_display_name: str | None = None
    actor_email: str | None = None
    action: AuditAction
    target_entity_type: str
    target_entity_id: str | None = None
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    timestamp: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
