from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import AuditAction, AuditEvent, BackupJob, Notification, NotificationType, Student
from tests.contracts import RESTORE


def _current_test_database() -> Path:
    raw = settings.database_url.replace('sqlite+aiosqlite:///', '')
    return Path(raw)


def _write_artifact(
    root: Path,
    *,
    backup_id: str,
    family_id: int,
    user_id: int,
    student_name: str = 'Restore Student',
    include_grade_payload: bool = False,
    mismatch_database_size: bool = False,
) -> Path:
    artifact_dir = root / backup_id
    database_dir = artifact_dir / 'database'
    files_dir = artifact_dir / 'files' / 'uploads'
    exports_dir = artifact_dir / 'exports'
    database_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    database_source = _current_test_database()
    database_target = database_dir / 'database.sqlite3'
    shutil.copy2(database_source, database_target)

    restored_upload = files_dir / 'restored-upload.txt'
    restored_upload.write_text('restored file', encoding='utf-8')

    package: dict[str, object] = {
        'metadata': {
            'entity_counts': {'students': 1},
            'entity_types': ['students'] if not include_grade_payload else ['students', 'subjects', 'assignments', 'submissions', 'grades'],
        },
        'students': [{'id': 101, 'name': student_name}],
    }
    attachments: dict[str, bytes] = {}
    if include_grade_payload:
        package.update(
            {
                'subjects': [{'id': 201, 'name': 'Mathematics', 'color': '#2563eb', 'grading_mode': 'points', 'grade_scale_id': None}],
                'assignments': [
                    {
                        'id': 301,
                        'title': 'Selective Restore Worksheet',
                        'subject_id': 201,
                        'subject_name': 'Mathematics',
                        'description': 'Restored assignment',
                        'due_date': '2026-05-09T00:00:00+00:00',
                        'status': 'pending',
                        'category': 'homework',
                        'grading_period_id': None,
                        'weight': 1,
                        'max_score': 100,
                        'recurrence': 'none',
                        'recurrence_end_date': None,
                        'rubric_description': None,
                        'attachments': [],
                        'status_history': [],
                        'targets': [
                            {
                                'id': 401,
                                'student_id': 101,
                                'student_name': student_name,
                                'due_date': '2026-05-09T00:00:00+00:00',
                                'status': 'assigned',
                                'completed_at': None,
                            }
                        ],
                    }
                ],
                'submissions': [
                    {
                        'id': 501,
                        'assignment_id': 301,
                        'assignment_title': 'Selective Restore Worksheet',
                        'student_id': 101,
                        'student_name': student_name,
                        'file_path': 'restored/submission.txt',
                        'original_filename': 'submission.txt',
                        'file_name': 'submission.txt',
                        'file_type': 'text/plain',
                        'file_size_bytes': 14,
                        'image_width': None,
                        'image_height': None,
                        'page_count': None,
                        'submission_version': 1,
                        'parent_submission_id': None,
                        'is_current': True,
                        'ocr_text': 'restored answer',
                    }
                ],
                'grades': [
                    {
                        'id': 601,
                        'submission_id': 501,
                        'student_id': 101,
                        'student_name': student_name,
                        'assignment_id': 301,
                        'assignment_title': 'Selective Restore Worksheet',
                        'subject_id': 201,
                        'subject_name': 'Mathematics',
                        'score': 97,
                        'max_score': 100,
                        'letter_grade': 'A',
                        'notes': 'Restored grade',
                        'graded_by': 'human',
                        'ai_confidence': None,
                    }
                ],
            }
        )
        attachments['attachments/restored/submission.txt'] = b'restored answer'

    export_zip = exports_dir / 'family-export-restore.zip'
    with ZipFile(export_zip, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('metadata.json', json.dumps(package['metadata']).encode('utf-8'))
        archive.writestr('family-export.json', json.dumps(package).encode('utf-8'))
        for name, content in attachments.items():
            archive.writestr(name, content)

    manifest = {
        'version': '2026.05.10-dm03',
        'backup_id': backup_id,
        'family_id': family_id,
        'user_id': user_id,
        'backup_type': 'manual',
        'destination': 'local',
        'storage_mode': 'plain_copy',
        'created_at': datetime.now(UTC).isoformat(),
        'completed_at': datetime.now(UTC).isoformat(),
        'size_bytes': 0,
        'contents': {
            'database': {'path': 'database/database.sqlite3', 'size_bytes': database_target.stat().st_size + (4 if mismatch_database_size else 0)},
            'files': {'path': 'files/uploads', 'size_bytes': restored_upload.stat().st_size, 'files_copied': 1},
            'export': {
                'path': 'exports/family-export-restore.zip',
                'size_bytes': export_zip.stat().st_size,
                'entity_counts': package['metadata']['entity_counts'],
            },
        },
    }
    manifest['size_bytes'] = database_target.stat().st_size + restored_upload.stat().st_size + export_zip.stat().st_size
    (artifact_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return artifact_dir


@pytest.mark.asyncio
async def test_restore_validation_detects_manifest_size_mismatch(authorized_client, tmp_path: Path, monkeypatch) -> None:
    backup_root = tmp_path / 'backups'
    backup_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, 'backup_target', str(backup_root))

    _write_artifact(backup_root, backup_id='broken-backup', family_id=1, user_id=1, mismatch_database_size=True)

    response = await authorized_client.post(RESTORE['validate'].format(backup_id='broken-backup'))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['valid'] is False
    assert payload['can_restore'] is False
    assert payload['confirmation_token'] is None
    assert any(check['name'] == 'database' and check['valid'] is False for check in payload['checks'])


@pytest.mark.asyncio
async def test_restore_cleanup_keeps_minimum_backups(authorized_client, tmp_path: Path, monkeypatch) -> None:
    backup_root = tmp_path / 'backups'
    backup_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, 'backup_target', str(backup_root))
    monkeypatch.setattr(settings, 'backup_retention_days', 1)
    monkeypatch.setattr(settings, 'backup_retention_count', 2)

    old_one = _write_artifact(backup_root, backup_id='old-1', family_id=1, user_id=1)
    old_two = _write_artifact(backup_root, backup_id='old-2', family_id=1, user_id=1)
    keep_one = _write_artifact(backup_root, backup_id='keep-1', family_id=1, user_id=1)
    keep_two = _write_artifact(backup_root, backup_id='keep-2', family_id=1, user_id=1)
    old_timestamp = (datetime.now().timestamp() - timedelta(days=5).total_seconds(),) * 2
    for path in (old_one, old_two):
        os.utime(path, old_timestamp)

    response = await authorized_client.post(RESTORE['cleanup'])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['retention_count'] == 2
    assert 'old-1' in payload['deleted']
    assert 'old-2' in payload['deleted']
    assert 'keep-1' in payload['kept']
    assert 'keep-2' in payload['kept']


