from __future__ import annotations

import asyncio
import csv
import io
from pathlib import Path

import pytest

from backend.config import settings
from tests.contracts import (
    ASSIGNMENTS,
    AUTH,
    BACKUPS,
    CALENDAR,
    GRADEBOOK,
    REPORT_CARDS,
    STUDENTS,
    SUBJECTS,
    SUBMISSIONS,
    assignment_payload,
    grading_period_payload,
    school_year_payload,
    student_payload,
    subject_payload,
    term_payload,
)
from tests.helpers import response_id, sync_csrf_header

pytestmark = pytest.mark.integration


async def _wait_for_export(client, job_id: int, *, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(f'/api/exports/{job_id}/status')
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload['status'] in {'complete', 'failed'}:
            return payload
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail(f'Export job {job_id} did not finish in time: {payload}')
        await asyncio.sleep(0.05)


async def _wait_for_import(client, job_id: int, *, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(f'/api/imports/{job_id}/status')
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload['status'] in {'complete', 'failed'}:
            return payload
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail(f'Import job {job_id} did not finish in time: {payload}')
        await asyncio.sleep(0.05)


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


async def _create_grading_period(client) -> tuple[int, int]:
    school_year = await client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())
    term = await client.post(CALENDAR['terms'], json=term_payload(school_year_id))
    assert term.status_code == 201, term.text
    grading_period = await client.post(CALENDAR['grading_periods'], json=grading_period_payload(response_id(term.json())))
    assert grading_period.status_code == 201, grading_period.text
    return school_year_id, response_id(grading_period.json())


@pytest.mark.asyncio
async def test_full_family_workflow_create_to_report_card(async_client):
    register = await async_client.post(AUTH['register'], json={'family_name': 'Integration Family', 'display_name': 'Owner', 'email': 'owner@example.com', 'password': 'strongpass123', 'timezone': 'UTC', 'grading_scale': 'letter'})
    assert register.status_code == 201, register.text
    sync_csrf_header(async_client)

    student = await async_client.post(STUDENTS['collection'], json=student_payload('Integration Student'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    subject = await async_client.post(SUBJECTS['collection'], json=subject_payload('Integrated Math', '#2563eb'))
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())

    categories = await async_client.put(
        GRADEBOOK['categories'],
        json={'subject_id': subject_id, 'categories': [{'name': 'homework', 'weight': 1.0, 'drop_lowest': 0}]},
    )
    assert categories.status_code == 200, categories.text

    _, grading_period_id = await _create_grading_period(async_client)

    assignment = await async_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': 'Capstone Worksheet',
            'grading_period_id': grading_period_id,
            'due_date': '2026-05-12T00:00:00Z',
            'targets': [{'student_id': student_id, 'due_date': '2026-05-12T00:00:00Z', 'status': 'assigned'}],
        },
    )
    assert assignment.status_code == 201, assignment.text

    submission = await async_client.post(
        SUBMISSIONS['collection'],
        data={'assignment_id': str(response_id(assignment.json())), 'student_id': str(student_id)},
        files={
            'file': (
                'integration.png',
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0'
                b'\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82',
                'image/png',
            )
        },
    )
    assert submission.status_code in {200, 201, 202}, submission.text
    submission_id = response_id(submission.json())

    from backend.database import AsyncSessionLocal
    from backend.models import GradingJob, GradingJobStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        job = (await session.execute(select(GradingJob).where(GradingJob.submission_id == submission_id))).scalar_one()
        job.status = GradingJobStatus.review_needed
        job.ai_grade = 89
        job.ai_feedback = 'Teacher review requested.'
        job.ai_confidence = 0.45
        job.status_history = [
            {'timestamp': '2026-05-10T00:00:00Z', 'status': 'pending', 'detail': 'Job created', 'payload': {}},
            {'timestamp': '2026-05-10T00:00:01Z', 'status': 'review_needed', 'detail': 'Low confidence', 'payload': {}},
        ]
        await session.commit()
        job_id = job.id

    queue = await async_client.get('/api/grading/review-queue')
    assert queue.status_code == 200, queue.text
    assert [item['id'] for item in queue.json()] == [job_id]

    graded = await async_client.post(
        f'/api/grading/review/{job_id}',
        json={'action': 'modify', 'score': 93, 'feedback': 'Reviewed and confirmed.', 'notes': 'Finalized by teacher.'},
    )
    assert graded.status_code == 200, graded.text
    assert graded.json()['status'] == 'final'

    report_card = await async_client.post(
        REPORT_CARDS['generate'],
        json={'student_id': student_id, 'grading_period_id': grading_period_id, 'notes': 'Integration flow complete.'},
    )
    assert report_card.status_code == 201, report_card.text
    assert report_card.json()['entries'][0]['percentage'] == 93.0


