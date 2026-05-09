from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZipFile

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import AsyncSessionLocal, engine
from backend.models import (
    Assignment,
    AssignmentCategory,
    AssignmentRecurrence,
    AssignmentStatus,
    AssignmentTarget,
    AssignmentTargetStatus,
    AttendanceExcuse,
    AttendanceRecord,
    AttendanceStatus,
    BackupDestination,
    BackupJob,
    BackupJobStatus,
    BackupType,
    ExportEntityType,
    Grade,
    GradedBy,
    NotificationType,
    SubjectGradingMode,
    Student,
    Subject,
    Submission,
)
from backend.schemas.restore import RestoreExecutionRead, RestoreValidationCheckRead, RestoreValidationRead
from backend.services.backup_service import _backup_target_path, _directory_size, create_backup_job, resolve_backup_destination
from backend.services.notifications import FAMILY_MANAGER_ROLES, create_family_notifications

logger = logging.getLogger(__name__)
_VALIDATION_TTL = timedelta(minutes=15)


@dataclass(slots=True)
class BackupArtifact:
    backup_id: str
    label: str
    path: Path
    destination: BackupDestination
    backup_type: BackupType | None
    storage_mode: str
    created_at: datetime | None
    completed_at: datetime | None
    size_bytes: int
    manifest: dict[str, Any] | None
    available_entities: list[ExportEntityType]
    metadata: dict[str, Any]


@dataclass(slots=True)
class ValidationSession:
    token: str
    backup_id: str
    family_id: int
    user_id: int
    expires_at: datetime


_VALIDATIONS: dict[str, ValidationSession] = {}


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _target_root() -> Path | None:
    return _backup_target_path(settings)


def get_retention_policy() -> dict[str, int]:
    return {
        'retention_days': max(1, int(settings.backup_retention_days)),
        'retention_count': max(1, int(settings.backup_retention_count)),
    }


def update_retention_policy(*, retention_days: int, retention_count: int) -> dict[str, int]:
    settings.backup_retention_days = max(1, retention_days)
    settings.backup_retention_count = max(1, retention_count)
    os.environ['BACKUP_RETENTION_DAYS'] = str(settings.backup_retention_days)
    os.environ['BACKUP_RETENTION_COUNT'] = str(settings.backup_retention_count)
    return get_retention_policy()


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        logger.warning('Unable to read backup manifest from %s', path, exc_info=True)
        return None


def _manifest_entities(manifest: dict[str, Any] | None) -> list[ExportEntityType]:
    if not manifest:
        return []
    entity_values = manifest.get('contents', {}).get('export', {}).get('entity_counts', {})
    entities: list[ExportEntityType] = []
    for raw in entity_values:
        try:
            entities.append(ExportEntityType(raw))
        except ValueError:
            continue
    return entities


def _coerce_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _artifact_from_directory(path: Path) -> BackupArtifact | None:
    manifest_path = path / 'manifest.json'
    manifest = _read_manifest(manifest_path) if manifest_path.exists() else None
    if manifest is None:
        return None
    metadata = {
        'family_id': manifest.get('family_id'),
        'user_id': manifest.get('user_id'),
        'version': manifest.get('version'),
    }
    raw_backup_id = manifest.get('backup_id')
    backup_id = str(raw_backup_id if raw_backup_id is not None else path.name)
    raw_backup_type = manifest.get('backup_type')
    backup_type = BackupType(raw_backup_type) if raw_backup_type in BackupType._value2member_map_ else None
    destination = resolve_backup_destination()
    raw_destination = manifest.get('destination')
    if raw_destination in BackupDestination._value2member_map_:
        destination = BackupDestination(raw_destination)
    return BackupArtifact(
        backup_id=backup_id,
        label=path.name,
        path=path,
        destination=destination,
        backup_type=backup_type,
        storage_mode=str(manifest.get('storage_mode') or 'plain_copy'),
        created_at=_coerce_datetime(manifest.get('created_at')),
        completed_at=_coerce_datetime(manifest.get('completed_at')),
        size_bytes=int(manifest.get('size_bytes') or 0),
        manifest=manifest,
        available_entities=_manifest_entities(manifest),
        metadata=metadata,
    )


