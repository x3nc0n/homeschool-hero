from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import desc, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings, settings
from backend.database import AsyncSessionLocal
from backend.models import (
    BackupDestination,
    BackupJob,
    BackupJobStatus,
    BackupType,
    ExportEntityType,
    ExportFormat,
    ExportJob,
    ExportJobStatus,
    ExportType,
    FamilyMembership,
    NotificationType,
)
from backend.services.export_service import _build_zip_export, _collect_export_bundle, DEFAULT_EXPORT_ENTITIES
from backend.services.notifications import FAMILY_MANAGER_ROLES, create_family_notifications

logger = logging.getLogger(__name__)

BACKUP_VERSION = '2026.05.10-dm03'
_BACKUP_TASKS: set[asyncio.Task[object]] = set()


@dataclass(slots=True)
class BackupExecutionContext:
    job_id: int
    family_id: int
    user_id: int
    backup_type: BackupType
    destination: BackupDestination
    started_at: datetime


@dataclass(slots=True)
class BackupExecutionResult:
    file_path: str
    file_size: int
    manifest: dict[str, Any]


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _track_task(task: asyncio.Task[object]) -> None:
    _BACKUP_TASKS.add(task)
    task.add_done_callback(_BACKUP_TASKS.discard)


def _sanitize_share_component(value: str) -> str:
    return value.strip().strip('/\\')


def resolve_backup_destination(config: Settings = settings) -> BackupDestination:
    raw = (config.backup_destination or 'local').strip().lower() or 'local'
    if raw in {'smb', 'nfs', 'local'}:
        return BackupDestination(raw)
    return BackupDestination.local


def _backup_target_path(config: Settings = settings) -> Path | None:
    if not config.backup_target:
        return None
    return Path(config.backup_target)


def _target_uri(config: Settings = settings) -> str | None:
    destination = resolve_backup_destination(config)
    if destination == BackupDestination.smb and config.backup_smb_host and config.backup_smb_share:
        return f"smb://{config.backup_smb_host}/{_sanitize_share_component(config.backup_smb_share)}"
    if destination == BackupDestination.nfs and config.backup_nfs_host and config.backup_nfs_path:
        return f"nfs://{config.backup_nfs_host}/{_sanitize_share_component(config.backup_nfs_path)}"
    return str(_backup_target_path(config)) if _backup_target_path(config) else None


def _restic_repository(config: Settings = settings) -> Path | None:
    target = _backup_target_path(config)
    if target is None:
        return None
    return target / 'restic-repo'


def restic_installed(config: Settings = settings) -> bool:
    _ = config
    return shutil.which('restic') is not None


def restic_enabled(config: Settings = settings) -> bool:
    return restic_installed(config) and bool((config.backup_encryption_key or '').strip()) and bool(_backup_target_path(config))


def compute_next_backup_run(config: Settings = settings, *, reference: datetime | None = None) -> datetime | None:
    if not config.backup_target or not config.backup_scheduler_enabled:
        return None
    trigger = CronTrigger.from_crontab(config.backup_schedule, timezone=UTC)
    return trigger.get_next_fire_time(None, reference or _now_utc())


