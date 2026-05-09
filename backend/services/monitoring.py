from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import AuditAction, AuditEvent, GradingJob, GradingJobStatus


@dataclass
class RequestMetrics:
    total: int = 0
    duration_total_ms: float = 0.0
    duration_max_ms: float = 0.0
    slow_requests: int = 0
    status_codes: Counter[int] = field(default_factory=Counter)


class MonitoringStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests = RequestMetrics()

    def observe_request(self, *, status_code: int, duration_ms: float, slow: bool) -> None:
        with self._lock:
            self._requests.total += 1
            self._requests.duration_total_ms += duration_ms
            self._requests.duration_max_ms = max(self._requests.duration_max_ms, duration_ms)
            self._requests.status_codes[status_code] += 1
            if slow:
                self._requests.slow_requests += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            count = self._requests.total
            return {
                'requests_total': count,
                'request_duration_ms': {
                    'count': count,
                    'total': round(self._requests.duration_total_ms, 2),
                    'average': round(self._requests.duration_total_ms / count, 2) if count else 0.0,
                    'max': round(self._requests.duration_max_ms, 2),
                },
                'slow_requests_total': self._requests.slow_requests,
                'responses_by_status': dict(sorted(self._requests.status_codes.items())),
            }


def install_monitoring(app: FastAPI) -> None:
    if not hasattr(app.state, 'monitoring'):
        app.state.monitoring = MonitoringStore()


def get_monitoring(app: FastAPI) -> MonitoringStore:
    store = getattr(app.state, 'monitoring', None)
    if store is None:
        store = MonitoringStore()
        app.state.monitoring = store
    return store


def get_backup_last_success() -> dict[str, Any] | None:
    if not settings.backup_target:
        return None

    target = Path(settings.backup_target)
    stamp = target / '.last-success'
    if not stamp.exists():
        return None

    raw_timestamp = stamp.read_text(encoding='utf-8').strip()
    if not raw_timestamp:
        return None

    timestamp = datetime.fromisoformat(raw_timestamp.replace('Z', '+00:00'))
    size_path = target / '.last-success-size'
    size_bytes = None
    if size_path.exists():
        try:
            size_bytes = int(size_path.read_text(encoding='utf-8').strip())
        except ValueError:
            size_bytes = None

    latest_artifact = None
    for artifact in sorted(target.glob('*'), key=lambda item: item.stat().st_mtime, reverse=True):
        if artifact.name.startswith('.'):
            continue
        if artifact.is_file():
            latest_artifact = artifact
            break

    return {
        'timestamp': timestamp.astimezone(UTC).isoformat(),
        'age_seconds': max(0, int((datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds())),
        'size_bytes': size_bytes,
        'artifact': latest_artifact.name if latest_artifact else None,
    }


async def collect_metrics_payload(app: FastAPI, db: AsyncSession) -> dict[str, Any]:
    requests = get_monitoring(app).snapshot()
    grading_rows = (
        await db.execute(select(GradingJob.status, func.count()).group_by(GradingJob.status).order_by(GradingJob.status))
    ).all()
    grading_by_status = {status.value if isinstance(status, GradingJobStatus) else str(status): count for status, count in grading_rows}
    grading_total = int(sum(grading_by_status.values()))
    active_users = (
        await db.execute(
            select(func.count(distinct(AuditEvent.actor_user_id))).where(
                AuditEvent.timestamp >= datetime.now(UTC) - timedelta(days=1),
                AuditEvent.action == AuditAction.login,
            )
        )
    ).scalar_one()

    return {
        **requests,
        'grading_jobs_total': grading_total,
        'grading_jobs_by_status': grading_by_status,
        'active_users': int(active_users or 0),
        'backup_last_success': get_backup_last_success(),
        'enabled': settings.enable_metrics_endpoint,
    }