async def list_available_backups(db: AsyncSession, *, family_id: int) -> list[BackupArtifact]:
    target = _target_root()
    if target is None or not target.exists():
        return []

    known_job_ids = {
        str(job.id)
        for job in (
            await db.execute(select(BackupJob.id).where(BackupJob.family_id == family_id))
        ).scalars()
    }
    artifacts: list[BackupArtifact] = []
    for item in target.iterdir():
        if not item.is_dir() or item.name.startswith('.') or item.name in {'_staging', 'restic-repo', 'manifests'}:
            continue
        artifact = _artifact_from_directory(item)
        if artifact is None:
            continue
        manifest_family_id = artifact.metadata.get('family_id')
        if manifest_family_id not in {None, family_id} and artifact.backup_id not in known_job_ids:
            continue
        artifacts.append(artifact)
    artifacts.sort(key=lambda item: item.completed_at or item.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    return artifacts


async def get_backup_artifact(db: AsyncSession, *, family_id: int, backup_id: str) -> BackupArtifact | None:
    for artifact in await list_available_backups(db, family_id=family_id):
        if artifact.backup_id == backup_id or artifact.label == backup_id:
            return artifact
    return None


def _artifact_component_path(artifact: BackupArtifact, category: str, manifest_entry: dict[str, Any] | None) -> Path | None:
    if manifest_entry is None:
        return None
    raw_path = manifest_entry.get('path')
    if isinstance(raw_path, str) and raw_path:
        normalized = Path(raw_path.replace('\\', '/'))
        if not normalized.is_absolute():
            return artifact.path / normalized
        if category == 'database':
            return artifact.path / 'database' / normalized.name
        if category == 'files':
            return artifact.path / 'files' / normalized.name
        if category == 'export':
            return artifact.path / 'exports' / normalized.name
    if category == 'database':
        for candidate in sorted((artifact.path / 'database').glob('*')):
            if candidate.is_file():
                return candidate
    if category == 'files':
        uploads_path = artifact.path / 'files' / 'uploads'
        return uploads_path if uploads_path.exists() else None
    if category == 'export':
        for candidate in sorted((artifact.path / 'exports').glob('*.zip')):
            if candidate.is_file():
                return candidate
    return None


def _store_validation(backup_id: str, *, family_id: int, user_id: int) -> ValidationSession:
    token = uuid4().hex
    session = ValidationSession(
        token=token,
        backup_id=backup_id,
        family_id=family_id,
        user_id=user_id,
        expires_at=_now_utc() + _VALIDATION_TTL,
    )
    _VALIDATIONS[token] = session
    return session


def _consume_validation(token: str, *, backup_id: str, family_id: int, user_id: int) -> ValidationSession:
    session = _VALIDATIONS.get(token)
    if session is None or session.backup_id != backup_id or session.family_id != family_id or session.user_id != user_id:
        raise ValueError('Restore confirmation is invalid or expired.')
    if session.expires_at <= _now_utc():
        _VALIDATIONS.pop(token, None)
        raise ValueError('Restore confirmation has expired. Validate the backup again.')
    _VALIDATIONS.pop(token, None)
    return session


async def validate_backup(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    backup_id: str,
) -> RestoreValidationRead:
    artifact = await get_backup_artifact(db, family_id=family_id, backup_id=backup_id)
    if artifact is None:
        return RestoreValidationRead(
            backup_id=backup_id,
            valid=False,
            can_restore=False,
            checks=[RestoreValidationCheckRead(name='backup', valid=False, message='Backup was not found in the configured backup target.')],
        )

    checks: list[RestoreValidationCheckRead] = []
    warnings: list[str] = []
    manifest = artifact.manifest
    if manifest is None:
        checks.append(
            RestoreValidationCheckRead(name='manifest', valid=False, message='Backup manifest is missing or unreadable.')
        )
        return RestoreValidationRead(
            backup_id=artifact.backup_id,
            valid=False,
            can_restore=False,
            checks=checks,
            metadata=artifact.metadata,
        )

    checks.append(
        RestoreValidationCheckRead(
            name='manifest',
            valid=True,
            actual=manifest.get('version'),
            message='Backup manifest is present.',
        )
    )

    database_entry = manifest.get('contents', {}).get('database')
    export_entry = manifest.get('contents', {}).get('export')
    files_entry = manifest.get('contents', {}).get('files')

    database_path = _artifact_component_path(artifact, 'database', database_entry if isinstance(database_entry, dict) else None)
    export_path = _artifact_component_path(artifact, 'export', export_entry if isinstance(export_entry, dict) else None)
    files_path = _artifact_component_path(artifact, 'files', files_entry if isinstance(files_entry, dict) else None)

    for name, entry, resolved_path in (
        ('database', database_entry, database_path),
        ('export', export_entry, export_path),
    ):
        if not isinstance(entry, dict):
            checks.append(RestoreValidationCheckRead(name=name, valid=False, message=f'{name.title()} entry is missing from the manifest.'))
            continue
        expected_size = int(entry.get('size_bytes') or 0)
        actual_size = resolved_path.stat().st_size if resolved_path and resolved_path.exists() and resolved_path.is_file() else None
        valid = actual_size is not None and actual_size == expected_size
        checks.append(
            RestoreValidationCheckRead(
                name=name,
                valid=valid,
                expected=expected_size,
                actual=actual_size,
                message=f'{name.title()} payload size matches the manifest.' if valid else f'{name.title()} payload is missing or size does not match the manifest.',
            )
        )

    if not isinstance(files_entry, dict):
        checks.append(RestoreValidationCheckRead(name='files', valid=False, message='Files entry is missing from the manifest.'))
    else:
        expected_size = int(files_entry.get('size_bytes') or 0)
        actual_size = _directory_size(files_path) if files_path and files_path.exists() and files_path.is_dir() else None
        valid = actual_size is not None and actual_size == expected_size
        checks.append(
            RestoreValidationCheckRead(
                name='files',
                valid=valid,
                expected=expected_size,
                actual=actual_size,
                message='Uploads archive size matches the manifest.' if valid else 'Uploads archive is missing or size does not match the manifest.',
            )
        )

    if artifact.storage_mode != 'plain_copy':
        warnings.append(f"Storage mode '{artifact.storage_mode}' is not restorable by the in-app restore flow.")

    if export_path and export_path.exists():
        try:
            with ZipFile(export_path) as archive:
                export_valid = 'family-export.json' in archive.namelist()
        except Exception:
            export_valid = False
        checks.append(
            RestoreValidationCheckRead(
                name='export_package',
                valid=export_valid,
                message='Selective export package is available.' if export_valid else 'Selective export package is unreadable.',
            )
        )

    if make_url(settings.database_url).drivername.startswith('postgresql'):
        checks.append(
            RestoreValidationCheckRead(
                name='pg_restore',
                valid=shutil.which('pg_restore') is not None,
                message='pg_restore is available.' if shutil.which('pg_restore') else 'pg_restore is required for PostgreSQL restores.',
            )
        )

    valid = all(check.valid for check in checks)
    can_restore = valid and artifact.storage_mode == 'plain_copy'
    confirmation = _store_validation(artifact.backup_id, family_id=family_id, user_id=user_id) if can_restore else None
    return RestoreValidationRead(
        backup_id=artifact.backup_id,
        valid=valid,
        can_restore=can_restore,
        confirmation_token=confirmation.token if confirmation else None,
        expires_at=confirmation.expires_at if confirmation else None,
        checks=checks,
        warnings=warnings,
        metadata={
            **artifact.metadata,
            'available_entities': [entity.value for entity in artifact.available_entities],
            'size_bytes': artifact.size_bytes,
        },
    )


async def cleanup_retained_backups() -> dict[str, Any]:
    target = _target_root()
    policy = get_retention_policy()
    result = {'retention_days': policy['retention_days'], 'retention_count': policy['retention_count'], 'deleted': [], 'kept': []}
    if target is None or not target.exists():
        return result

    artifacts = [artifact for artifact in ([_artifact_from_directory(item) for item in target.iterdir() if item.is_dir()]) if artifact]
    artifacts.sort(key=lambda item: item.completed_at or item.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    protected = {artifact.path for artifact in artifacts[: policy['retention_count']]}
    cutoff = _now_utc() - timedelta(days=policy['retention_days'])

    for artifact in artifacts:
        modified_at = datetime.fromtimestamp(artifact.path.stat().st_mtime, tz=UTC)
        if artifact.path in protected or modified_at >= cutoff:
            result['kept'].append(artifact.label)
            continue
        shutil.rmtree(artifact.path, ignore_errors=True)
        result['deleted'].append(artifact.label)
    return result


async def _create_safety_snapshot(*, family_id: int, user_id: int) -> BackupJob:
    async with AsyncSessionLocal() as db:
        job = await create_backup_job(db, family_id=family_id, user_id=user_id, backup_type=BackupType.manual)
        await db.commit()
        job_id = job.id
    from backend.services.backup_service import _run_backup_job

    await _run_backup_job(job_id)
    async with AsyncSessionLocal() as db:
        refreshed = await db.get(BackupJob, job_id)
        if refreshed is None or refreshed.status != BackupJobStatus.complete:
            message = refreshed.error_message if refreshed is not None else 'Safety snapshot did not complete.'
            raise RuntimeError(message or 'Safety snapshot failed.')
        return refreshed


async def _restore_database_from_artifact(artifact: BackupArtifact) -> None:
    manifest = artifact.manifest or {}
    database_entry = manifest.get('contents', {}).get('database')
    database_path = _artifact_component_path(artifact, 'database', database_entry if isinstance(database_entry, dict) else None)
    if database_path is None or not database_path.exists():
        raise RuntimeError('Database backup file is missing from the backup artifact.')

    url = make_url(settings.database_url)
    if url.drivername.startswith('sqlite'):
        destination = Path(url.database or '')
        if not destination.is_absolute():
            destination = Path.cwd() / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        await engine.dispose()
        source_connection = sqlite3.connect(database_path)
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
            source_connection.close()
        return

    pg_restore = shutil.which('pg_restore')
    if not pg_restore:
        raise RuntimeError('pg_restore is required for PostgreSQL restores.')
    env = {**os.environ, 'PGPASSWORD': url.password or ''}
    command = [
        pg_restore,
        '--clean',
        '--if-exists',
        '--no-owner',
        '--no-privileges',
        '--host',
        str(url.host or 'localhost'),
        '--port',
        str(url.port or 5432),
        '--username',
        str(url.username or settings.postgres_user),
        '--dbname',
        str(url.database or settings.postgres_db),
        str(database_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or 'pg_restore failed')


def _restore_uploads_from_artifact(artifact: BackupArtifact) -> None:
    manifest = artifact.manifest or {}
    files_entry = manifest.get('contents', {}).get('files')
    files_path = _artifact_component_path(artifact, 'files', files_entry if isinstance(files_entry, dict) else None)
    if files_path is None or not files_path.exists():
        raise RuntimeError('Uploads payload is missing from the backup artifact.')
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    for item in upload_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)
    for source in files_path.iterdir():
        destination = upload_dir / source.name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)


def _load_export_package(artifact: BackupArtifact) -> tuple[dict[str, Any], ZipFile]:
    manifest = artifact.manifest or {}
    export_entry = manifest.get('contents', {}).get('export')
    export_path = _artifact_component_path(artifact, 'export', export_entry if isinstance(export_entry, dict) else None)
    if export_path is None or not export_path.exists():
        raise RuntimeError('Export package is missing from the backup artifact.')
    archive = ZipFile(export_path)
    try:
        package = json.loads(archive.read('family-export.json').decode('utf-8'))
    except Exception:
        archive.close()
        raise RuntimeError('family-export.json is missing from the export package.') from None
    return package, archive


def _safe_decimal(value: Any) -> Decimal:
    return Decimal(str(value if value is not None else 0))


async def _ensure_student_records(db: AsyncSession, *, family_id: int, students_payload: list[dict[str, Any]], overwrite_existing: bool) -> tuple[dict[str, Student], dict[str, int]]:
    existing = {
        student.name.strip().lower(): student
        for student in (await db.execute(select(Student).where(Student.family_id == family_id))).scalars()
    }
    counts = {'created': 0, 'updated': 0, 'skipped': 0}
    mapped: dict[str, Student] = {}
    for payload in students_payload:
        name = str(payload.get('name') or '').strip()
        if not name:
            continue
        key = name.lower()
        student = existing.get(key)
        if student is None:
            student = Student(family_id=family_id, name=name)
            db.add(student)
            await db.flush()
            existing[key] = student
            counts['created'] += 1
        elif overwrite_existing and student.name != name:
            student.name = name
            counts['updated'] += 1
        else:
            counts['skipped'] += 1
        mapped[key] = student
    return mapped, counts


async def _ensure_subject_records(db: AsyncSession, *, family_id: int, subjects_payload: list[dict[str, Any]], overwrite_existing: bool) -> tuple[dict[str, Subject], dict[str, int]]:
    existing = {
        subject.name.strip().lower(): subject
        for subject in (await db.execute(select(Subject).where(Subject.family_id == family_id))).scalars()
    }
    counts = {'created': 0, 'updated': 0, 'skipped': 0}
    mapped: dict[str, Subject] = {}
    for payload in subjects_payload:
        name = str(payload.get('name') or '').strip()
        if not name:
            continue
        key = name.lower()
        subject = existing.get(key)
        if subject is None:
            subject = Subject(
                family_id=family_id,
                name=name,
                color=str(payload.get('color') or '#4f46e5'),
                grading_mode=SubjectGradingMode(str(payload.get('grading_mode') or SubjectGradingMode.points.value)),
                grade_scale_id=payload.get('grade_scale_id'),
            )
            db.add(subject)
            await db.flush()
            existing[key] = subject
            counts['created'] += 1
        elif overwrite_existing:
            subject.color = str(payload.get('color') or subject.color)
            subject.grading_mode = SubjectGradingMode(str(payload.get('grading_mode') or subject.grading_mode.value))
            subject.grade_scale_id = payload.get('grade_scale_id')
            counts['updated'] += 1
        else:
            counts['skipped'] += 1
        mapped[key] = subject
    return mapped, counts


async def _ensure_assignments(
    db: AsyncSession,
    *,
    family_id: int,
    assignments_payload: list[dict[str, Any]],
    students: dict[str, Student],
    subjects: dict[str, Subject],
    overwrite_existing: bool,
) -> tuple[dict[tuple[str, str], Assignment], dict[str, int]]:
    existing_assignments = list(
        (
            await db.execute(
                select(Assignment)
                .options(selectinload(Assignment.subject), selectinload(Assignment.targets))
                .where(Assignment.family_id == family_id)
            )
        ).scalars()
    )
    by_key = {(assignment.title.strip().lower(), assignment.subject.name.strip().lower() if assignment.subject else ''): assignment for assignment in existing_assignments}
    counts = {'created': 0, 'updated': 0, 'skipped': 0}
    mapped: dict[tuple[str, str], Assignment] = {}
    for payload in assignments_payload:
        title = str(payload.get('title') or '').strip()
        subject_name = str(payload.get('subject_name') or '').strip().lower()
        subject = subjects.get(subject_name)
        if not title or subject is None:
            continue
        key = (title.lower(), subject_name)
        assignment = by_key.get(key)
        if assignment is None:
            assignment = Assignment(
                family_id=family_id,
                title=title,
                subject_id=subject.id,
                description=payload.get('description'),
                due_date=datetime.fromisoformat(str(payload['due_date']).replace('Z', '+00:00')) if payload.get('due_date') else None,
                status=AssignmentStatus(str(payload.get('status') or AssignmentStatus.pending.value)),
                category=AssignmentCategory(str(payload.get('category') or AssignmentCategory.homework.value)),
                grading_period_id=payload.get('grading_period_id'),
                weight=float(payload.get('weight') or 1),
                max_score=float(payload.get('max_score') or 100),
                recurrence=AssignmentRecurrence(str(payload.get('recurrence') or AssignmentRecurrence.none.value)),
                recurrence_end_date=datetime.fromisoformat(str(payload['recurrence_end_date'])).date() if payload.get('recurrence_end_date') else None,
                rubric_description=payload.get('rubric_description'),
                attachments=list(payload.get('attachments') or []),
                status_history=list(payload.get('status_history') or []),
            )
            db.add(assignment)
            await db.flush()
            counts['created'] += 1
        elif overwrite_existing:
            assignment.description = payload.get('description')
            assignment.due_date = datetime.fromisoformat(str(payload['due_date']).replace('Z', '+00:00')) if payload.get('due_date') else None
            assignment.status = AssignmentStatus(str(payload.get('status') or assignment.status.value))
            assignment.category = AssignmentCategory(str(payload.get('category') or assignment.category.value))
            assignment.weight = float(payload.get('weight') or assignment.weight)
            assignment.max_score = float(payload.get('max_score') or assignment.max_score)
            assignment.recurrence = AssignmentRecurrence(str(payload.get('recurrence') or assignment.recurrence.value))
            assignment.recurrence_end_date = datetime.fromisoformat(str(payload['recurrence_end_date'])).date() if payload.get('recurrence_end_date') else None
            assignment.rubric_description = payload.get('rubric_description')
            assignment.attachments = list(payload.get('attachments') or [])
            assignment.status_history = list(payload.get('status_history') or [])
            counts['updated'] += 1
        else:
            counts['skipped'] += 1
        for target_payload in payload.get('targets') or []:
            student_name = str(target_payload.get('student_name') or '').strip().lower()
            student = students.get(student_name)
            if student is None:
                continue
            existing_target = (
                await db.execute(
                    select(AssignmentTarget).where(
                        AssignmentTarget.assignment_id == assignment.id,
                        AssignmentTarget.student_id == student.id,
                    )
                )
            ).scalar_one_or_none()
            if existing_target is None:
                db.add(
                    AssignmentTarget(
                        assignment_id=assignment.id,
                        student_id=student.id,
                        due_date=datetime.fromisoformat(str(target_payload['due_date']).replace('Z', '+00:00')) if target_payload.get('due_date') else None,
                        status=AssignmentTargetStatus(str(target_payload.get('status') or AssignmentTargetStatus.assigned.value)),
                        completed_at=datetime.fromisoformat(str(target_payload['completed_at']).replace('Z', '+00:00')) if target_payload.get('completed_at') else None,
                    )
                )
            elif overwrite_existing:
                existing_target.due_date = datetime.fromisoformat(str(target_payload['due_date']).replace('Z', '+00:00')) if target_payload.get('due_date') else None
                existing_target.status = AssignmentTargetStatus(str(target_payload.get('status') or existing_target.status.value))
                existing_target.completed_at = datetime.fromisoformat(str(target_payload['completed_at']).replace('Z', '+00:00')) if target_payload.get('completed_at') else None
        mapped[key] = assignment
    await db.flush()
    return mapped, counts


async def _ensure_submissions(
    db: AsyncSession,
    *,
    family_id: int,
    submissions_payload: list[dict[str, Any]],
    archive: ZipFile,
    students: dict[str, Student],
    assignments: dict[tuple[str, str], Assignment],
    overwrite_existing: bool,
) -> tuple[dict[tuple[int, int], Submission], dict[str, int]]:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    existing_submissions = list((await db.execute(select(Submission).where(Submission.family_id == family_id))).scalars())
    by_key = {(submission.assignment_id, submission.student_id): submission for submission in existing_submissions if submission.is_current}
    counts = {'created': 0, 'updated': 0, 'skipped': 0}
    mapped: dict[tuple[int, int], Submission] = {}
    names = set(archive.namelist())
    for payload in submissions_payload:
        student_name = str(payload.get('student_name') or '').strip().lower()
        assignment_title = str(payload.get('assignment_title') or '').strip().lower()
        matching_assignment = None
        for candidate_key, candidate in assignments.items():
            if candidate_key[0] == assignment_title:
                matching_assignment = candidate
                break
        student = students.get(student_name)
        if matching_assignment is None or student is None:
            continue
        key = (matching_assignment.id, student.id)
        submission = by_key.get(key)
        file_path_value = str(payload.get('file_path') or '')
        archive_member = None
        if file_path_value:
            relative = Path(file_path_value.replace('\\', '/'))
            archive_member = str(Path('attachments') / relative).replace('\\', '/')
        destination_relative = Path(file_path_value.replace('\\', '/')) if file_path_value else Path('restored') / f'assignment-{matching_assignment.id}' / f'student-{student.id}.txt'
        destination = upload_dir / destination_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if archive_member and archive_member in names:
            destination.write_bytes(archive.read(archive_member))
        elif not destination.exists():
            destination.write_text('Selective restore placeholder submission', encoding='utf-8')
        if submission is None:
            submission = Submission(
                family_id=family_id,
                assignment_id=matching_assignment.id,
                student_id=student.id,
                file_path=str(destination_relative).replace('\\', '/'),
                original_filename=str(payload.get('original_filename') or destination.name),
                file_name=str(payload.get('file_name') or destination.name),
                file_type=str(payload.get('file_type') or 'text/plain'),
                file_size_bytes=int(destination.stat().st_size),
                image_width=payload.get('image_width'),
                image_height=payload.get('image_height'),
                page_count=payload.get('page_count'),
                submission_version=int(payload.get('submission_version') or 1),
                parent_submission_id=None,
                is_current=bool(payload.get('is_current', True)),
                ocr_text=payload.get('ocr_text'),
            )
            db.add(submission)
            await db.flush()
            counts['created'] += 1
        elif overwrite_existing:
            submission.file_path = str(destination_relative).replace('\\', '/')
            submission.original_filename = str(payload.get('original_filename') or submission.original_filename)
            submission.file_name = str(payload.get('file_name') or submission.file_name)
            submission.file_type = str(payload.get('file_type') or submission.file_type)
            submission.file_size_bytes = int(destination.stat().st_size)
            submission.ocr_text = payload.get('ocr_text')
            counts['updated'] += 1
        else:
            counts['skipped'] += 1
        mapped[key] = submission
    return mapped, counts


async def _ensure_grades(
    db: AsyncSession,
    *,
    family_id: int,
    grades_payload: list[dict[str, Any]],
    students: dict[str, Student],
    assignments: dict[tuple[str, str], Assignment],
    submissions: dict[tuple[int, int], Submission],
    overwrite_existing: bool,
) -> dict[str, int]:
    existing_grades = {
        grade.submission_id: grade for grade in (await db.execute(select(Grade).where(Grade.family_id == family_id))).scalars()
    }
    counts = {'created': 0, 'updated': 0, 'skipped': 0}
    for payload in grades_payload:
        student = students.get(str(payload.get('student_name') or '').strip().lower())
        if student is None:
            continue
        assignment_title = str(payload.get('assignment_title') or '').strip().lower()
        subject_name = str(payload.get('subject_name') or '').strip().lower()
        assignment = assignments.get((assignment_title, subject_name))
        if assignment is None:
            continue
        submission = submissions.get((assignment.id, student.id))
        if submission is None:
            continue
        grade = existing_grades.get(submission.id)
        if grade is None:
            grade = Grade(
                family_id=family_id,
                submission_id=submission.id,
                student_id=student.id,
                score=float(payload.get('score') or 0),
                max_score=float(payload.get('max_score') or 100),
                letter_grade=payload.get('letter_grade'),
                notes=payload.get('notes'),
                graded_by=GradedBy(str(payload.get('graded_by') or GradedBy.human.value)),
                ai_confidence=payload.get('ai_confidence'),
            )
            db.add(grade)
            counts['created'] += 1
            existing_grades[submission.id] = grade
        elif overwrite_existing:
            grade.score = float(payload.get('score') or grade.score)
            grade.max_score = float(payload.get('max_score') or grade.max_score)
            grade.letter_grade = payload.get('letter_grade')
            grade.notes = payload.get('notes')
            grade.graded_by = GradedBy(str(payload.get('graded_by') or grade.graded_by.value))
            grade.ai_confidence = payload.get('ai_confidence')
            counts['updated'] += 1
        else:
            counts['skipped'] += 1
    return counts


async def _ensure_attendance(
    db: AsyncSession,
    *,
    family_id: int,
    attendance_payload: list[dict[str, Any]],
    students: dict[str, Student],
    archive: ZipFile,
    overwrite_existing: bool,
) -> dict[str, int]:
    names = set(archive.namelist())
    existing = {
        (record.student_id, record.date.isoformat()): record
        for record in (await db.execute(select(AttendanceRecord).where(AttendanceRecord.family_id == family_id))).scalars()
    }
    counts = {'created': 0, 'updated': 0, 'skipped': 0}
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    for payload in attendance_payload:
        student = students.get(str(payload.get('student_name') or '').strip().lower())
        date_value = str(payload.get('date') or '')
        if student is None or not date_value:
            continue
        key = (student.id, date_value)
        record = existing.get(key)
        check_in = payload.get('check_in_time')
        check_out = payload.get('check_out_time')
        excuse_payload = payload.get('excuse') if isinstance(payload.get('excuse'), dict) else None
        if record is None:
            record = AttendanceRecord(
                family_id=family_id,
                student_id=student.id,
                date=date.fromisoformat(date_value),
                status=AttendanceStatus(str(payload.get('status') or AttendanceStatus.present.value)),
                check_in_time=time.fromisoformat(check_in) if check_in else None,
                check_out_time=time.fromisoformat(check_out) if check_out else None,
                instructional_hours=_safe_decimal(payload.get('instructional_hours')),
                notes=payload.get('notes'),
            )
            db.add(record)
            await db.flush()
            counts['created'] += 1
            existing[key] = record
        elif overwrite_existing:
            record.status = AttendanceStatus(str(payload.get('status') or record.status.value))
            record.check_in_time = time.fromisoformat(check_in) if check_in else None
            record.check_out_time = time.fromisoformat(check_out) if check_out else None
            record.instructional_hours = _safe_decimal(payload.get('instructional_hours'))
            record.notes = payload.get('notes')
            counts['updated'] += 1
        else:
            counts['skipped'] += 1
        if excuse_payload:
            if record.excuse is None:
                record.excuse = AttendanceExcuse(
                    family_id=family_id,
                    reason=str(excuse_payload.get('reason') or 'Restored excuse'),
                    document_path=None,
                    approved_by_user_id=excuse_payload.get('approved_by_user_id'),
                    approved_at=_coerce_datetime(excuse_payload.get('approved_at')),
                )
            document_path = excuse_payload.get('document_path')
            if document_path:
                member = str(Path('attachments') / Path(str(document_path).replace('\\', '/'))).replace('\\', '/')
                if member in names:
                    relative = Path(str(document_path).replace('\\', '/'))
                    destination = upload_dir / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(member))
                    record.excuse.document_path = str(relative).replace('\\', '/')
    return counts