def validate_backup_configuration(
    config: Settings = settings,
    *,
    raise_on_error: bool = True,
) -> dict[str, Any]:
    destination = resolve_backup_destination(config)
    target = _backup_target_path(config)
    details: dict[str, Any] = {
        'configured': bool(target),
        'reachable': False,
        'writable': False,
        'message': 'Backups are not configured.',
    }
    if target is None:
        if raise_on_error:
            raise ValueError('BACKUP_TARGET is required to enable local, SMB, or NFS backups.')
        return details

    if destination == BackupDestination.smb:
        missing = [
            name
            for name, value in {
                'BACKUP_SMB_HOST': config.backup_smb_host,
                'BACKUP_SMB_SHARE': config.backup_smb_share,
                'BACKUP_SMB_USER': config.backup_smb_user,
                'BACKUP_SMB_PASSWORD': config.backup_smb_password,
            }.items()
            if not (value or '').strip()
        ]
        if missing:
            if raise_on_error:
                raise ValueError('SMB backups require: ' + ', '.join(missing))
            details['message'] = 'SMB credentials are incomplete.'
            return details
        if not target.exists():
            if raise_on_error:
                raise ValueError(f"SMB mount path '{target}' was not found. Mount the share before startup.")
            details['message'] = 'SMB mount path is not available.'
            return details
    elif destination == BackupDestination.nfs:
        missing = [
            name
            for name, value in {
                'BACKUP_NFS_HOST': config.backup_nfs_host,
                'BACKUP_NFS_PATH': config.backup_nfs_path,
            }.items()
            if not (value or '').strip()
        ]
        if missing:
            if raise_on_error:
                raise ValueError('NFS backups require: ' + ', '.join(missing))
            details['message'] = 'NFS path settings are incomplete.'
            return details
        if not target.exists():
            if raise_on_error:
                raise ValueError(f"NFS mount path '{target}' was not found. Mount the export before startup.")
            details['message'] = 'NFS mount path is not available.'
            return details
    else:
        target.mkdir(parents=True, exist_ok=True)

    CronTrigger.from_crontab(config.backup_schedule, timezone=UTC)

    if not target.is_dir():
        if raise_on_error:
            raise ValueError(f"BACKUP_TARGET '{target}' must be a directory.")
        details['message'] = 'Backup target is not a directory.'
        return details

    probe = target / f'.backup-probe-{datetime.now(UTC).timestamp():.0f}'
    try:
        probe.write_text('ok', encoding='utf-8')
        details['reachable'] = True
        details['writable'] = True
        details['message'] = 'Backup target is reachable and writable.'
    finally:
        if probe.exists():
            probe.unlink()
    return details


def get_backup_configuration(config: Settings = settings) -> dict[str, Any]:
    try:
        validation = validate_backup_configuration(config, raise_on_error=False)
        next_scheduled = compute_next_backup_run(config)
    except Exception as exc:  # pragma: no cover - defensive
        validation = {'configured': False, 'reachable': False, 'writable': False, 'message': str(exc)}
        next_scheduled = None
    repository = _restic_repository(config)
    return {
        'configured': bool(config.backup_target),
        'scheduler_enabled': config.backup_scheduler_enabled,
        'destination': resolve_backup_destination(config),
        'target_path': str(_backup_target_path(config)) if _backup_target_path(config) else None,
        'target_uri': _target_uri(config),
        'schedule': config.backup_schedule,
        'next_scheduled': next_scheduled,
        'retention_days': config.backup_retention_days,
        'retention_count': max(1, config.backup_retention_count),
        'filename_prefix': config.backup_filename_prefix,
        'encryption_configured': bool((config.backup_encryption_key or '').strip()),
        'restic_installed': restic_installed(config),
        'restic_enabled': restic_enabled(config),
        'restic_repository': str(repository) if repository is not None else None,
        'validation': validation,
        'smb': (
            {
                'host': config.backup_smb_host,
                'share': config.backup_smb_share,
                'user': config.backup_smb_user,
                'password_configured': bool((config.backup_smb_password or '').strip()),
            }
            if resolve_backup_destination(config) == BackupDestination.smb
            else None
        ),
        'nfs': (
            {
                'host': config.backup_nfs_host,
                'path': config.backup_nfs_path,
            }
            if resolve_backup_destination(config) == BackupDestination.nfs
            else None
        ),
    }


async def list_backup_jobs(db: AsyncSession, *, family_id: int) -> list[BackupJob]:
    return list(
        (
            await db.execute(
                select(BackupJob).where(BackupJob.family_id == family_id).order_by(BackupJob.started_at.desc(), BackupJob.id.desc())
            )
        ).scalars()
    )


async def create_backup_job(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    backup_type: BackupType = BackupType.manual,
) -> BackupJob:
    destination = resolve_backup_destination()
    job = BackupJob(
        family_id=family_id,
        user_id=user_id,
        backup_type=backup_type,
        status=BackupJobStatus.pending,
        destination=destination,
        file_path='',
        file_size=0,
        manifest=None,
    )
    db.add(job)
    await db.flush()
    return job