@pytest.mark.asyncio
async def test_selective_restore_creates_students_and_grades_with_safety_snapshot(authorized_client, tmp_path: Path, monkeypatch) -> None:
    backup_root = tmp_path / 'backups'
    upload_root = tmp_path / 'uploads'
    backup_root.mkdir(parents=True, exist_ok=True)
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, 'backup_target', str(backup_root))
    monkeypatch.setattr(settings, 'upload_dir', str(upload_root))
    monkeypatch.setattr(settings, 'backup_destination', 'local')

    _write_artifact(backup_root, backup_id='selective-backup', family_id=1, user_id=1, include_grade_payload=True)

    validate_response = await authorized_client.post(RESTORE['validate'].format(backup_id='selective-backup'))
    assert validate_response.status_code == 200, validate_response.text
    token = validate_response.json()['confirmation_token']
    assert token

    restore_response = await authorized_client.post(
        RESTORE['selective'].format(backup_id='selective-backup'),
        json={'confirmation_token': token, 'entity_types': ['grades'], 'overwrite_existing': False, 'auto_backup': True},
    )
    assert restore_response.status_code == 200, restore_response.text
    payload = restore_response.json()
    assert payload['mode'] == 'selective'
    assert payload['safety_snapshot_job_id'] is not None
    assert payload['restored_entities']['students']['created'] == 1
    assert payload['restored_entities']['grades']['created'] == 1
    assert (upload_root / 'restored' / 'submission.txt').exists()

    async with AsyncSessionLocal() as db:
        restored_students = (await db.execute(select(Student).where(Student.name == 'Restore Student'))).scalars().all()
        assert len(restored_students) == 1
        safety_snapshot = await db.get(BackupJob, payload['safety_snapshot_job_id'])
        assert safety_snapshot is not None
        assert safety_snapshot.status.value == 'complete'
        notifications = (
            await db.execute(select(Notification).where(Notification.type == NotificationType.backup_status))
        ).scalars().all()
        assert any(notification.link == '/settings/restore' for notification in notifications)


@pytest.mark.asyncio
async def test_restore_execute_restores_files_and_records_audit(authorized_client, tmp_path: Path, monkeypatch) -> None:
    backup_root = tmp_path / 'backups'
    upload_root = tmp_path / 'uploads'
    backup_root.mkdir(parents=True, exist_ok=True)
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, 'backup_target', str(backup_root))
    monkeypatch.setattr(settings, 'upload_dir', str(upload_root))
    monkeypatch.setattr(settings, 'backup_destination', 'local')

    _write_artifact(backup_root, backup_id='execute-backup', family_id=1, user_id=1)
    (upload_root / 'stale.txt').write_text('stale', encoding='utf-8')

    validate_response = await authorized_client.post(RESTORE['validate'].format(backup_id='execute-backup'))
    token = validate_response.json()['confirmation_token']
    assert token

    async def noop_restore_database(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr('backend.services.restore_service._restore_database_from_artifact', noop_restore_database)

    restore_response = await authorized_client.post(
        RESTORE['execute'].format(backup_id='execute-backup'),
        json={'confirmation_token': token, 'include_database': False, 'include_files': True, 'auto_backup': True},
    )
    assert restore_response.status_code == 200, restore_response.text
    payload = restore_response.json()
    assert payload['restored_files'] is True
    assert payload['safety_snapshot_job_id'] is not None
    assert (upload_root / 'restored-upload.txt').exists()
    assert not (upload_root / 'stale.txt').exists()

    async with AsyncSessionLocal() as db:
        audit_events = (
            await db.execute(select(AuditEvent).where(AuditEvent.action == AuditAction.restore))
        ).scalars().all()
        assert any(event.target_entity_type == 'restore' for event in audit_events)
