from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import Notification, NotificationType
from tests.contracts import BACKUPS, STUDENTS, student_payload


async def _wait_for_backup(client, job_id: int, *, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(BACKUPS['detail'].format(job_id=job_id))
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload['status'] in {'complete', 'failed'}:
            return payload
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail(f'Backup job {job_id} did not finish in time: {payload}')
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_manual_backup_creates_local_artifact_and_manifest(authorized_client, tmp_path: Path, monkeypatch) -> None:
    backup_dir = tmp_path / 'backups'
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / 'sample-upload.txt').write_text('backup me', encoding='utf-8')

    monkeypatch.setattr(settings, 'backup_target', str(backup_dir))
    monkeypatch.setattr(settings, 'backup_destination', 'local')
    monkeypatch.setattr(settings, 'backup_schedule', '15 3 * * *')
    monkeypatch.setattr(settings, 'backup_scheduler_enabled', True)
    monkeypatch.setattr(settings, 'backup_encryption_key', None)

    student_response = await authorized_client.post(STUDENTS['collection'], json=student_payload('Backup Student'))
    assert student_response.status_code == 201, student_response.text

    create_response = await authorized_client.post(BACKUPS['trigger'], json={'backup_type': 'manual'})
    assert create_response.status_code == 201, create_response.text

    job = await _wait_for_backup(authorized_client, create_response.json()['id'])
    assert job['status'] == 'complete'
    assert job['file_size'] > 0
    artifact_dir = Path(job['file_path'])
    assert artifact_dir.exists()
    manifest_path = artifact_dir / 'manifest.json'
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['version'] == '2026.05.10-dm03'
    assert manifest['contents']['database']['size_bytes'] > 0
    assert manifest['contents']['export']['size_bytes'] > 0
    assert manifest['contents']['files']['files_copied'] >= 1
    assert (artifact_dir / 'files' / 'uploads' / 'sample-upload.txt').exists()
    assert any(path.name.endswith('.zip') for path in (artifact_dir / 'exports').iterdir())


@pytest.mark.asyncio
async def test_backup_config_reports_nas_schedule_without_exposing_password(authorized_client, tmp_path: Path, monkeypatch) -> None:
    backup_dir = tmp_path / 'smb-backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, 'backup_target', str(backup_dir))
    monkeypatch.setattr(settings, 'backup_destination', 'smb')
    monkeypatch.setattr(settings, 'backup_schedule', '0 2 * * *')
    monkeypatch.setattr(settings, 'backup_smb_host', 'nas.local')
    monkeypatch.setattr(settings, 'backup_smb_share', 'homeschool')
    monkeypatch.setattr(settings, 'backup_smb_user', 'backup-user')
    monkeypatch.setattr(settings, 'backup_smb_password', 'super-secret')

    config_response = await authorized_client.get(BACKUPS['config'])
    assert config_response.status_code == 200, config_response.text
    config_payload = config_response.json()
    assert config_payload['destination'] == 'smb'
    assert config_payload['schedule'] == '0 2 * * *'
    assert config_payload['next_scheduled'] is not None
    assert config_payload['smb']['password_configured'] is True
    assert 'super-secret' not in json.dumps(config_payload)
    assert config_payload['validation']['writable'] is True

    status_response = await authorized_client.get(BACKUPS['status'])
    assert status_response.status_code == 200, status_response.text
    status_payload = status_response.json()
    assert status_payload['destination'] == 'smb'
    assert status_payload['next_scheduled'] is not None


@pytest.mark.asyncio
async def test_backup_failure_creates_notification(authorized_client, tmp_path: Path, monkeypatch) -> None:
    backup_dir = tmp_path / 'failed-backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, 'backup_target', str(backup_dir))
    monkeypatch.setattr(settings, 'backup_destination', 'local')

    async def fail_backup(*_args, **_kwargs):
        raise RuntimeError('simulated backup failure')

    monkeypatch.setattr('backend.services.backup_service._perform_backup', fail_backup)

    create_response = await authorized_client.post(BACKUPS['trigger'], json={'backup_type': 'manual'})
    assert create_response.status_code == 201, create_response.text

    job = await _wait_for_backup(authorized_client, create_response.json()['id'])
    assert job['status'] == 'failed'
    assert 'simulated backup failure' in (job['error_message'] or '')

    async with AsyncSessionLocal() as db:
        notifications = (
            await db.execute(
                select(Notification).where(
                    Notification.type == NotificationType.backup_status,
                    Notification.link == '/settings/backups',
                )
            )
        ).scalars().all()

    assert notifications