async def get_backup_status(db: AsyncSession, *, family_id: int) -> dict[str, Any]:
    latest = (
        await db.execute(
            select(BackupJob)
            .where(BackupJob.family_id == family_id)
            .order_by(BackupJob.started_at.desc(), BackupJob.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    latest_success = (
        await db.execute(
            select(BackupJob)
            .where(BackupJob.family_id == family_id, BackupJob.status == BackupJobStatus.complete)
            .order_by(BackupJob.completed_at.desc(), BackupJob.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    config_payload = get_backup_configuration()
    return {
        'configured': config_payload['configured'],
        'scheduler_enabled': config_payload['scheduler_enabled'],
        'destination': config_payload['destination'],
        'next_scheduled': config_payload['next_scheduled'],
        'restic_enabled': config_payload['restic_enabled'],
        'validation': config_payload['validation'],
        'last_backup': latest,
        'last_success': latest_success,
    }


def _directory_size(path: Path) -> int:
    total = 0
    for file_path in path.rglob('*'):
        if file_path.is_file():
            total += file_path.stat().st_size
    return total


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_database_backup(config: Settings, destination: Path) -> dict[str, Any]:
    url = make_url(config.database_url)
    if url.drivername.startswith('sqlite'):
        source = Path(url.database or '')
        if not source.is_absolute():
            source = Path.cwd() / source
        if not source.exists():
            raise RuntimeError(f"SQLite database '{source}' does not exist.")
        target = destination / 'database.sqlite3'
        shutil.copy2(source, target)
        return {'mode': 'sqlite_copy', 'path': str(target), 'size_bytes': target.stat().st_size}

    pg_dump_binary = shutil.which('pg_dump')
    if not pg_dump_binary:
        raise RuntimeError('pg_dump is required for PostgreSQL backups but was not found on PATH.')

    target = destination / 'database.dump'
    env = {'PGPASSWORD': url.password or ''}
    command = [
        pg_dump_binary,
        '--format=custom',
        '--clean',
        '--if-exists',
        '--file',
        str(target),
        '--host',
        str(url.host or 'localhost'),
        '--port',
        str(url.port or 5432),
        '--username',
        str(url.username or config.postgres_user),
        str(url.database or config.postgres_db),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, env={**os.environ, **env}, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or 'pg_dump failed')
    return {'mode': 'pg_dump_custom', 'path': str(target), 'size_bytes': target.stat().st_size}


def _copy_upload_tree(source: Path, destination: Path) -> dict[str, Any]:
    target = destination / 'uploads'
    if not source.exists():
        _ensure_directory(target)
        return {'path': str(target), 'files_copied': 0, 'size_bytes': 0}
    shutil.copytree(source, target, dirs_exist_ok=True)
    return {'path': str(target), 'files_copied': sum(1 for item in target.rglob('*') if item.is_file()), 'size_bytes': _directory_size(target)}


async def _build_export_archive(family_id: int, user_id: int, destination: Path) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        package, csv_rows, binary_files = await _collect_export_bundle(
            db,
            family_id=family_id,
            export_type=ExportType.full,
            entity_types=list(DEFAULT_EXPORT_ENTITIES),
            date_from=None,
        )
    pseudo_job = ExportJob(
        id=0,
        family_id=family_id,
        user_id=user_id,
        export_type=ExportType.full,
        format=ExportFormat.zip,
        status=ExportJobStatus.complete,
        file_path='',
        file_size=0,
        entity_types=[entity.value if isinstance(entity, ExportEntityType) else str(entity) for entity in DEFAULT_EXPORT_ENTITIES],
        date_from=None,
        expires_at=_now_utc() + timedelta(days=7),
    )
    content, file_name = _build_zip_export(pseudo_job, package=package, csv_rows=csv_rows, binary_files=binary_files)
    target = destination / file_name
    await asyncio.to_thread(target.write_bytes, content)
    return {
        'path': str(target),
        'size_bytes': target.stat().st_size,
        'entity_counts': package['metadata'].get('entity_counts', {}),
    }


def _write_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding='utf-8')


def _restic_env(config: Settings) -> dict[str, str]:
    repository = _restic_repository(config)
    if repository is None:
        raise RuntimeError('Restic repository path could not be resolved.')
    return {
        'RESTIC_PASSWORD': config.backup_encryption_key or '',
        'RESTIC_REPOSITORY': str(repository),
    }


def _initialize_restic_repository(config: Settings) -> Path:
    repository = _restic_repository(config)
    if repository is None:
        raise RuntimeError('Restic repository path could not be resolved.')
    repository.mkdir(parents=True, exist_ok=True)
    if (repository / 'config').exists():
        return repository
    command = [shutil.which('restic') or 'restic', 'init']
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env={**os.environ, **_restic_env(config)},
        check=False,
    )
    if completed.returncode != 0 and 'already initialized' not in completed.stderr.lower():
        raise RuntimeError(completed.stderr.strip() or 'restic init failed')
    return repository


def _run_restic_backup(config: Settings, source: Path) -> tuple[Path, str | None]:
    repository = _initialize_restic_repository(config)
    command = [shutil.which('restic') or 'restic', 'backup', str(source), '--json']
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env={**os.environ, **_restic_env(config)},
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or 'restic backup failed')
    snapshot_id = None
    for line in completed.stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get('message_type') == 'summary':
            snapshot_id = payload.get('snapshot_id')
    return repository, snapshot_id if isinstance(snapshot_id, str) else None


def _write_success_markers(target: Path, *, completed_at: datetime, size_bytes: int) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / '.last-success').write_text(completed_at.isoformat(), encoding='utf-8')
    (target / '.last-success-size').write_text(str(size_bytes), encoding='utf-8')


def _cleanup_old_backups(config: Settings) -> None:
    target = _backup_target_path(config)
    if target is None or not target.exists():
        return
    cutoff = _now_utc() - timedelta(days=config.backup_retention_days)
    candidates: list[tuple[Path, datetime]] = []
    for item in target.iterdir():
        if item.name.startswith('.') or item.name in {'_staging', 'restic-repo', 'manifests'} or not item.is_dir():
            continue
        try:
            modified = datetime.fromtimestamp(item.stat().st_mtime, tz=UTC)
        except OSError:
            continue
        candidates.append((item, modified))
    candidates.sort(key=lambda row: row[1], reverse=True)
    keep_minimum = max(1, int(config.backup_retention_count))
    protected = {path for path, _ in candidates[:keep_minimum]}
    for item, modified in candidates:
        if item in protected or modified >= cutoff:
            continue
        shutil.rmtree(item, ignore_errors=True)


def _build_manifest(
    *,
    context: BackupExecutionContext,
    file_size: int,
    database: dict[str, Any],
    files: dict[str, Any],
    export: dict[str, Any],
    restic_snapshot_id: str | None,
    storage_mode: str,
) -> dict[str, Any]:
    return {
        'version': BACKUP_VERSION,
        'backup_id': context.job_id,
        'family_id': context.family_id,
        'user_id': context.user_id,
        'backup_type': context.backup_type.value,
        'destination': context.destination.value,
        'storage_mode': storage_mode,
        'restic_snapshot_id': restic_snapshot_id,
        'created_at': context.started_at.isoformat(),
        'completed_at': _now_utc().isoformat(),
        'size_bytes': file_size,
        'contents': {
            'database': database,
            'files': files,
            'export': export,
        },
    }


def _normalize_manifest_paths(manifest: dict[str, Any], *, export_file_name: str | None = None) -> dict[str, Any]:
    contents = manifest.setdefault('contents', {})
    database = contents.get('database')
    files = contents.get('files')
    export = contents.get('export')
    if isinstance(database, dict):
        existing = database.get('path')
        database['path'] = str(Path('database') / Path(str(existing)).name) if existing else str(Path('database') / 'database.dump')
    if isinstance(files, dict):
        files['path'] = str(Path('files') / 'uploads')
    if isinstance(export, dict):
        existing = export.get('path')
        export_name = export_file_name or (Path(str(existing)).name if existing else 'family-export.zip')
        export['path'] = str(Path('exports') / export_name)
    return manifest


async def _perform_backup(context: BackupExecutionContext) -> BackupExecutionResult:
    config = settings
    validation = validate_backup_configuration(config)
    if not validation['writable']:
        raise RuntimeError(validation['message'])

    target = _backup_target_path(config)
    if target is None:
        raise RuntimeError('BACKUP_TARGET is not configured.')
    await asyncio.to_thread(_ensure_directory, target)
    started_stamp = context.started_at.strftime('%Y%m%dT%H%M%SZ')
    staging_root = target / '_staging' / f'backup-{context.job_id}-{started_stamp}'
    await asyncio.to_thread(_ensure_directory, staging_root)
    try:
        database_dir = staging_root / 'database'
        files_dir = staging_root / 'files'
        exports_dir = staging_root / 'exports'
        await asyncio.to_thread(_ensure_directory, database_dir)
        await asyncio.to_thread(_ensure_directory, files_dir)
        await asyncio.to_thread(_ensure_directory, exports_dir)

        database = await asyncio.to_thread(_write_database_backup, config, database_dir)
        files = await asyncio.to_thread(_copy_upload_tree, Path(config.upload_dir), files_dir)
        export = await _build_export_archive(context.family_id, context.user_id, exports_dir)

        stage_size = await asyncio.to_thread(_directory_size, staging_root)

        if restic_enabled(config):
            repository, snapshot_id = await asyncio.to_thread(_run_restic_backup, config, staging_root)
            manifests_dir = target / 'manifests'
            await asyncio.to_thread(_ensure_directory, manifests_dir)
            manifest_path = manifests_dir / f'backup-{context.job_id}-manifest.json'
            manifest = _build_manifest(
                context=context,
                file_size=stage_size,
                database=database,
                files=files,
                export=export,
                restic_snapshot_id=snapshot_id,
                storage_mode='restic',
            )
            manifest = _normalize_manifest_paths(manifest, export_file_name=Path(str(export.get('path') or '')).name)
            await asyncio.to_thread(_write_manifest, manifest_path, manifest)
            completed_at = _now_utc()
            await asyncio.to_thread(_write_success_markers, target, completed_at=completed_at, size_bytes=stage_size)
            await asyncio.to_thread(_cleanup_old_backups, config)
            return BackupExecutionResult(file_path=f'{repository}#{snapshot_id or "latest"}', file_size=stage_size, manifest=manifest)

        destination_dir = target / f'{config.backup_filename_prefix}-{started_stamp}-backup-{context.job_id}'
        await asyncio.to_thread(shutil.copytree, staging_root, destination_dir, dirs_exist_ok=True)
        artifact_size = await asyncio.to_thread(_directory_size, destination_dir)
        manifest = _build_manifest(
            context=context,
            file_size=artifact_size,
            database=database,
            files=files,
            export=export,
            restic_snapshot_id=None,
            storage_mode='plain_copy',
        )
        manifest = _normalize_manifest_paths(manifest, export_file_name=Path(str(export.get('path') or '')).name)
        await asyncio.to_thread(_write_manifest, destination_dir / 'manifest.json', manifest)
        completed_at = _now_utc()
        await asyncio.to_thread(_write_success_markers, target, completed_at=completed_at, size_bytes=artifact_size)
        await asyncio.to_thread(_cleanup_old_backups, config)
        return BackupExecutionResult(file_path=str(destination_dir), file_size=artifact_size, manifest=manifest)
    finally:
        await asyncio.to_thread(shutil.rmtree, staging_root, True)


async def _notify_backup_result(db: AsyncSession, job: BackupJob) -> None:
    if job.status == BackupJobStatus.complete:
        title = 'Backup completed successfully'
        message = 'Backup finished and the artifact is available in backup history.'
    else:
        title = 'Backup failed'
        message = job.error_message or 'Backup failed before completion. Review backup settings and retry.'
    await create_family_notifications(
        db,
        family_id=job.family_id,
        notification_type=NotificationType.backup_status,
        title=title,
        message=message,
        link='/settings/backups',
        roles=FAMILY_MANAGER_ROLES,
        suppress_duplicates_for=timedelta(minutes=30 if job.status == BackupJobStatus.complete else 5),
    )


async def _run_backup_job(job_id: int) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(BackupJob, job_id)
        if job is None or job.status == BackupJobStatus.complete:
            return
        job.status = BackupJobStatus.running
        job.started_at = _now_utc()
        job.completed_at = None
        job.error_message = None
        job.file_path = ''
        job.file_size = 0
        job.manifest = None
        await db.commit()
        context = BackupExecutionContext(
            job_id=job.id,
            family_id=job.family_id,
            user_id=job.user_id,
            backup_type=job.backup_type,
            destination=job.destination,
            started_at=job.started_at,
        )

    try:
        result = await _perform_backup(context)
    except Exception as exc:
        logger.exception('Backup job %s failed', job_id)
        async with AsyncSessionLocal() as db:
            job = await db.get(BackupJob, job_id)
            if job is None:
                return
            job.status = BackupJobStatus.failed
            job.completed_at = _now_utc()
            job.error_message = str(exc)
            await _notify_backup_result(db, job)
            await db.commit()
        return

    async with AsyncSessionLocal() as db:
        job = await db.get(BackupJob, job_id)
        if job is None:
            return
        job.status = BackupJobStatus.complete
        job.file_path = result.file_path
        job.file_size = result.file_size
        job.completed_at = _now_utc()
        job.manifest = result.manifest
        await _notify_backup_result(db, job)
        await db.commit()


def schedule_backup_execution(job_id: int) -> None:
    _track_task(asyncio.create_task(_run_backup_job(job_id)))


async def run_scheduled_backups() -> list[int]:
    selected: list[tuple[int, int]] = []
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(FamilyMembership.family_id, FamilyMembership.user_id)
                .where(
                    FamilyMembership.accepted_at.is_not(None),
                    FamilyMembership.role.in_(tuple(FAMILY_MANAGER_ROLES)),
                )
                .order_by(FamilyMembership.family_id.asc(), desc(FamilyMembership.is_owner), FamilyMembership.user_id.asc())
            )
        ).all()
        seen_families: set[int] = set()
        for family_id, user_id in rows:
            if family_id in seen_families:
                continue
            seen_families.add(family_id)
            selected.append((family_id, user_id))

        job_ids: list[int] = []
        backup_type = BackupType.incremental if restic_enabled() else BackupType.full
        for family_id, user_id in selected:
            job = await create_backup_job(db, family_id=family_id, user_id=user_id, backup_type=backup_type)
            job_ids.append(job.id)
        await db.commit()

    for job_id in job_ids:
        await _run_backup_job(job_id)
    return job_ids


class BackupSchedulerRuntime:
    def __init__(self) -> None:
        self._scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        config = settings
        if config.testing or not config.backup_scheduler_enabled or not config.backup_target:
            return
        validate_backup_configuration(config)
        if self._scheduler is not None:
            return
        scheduler = BackgroundScheduler(timezone=UTC)
        scheduler.add_job(
            lambda: asyncio.run(run_scheduled_backups()),
            trigger=CronTrigger.from_crontab(config.backup_schedule, timezone=UTC),
            id='scheduled-backup',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        self._scheduler = scheduler

    def stop(self) -> None:
        if self._scheduler is None:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None

    def next_run_time(self) -> datetime | None:
        if self._scheduler is None:
            return compute_next_backup_run()
        job = self._scheduler.get_job('scheduled-backup')
        return job.next_run_time if job is not None else None


_SCHEDULER = BackupSchedulerRuntime()


def get_backup_scheduler() -> BackupSchedulerRuntime:
    return _SCHEDULER