async def selective_restore(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    backup_id: str,
    confirmation_token: str,
    entity_types: list[ExportEntityType],
    overwrite_existing: bool,
    auto_backup: bool,
) -> RestoreExecutionRead:
    artifact = await get_backup_artifact(db, family_id=family_id, backup_id=backup_id)
    if artifact is None:
        raise ValueError('Backup was not found.')
    _consume_validation(confirmation_token, backup_id=artifact.backup_id, family_id=family_id, user_id=user_id)
    safety_snapshot = await _create_safety_snapshot(family_id=family_id, user_id=user_id) if auto_backup else None

    package, archive = _load_export_package(artifact)
    try:
        requested = set(entity_types)
        if ExportEntityType.grades in requested:
            requested.update({ExportEntityType.students, ExportEntityType.subjects, ExportEntityType.assignments, ExportEntityType.submissions})
        if ExportEntityType.submissions in requested:
            requested.update({ExportEntityType.students, ExportEntityType.subjects, ExportEntityType.assignments})
        if ExportEntityType.assignments in requested:
            requested.update({ExportEntityType.students, ExportEntityType.subjects})
        if ExportEntityType.attendance in requested:
            requested.add(ExportEntityType.students)

        restored: dict[str, dict[str, int]] = {}
        students: dict[str, Student] = {}
        subjects: dict[str, Subject] = {}
        assignments: dict[tuple[str, str], Assignment] = {}
        submissions: dict[tuple[int, int], Submission] = {}

        if ExportEntityType.students in requested:
            students, restored['students'] = await _ensure_student_records(
                db, family_id=family_id, students_payload=list(package.get('students') or []), overwrite_existing=overwrite_existing
            )
        else:
            students = {
                student.name.strip().lower(): student
                for student in (await db.execute(select(Student).where(Student.family_id == family_id))).scalars()
            }
        if ExportEntityType.subjects in requested:
            subjects, restored['subjects'] = await _ensure_subject_records(
                db, family_id=family_id, subjects_payload=list(package.get('subjects') or []), overwrite_existing=overwrite_existing
            )
        else:
            subjects = {
                subject.name.strip().lower(): subject
                for subject in (await db.execute(select(Subject).where(Subject.family_id == family_id))).scalars()
            }
        if ExportEntityType.assignments in requested:
            assignments, restored['assignments'] = await _ensure_assignments(
                db,
                family_id=family_id,
                assignments_payload=list(package.get('assignments') or []),
                students=students,
                subjects=subjects,
                overwrite_existing=overwrite_existing,
            )
        if ExportEntityType.submissions in requested:
            submissions, restored['submissions'] = await _ensure_submissions(
                db,
                family_id=family_id,
                submissions_payload=list(package.get('submissions') or []),
                archive=archive,
                students=students,
                assignments=assignments,
                overwrite_existing=overwrite_existing,
            )
        if ExportEntityType.grades in requested:
            restored['grades'] = await _ensure_grades(
                db,
                family_id=family_id,
                grades_payload=list(package.get('grades') or []),
                students=students,
                assignments=assignments,
                submissions=submissions,
                overwrite_existing=overwrite_existing,
            )
        if ExportEntityType.attendance in requested:
            restored['attendance'] = await _ensure_attendance(
                db,
                family_id=family_id,
                attendance_payload=list(package.get('attendance') or []),
                students=students,
                archive=archive,
                overwrite_existing=overwrite_existing,
            )

        await db.commit()
    finally:
        archive.close()

    return RestoreExecutionRead(
        backup_id=artifact.backup_id,
        mode='selective',
        restored_entities=restored,
        safety_snapshot_job_id=safety_snapshot.id if safety_snapshot else None,
        completed_at=_now_utc(),
        message='Selective restore completed successfully.',
    )