@pytest.mark.asyncio
async def test_csv_import_export_round_trip_preserves_students(authorized_client):
    upload = await authorized_client.post(
        '/api/imports/upload',
        params={'entity_type': 'students'},
        files={'file': ('students.csv', b'name\nAda Lovelace\nJos\xc3\xa9 Curie\n', 'text/csv')},
    )
    assert upload.status_code == 201, upload.text

    execute = await authorized_client.post(f"/api/imports/{upload.json()['id']}/execute")
    assert execute.status_code == 202, execute.text
    imported = await _wait_for_import(authorized_client, upload.json()['id'])
    assert imported['status'] == 'complete'

    export = await authorized_client.post(
        '/api/exports',
        json={'export_type': 'entity', 'format': 'csv', 'entity_types': ['students']},
    )
    assert export.status_code == 201, export.text
    exported = await _wait_for_export(authorized_client, export.json()['id'])
    assert exported['status'] == 'complete'

    download = await authorized_client.get(f"/api/exports/{exported['id']}/download")
    assert download.status_code == 200, download.text
    rows = list(csv.DictReader(io.StringIO(download.content.decode('utf-8'))))
    assert sorted(row['name'] for row in rows) == ['Ada Lovelace', 'José Curie']


@pytest.mark.asyncio
async def test_backup_and_restore_validation_workflow(authorized_client, tmp_path: Path, monkeypatch):
    backup_root = tmp_path / 'backups'
    upload_root = tmp_path / 'uploads'
    backup_root.mkdir(parents=True, exist_ok=True)
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, 'backup_target', str(backup_root))
    monkeypatch.setattr(settings, 'backup_destination', 'local')
    monkeypatch.setattr(settings, 'upload_dir', str(upload_root))

    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Backup Student'))
    assert student.status_code == 201, student.text

    create_response = await authorized_client.post(BACKUPS['trigger'], json={'backup_type': 'manual'})
    assert create_response.status_code == 201, create_response.text
    backup = await _wait_for_backup(authorized_client, create_response.json()['id'])
    assert backup['status'] == 'complete'

    listing = await authorized_client.get('/api/restore/backups')
    assert listing.status_code == 200, listing.text
    available = listing.json()
    assert available
    backup_id = available[0]['backup_id']

    validation = await authorized_client.post(f'/api/restore/validate/{backup_id}')
    assert validation.status_code == 200, validation.text
    assert validation.json()['valid'] is True
    assert validation.json()['can_restore'] is True
    assert validation.json()['confirmation_token']


@pytest.mark.asyncio
async def test_register_login_and_rbac_flow(async_client, secondary_client, create_family_user):
    register = await async_client.post(
        AUTH['register'],
        json={'family_name': 'RBAC Family', 'display_name': 'Owner', 'email': 'owner@example.com', 'password': 'strongpass123', 'timezone': 'UTC', 'grading_scale': 'letter'},
    )
    assert register.status_code == 201, register.text
    sync_csrf_header(async_client)
    family_id = register.json()['family']['id']

    student = await async_client.post(STUDENTS['collection'], json=student_payload('Visible Student'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    await create_family_user(
        family_name='RBAC Family',
        family_id=family_id,
        email='viewer@example.com',
        password='viewer-pass-123',
        display_name='Viewer',
        role='student_viewer',
        student_id=student_id,
    )

    logout = await async_client.post(AUTH['logout'])
    assert logout.status_code in {200, 204}, logout.text

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'viewer@example.com', 'password': 'viewer-pass-123', 'family_id': family_id},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    visible = await secondary_client.get(STUDENTS['detail'].format(student_id=student_id))
    assert visible.status_code == 200, visible.text

    blocked = await secondary_client.post(STUDENTS['collection'], json=student_payload('Blocked Student'))
    assert blocked.status_code == 403, blocked.text
