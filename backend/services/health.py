from __future__ import annotations

import asyncio
import logging
import shutil
import socket
import ssl
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings, settings
from backend.database import engine
from backend.openapi import API_VERSION
from backend.security import AuthSession
from backend.services.backup_service import get_backup_status
from backend.services.capabilities import check_ai_grading, check_email

logger = logging.getLogger(__name__)

DISK_WARNING_THRESHOLD_PERCENT = 95.0
DISK_CRITICAL_THRESHOLD_PERCENT = 98.0
OVERALL_HEALTH_STATES = {'healthy', 'degraded', 'unhealthy'}


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _service_payload(
    name: str,
    label: str,
    *,
    status: str,
    required: bool,
    configured: bool,
    message: str,
    response_time_ms: float | None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'name': name,
        'label': label,
        'required': required,
        'configured': configured,
        'status': status,
        'message': message,
        'checked_at': _timestamp(),
        'response_time_ms': None if response_time_ms is None else round(response_time_ms, 2),
        'details': details or {},
    }


async def check_database_health() -> dict[str, Any]:
    started = perf_counter()
    try:
        async with engine.connect() as connection:
            await connection.execute(text('SELECT 1'))
    except Exception as exc:
        return _service_payload(
            'database',
            'Database',
            status='unhealthy',
            required=True,
            configured=True,
            message=f'Database query failed: {exc}',
            response_time_ms=(perf_counter() - started) * 1000,
            details={},
        )
    return _service_payload(
        'database',
        'Database',
        status='healthy',
        required=True,
        configured=True,
        message='Database query succeeded.',
        response_time_ms=(perf_counter() - started) * 1000,
        details={},
    )