async def execute_restore(
    db: AsyncSession,
    *,
    family_id: int,
    user_id: int,
    backup_id: str,
    confirmation_token: str,
    include_database: bool,
    include_files: bool,
    auto_backup: bool,
) -> RestoreExecutionRead:
    artifact = await get_backup_artifact(db, family_id=family_id, backup_id=backup_id)
    if artifact is None:
        raise ValueError('Backup was not found.')
    _consume_validation(confirmation_token, backup_id=artifact.backup_id, family_id=family_id, user_id=user_id)
    safety_snapshot = await _create_safety_snapshot(family_id=family_id, user_id=user_id) if auto_backup else None
    if include_database:
        await _restore_database_from_artifact(artifact)
    if include_files:
        _restore_uploads_from_artifact(artifact)
    return RestoreExecutionRead(
        backup_id=artifact.backup_id,
        mode='full',
        restored_database=include_database,
        restored_files=include_files,
        safety_snapshot_job_id=safety_snapshot.id if safety_snapshot else None,
        completed_at=_now_utc(),
        message='Restore completed successfully.',
    )


async def notify_restore_result(*, family_id: int, success: bool, message: str) -> None:
    async with AsyncSessionLocal() as db:
        await create_family_notifications(
            db,
            family_id=family_id,
            notification_type=NotificationType.backup_status,
            title='Restore completed successfully' if success else 'Restore failed',
            message=message,
            link='/settings/restore',
            roles=FAMILY_MANAGER_ROLES,
            suppress_duplicates_for=timedelta(minutes=5),
        )
        await db.commit()
