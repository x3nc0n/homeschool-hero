from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from backend.schemas.backups import BackupStatusRead

HealthLevel = Literal['healthy', 'degraded', 'unhealthy', 'not_configured']
OverallHealthLevel = Literal['healthy', 'degraded', 'unhealthy']


class ServiceHealthRead(BaseModel):
    name: str
    label: str
    required: bool
    configured: bool
    status: HealthLevel
    message: str
    checked_at: datetime
    response_time_ms: float | None
    details: dict[str, Any]


class HealthSummaryRead(BaseModel):
    healthy: int
    degraded: int
    unhealthy: int
    not_configured: int


class SimpleHealthRead(BaseModel):
    status: OverallHealthLevel
    ready: bool
    checked_at: datetime
    transport: dict[str, bool]
    maintenance: dict[str, Any]


class ReadinessRead(BaseModel):
    status: Literal['ready', 'not_ready']
    ready: bool
    checked_at: datetime
    checks: dict[str, str]


class DetailedHealthRead(BaseModel):
    status: OverallHealthLevel
    ready: bool
    checked_at: datetime
    services: dict[str, ServiceHealthRead]
    summary: HealthSummaryRead
    backup: BackupStatusRead | None = None
    transport: dict[str, bool]
    maintenance: dict[str, Any]


class DiskUsageRead(BaseModel):
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float
    warning_threshold_percent: float
    critical_threshold_percent: float
    status: Literal['healthy', 'degraded', 'unhealthy']


class SystemStatusRead(DetailedHealthRead):
    version: str
    started_at: datetime
    uptime_seconds: int
    uptime_human: str
    disk: DiskUsageRead