def _check_cache_health_sync(config: Settings = settings) -> dict[str, Any]:
    started = perf_counter()
    redis_url = str(getattr(config, 'redis_url', '') or '').strip()
    if not redis_url:
        return _service_payload(
            'cache',
            'Redis / cache',
            status='not_configured',
            required=False,
            configured=False,
            message='REDIS_URL is not configured; using in-process cache only.',
            response_time_ms=(perf_counter() - started) * 1000,
            details={'backend': 'memory'},
        )

    parsed = urlparse(redis_url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 6379
    try:
        connection = socket.create_connection((host, port), timeout=2.0)
        if parsed.scheme == 'rediss':
            context = ssl.create_default_context()
            sock = context.wrap_socket(connection, server_hostname=host)
        else:
            sock = connection
        try:
            sock.settimeout(2.0)
            sock.sendall(b'*1\r\n$4\r\nPING\r\n')
            response = sock.recv(16)
            if response and not (response.startswith(b'+PONG') or response.startswith(b'-NOAUTH')):
                raise RuntimeError(f'Unexpected Redis response: {response!r}')
        finally:
            sock.close()
    except Exception as exc:
        return _service_payload(
            'cache',
            'Redis / cache',
            status='degraded',
            required=False,
            configured=True,
            message=f'Redis is unreachable: {exc}',
            response_time_ms=(perf_counter() - started) * 1000,
            details={'host': host, 'port': port},
        )

    return _service_payload(
        'cache',
        'Redis / cache',
        status='healthy',
        required=False,
        configured=True,
        message='Redis responded to connectivity probe.',
        response_time_ms=(perf_counter() - started) * 1000,
        details={'host': host, 'port': port},
    )


def _map_capability_to_service(
    name: str,
    label: str,
    payload: dict[str, Any],
    *,
    required: bool = False,
) -> dict[str, Any]:
    if payload.get('enabled'):
        status = 'healthy'
    elif payload.get('configured'):
        status = 'degraded'
    else:
        status = 'not_configured'
    return _service_payload(
        name,
        label,
        status=status,
        required=required,
        configured=bool(payload.get('configured')),
        message=str(payload.get('reason') or ''),
        response_time_ms=None,
        details=dict(payload.get('details') or {}),
    )


def _check_backup_destination_sync(config: Settings = settings) -> dict[str, Any]:
    from backend.services.backup_service import get_backup_configuration

    started = perf_counter()
    payload = get_backup_configuration(config)
    validation = payload['validation']
    configured = bool(payload['configured'])
    if not configured:
        status = 'not_configured'
        message = 'Backup destination is not configured.'
    elif validation.get('reachable') and validation.get('writable'):
        status = 'healthy'
        message = str(validation.get('message') or 'Backup destination is reachable.')
    else:
        status = 'degraded'
        message = str(validation.get('message') or 'Backup destination is unavailable.')
    return _service_payload(
        'backup_destination',
        'NAS / backup destination',
        status=status,
        required=False,
        configured=configured,
        message=message,
        response_time_ms=(perf_counter() - started) * 1000,
        details={
            'destination': getattr(payload['destination'], 'value', payload['destination']),
            'target_path': payload.get('target_path'),
            'target_uri': payload.get('target_uri'),
            'schedule': payload.get('schedule'),
            'next_scheduled': payload.get('next_scheduled').isoformat() if payload.get('next_scheduled') else None,
            'validation': validation,
            'restic_enabled': payload.get('restic_enabled'),
        },
    )


def _check_disk_health_sync(config: Settings = settings) -> dict[str, Any]:
    started = perf_counter()
    upload_path = Path(config.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(upload_path)
    used_bytes = usage.total - usage.free
    used_percent = round((used_bytes / usage.total) * 100, 2) if usage.total else 0.0
    if used_percent >= DISK_CRITICAL_THRESHOLD_PERCENT:
        status = 'unhealthy'
        message = 'Upload storage is critically low on disk space.'
    elif used_percent >= DISK_WARNING_THRESHOLD_PERCENT:
        status = 'degraded'
        message = 'Upload storage is nearing capacity.'
    else:
        status = 'healthy'
        message = 'Upload storage has sufficient free disk space.'
    return _service_payload(
        'disk_space',
        'Upload storage',
        status=status,
        required=True,
        configured=True,
        message=message,
        response_time_ms=(perf_counter() - started) * 1000,
        details={
            'path': str(upload_path.resolve()),
            'total_bytes': usage.total,
            'used_bytes': used_bytes,
            'free_bytes': usage.free,
            'used_percent': used_percent,
            'warning_threshold_percent': DISK_WARNING_THRESHOLD_PERCENT,
            'critical_threshold_percent': DISK_CRITICAL_THRESHOLD_PERCENT,
        },
    )


def summarize_health(services: dict[str, dict[str, Any]]) -> tuple[str, dict[str, int]]:
    counts = {'healthy': 0, 'degraded': 0, 'unhealthy': 0, 'not_configured': 0}
    overall = 'healthy'
    for payload in services.values():
        status = str(payload.get('status') or 'degraded')
        counts[status if status in counts else 'degraded'] += 1
        if status == 'unhealthy' and payload.get('required'):
            overall = 'unhealthy'
        elif overall != 'unhealthy' and status in {'degraded', 'not_configured', 'unhealthy'}:
            overall = 'degraded'
    return overall, counts


async def collect_service_health(config: Settings = settings) -> dict[str, dict[str, Any]]:
    database_task = asyncio.create_task(check_database_health())
    cache_task = asyncio.create_task(asyncio.to_thread(_check_cache_health_sync, config))
    ai_task = asyncio.create_task(asyncio.to_thread(check_ai_grading, config))
    smtp_task = asyncio.create_task(asyncio.to_thread(check_email, config))
    backup_task = asyncio.create_task(asyncio.to_thread(_check_backup_destination_sync, config))
    disk_task = asyncio.create_task(asyncio.to_thread(_check_disk_health_sync, config))

    database, cache, ai_payload, smtp_payload, backup_destination, disk = await asyncio.gather(
        database_task,
        cache_task,
        ai_task,
        smtp_task,
        backup_task,
        disk_task,
    )
    return {
        'database': database,
        'cache': cache,
        'ai_service': _map_capability_to_service('ai_service', 'AI / Ollama', ai_payload),
        'smtp': _map_capability_to_service('smtp', 'SMTP', smtp_payload),
        'backup_destination': backup_destination,
        'disk_space': disk,
    }


def build_startup_log_lines(services: dict[str, dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for key in ['database', 'cache', 'ai_service', 'smtp', 'backup_destination', 'disk_space']:
        service = services.get(key)
        if service is None:
            continue
        lines.append(
            f"{service['label']}: {service['status']} ({service['message']})"
        )
    return lines


def get_runtime_started_at(app: FastAPI) -> datetime:
    started_at = getattr(app.state, 'started_at', None)
    if isinstance(started_at, datetime):
        return started_at.astimezone(UTC)
    started_at = datetime.now(UTC)
    app.state.started_at = started_at
    return started_at


def get_runtime_readiness(app: FastAPI) -> dict[str, bool]:
    return {
        'database_migrated': bool(getattr(app.state, 'database_migrated', settings.testing)),
        'services_initialized': bool(getattr(app.state, 'services_initialized', settings.testing)),
    }


async def build_health_payload(
    app: FastAPI,
    *,
    auth: AuthSession | None = None,
    db: AsyncSession | None = None,
    config: Settings = settings,
) -> dict[str, Any]:
    services = await collect_service_health(config)
    overall, summary = summarize_health(services)
    readiness = get_runtime_readiness(app)
    backup = None
    if auth is not None and db is not None:
        from backend.schemas.backups import BackupJobRead

        backup = await get_backup_status(db, family_id=auth.family_id)
        if backup.get('destination') is not None:
            backup['destination'] = getattr(backup['destination'], 'value', backup['destination'])
        if backup.get('last_backup') is not None:
            backup['last_backup'] = BackupJobRead.model_validate(backup['last_backup']).model_dump(mode='json')
        if backup.get('last_success') is not None:
            backup['last_success'] = BackupJobRead.model_validate(backup['last_success']).model_dump(mode='json')
    return {
        'status': overall,
        'ready': readiness['database_migrated'] and readiness['services_initialized'],
        'checked_at': _timestamp(),
        'services': services,
        'summary': summary,
        'backup': backup,
        'transport': {
            'tls_enabled': bool(getattr(config, 'tls_enabled', False)),
            'https_redirect_enabled': bool(
                getattr(config, 'tls_enabled', False) and getattr(config, 'https_redirect_enabled', False)
            ),
            'hsts_enabled': bool(getattr(config, 'hsts_enabled', False)),
        },
    }


async def build_simple_health_payload(app: FastAPI, config: Settings = settings) -> tuple[int, dict[str, Any]]:
    payload = await build_health_payload(app, config=config)
    database_status = payload['services'].get('database', {}).get('status')
    status_code = 503 if not payload['ready'] or database_status == 'unhealthy' else 200
    return status_code, {
        'status': payload['status'],
        'ready': payload['ready'],
        'checked_at': payload['checked_at'],
        'transport': payload['transport'],
    }


async def build_readiness_payload(app: FastAPI, config: Settings = settings) -> tuple[int, dict[str, Any]]:
    database = await check_database_health()
    readiness = get_runtime_readiness(app)
    ready = database['status'] == 'healthy' and readiness['database_migrated'] and readiness['services_initialized']
    return (
        200 if ready else 503,
        {
            'status': 'ready' if ready else 'not_ready',
            'ready': ready,
            'checked_at': _timestamp(),
            'checks': {
                'database': database['status'],
                'database_migrated': 'ready' if readiness['database_migrated'] else 'not_ready',
                'services_initialized': 'ready' if readiness['services_initialized'] else 'not_ready',
            },
        },
    )


def format_uptime(started_at: datetime) -> tuple[int, str]:
    uptime_seconds = max(0, int((datetime.now(UTC) - started_at).total_seconds()))
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return uptime_seconds, f'{hours}h {minutes}m'
    if minutes:
        return uptime_seconds, f'{minutes}m {seconds}s'
    return uptime_seconds, f'{seconds}s'


async def build_status_payload(app: FastAPI, auth: AuthSession, db: AsyncSession, config: Settings = settings) -> dict[str, Any]:
    payload = await build_health_payload(app, auth=auth, db=db, config=config)
    disk = payload['services']['disk_space']['details']
    started_at = get_runtime_started_at(app)
    uptime_seconds, uptime_human = format_uptime(started_at)
    return {
        **payload,
        'version': API_VERSION,
        'started_at': started_at.isoformat(),
        'uptime_seconds': uptime_seconds,
        'uptime_human': uptime_human,
        'disk': {
            'path': disk['path'],
            'total_bytes': disk['total_bytes'],
            'used_bytes': disk['used_bytes'],
            'free_bytes': disk['free_bytes'],
            'used_percent': disk['used_percent'],
            'warning_threshold_percent': disk['warning_threshold_percent'],
            'critical_threshold_percent': disk['critical_threshold_percent'],
            'status': payload['services']['disk_space']['status'],
        },
    }


async def log_startup_health_snapshot(app: FastAPI, config: Settings = settings) -> dict[str, Any]:
    payload = await build_health_payload(app, config=config)
    logger.info('Startup health status: %s', payload['status'])
    for line in build_startup_log_lines(payload['services']):
        logger.info('Startup health check - %s', line)
    for service in payload['services'].values():
        if not service['required'] and service['status'] in {'degraded', 'not_configured', 'unhealthy'}:
            logger.warning('Optional service unavailable at startup: %s (%s)', service['label'], service['message'])
    return payload
