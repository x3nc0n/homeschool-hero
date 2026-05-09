from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import UTC, datetime, timedelta
from zipfile import ZipFile

import pytest
from httpx import AsyncClient

from backend.database import AsyncSessionLocal
from backend.models import Student
from tests.contracts import (
    ASSIGNMENTS,
    ATTENDANCE,
    AUTH,
    CALENDAR,
    COMPLIANCE_REPORTS,
    GRADES,
    REPORT_CARDS,
    STUDENTS,
    SUBJECTS,
    SUBMISSIONS,
    TRANSCRIPTS,
    assignment_payload,
    attendance_daily_payload,
    attendance_record_payload,
    grading_period_payload,
    portfolio_entry_payload,
    school_year_payload,
    student_payload,
    subject_payload,
    term_payload,
)
from tests.helpers import response_id, sync_csrf_header

EXPORTS = {
    'collection': '/api/exports',
    'detail': '/api/exports/{job_id}/status',
    'download': '/api/exports/{job_id}/download',
    'delete': '/api/exports/{job_id}',
}


async def _wait_for_export(client: AsyncClient, job_id: int, *, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(EXPORTS['detail'].format(job_id=job_id))
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload['status'] in {'complete', 'failed'}:
            return payload
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail(f'Export job {job_id} did not finish in time: {payload}')
        await asyncio.sleep(0.05)


async def _create_school_year_with_period(client: AsyncClient) -> tuple[int, int]:
    school_year = await client.post(
        CALENDAR['school_years'],
        json=school_year_payload(name='2025-2026', start_date='2025-08-18', end_date='2026-05-29'),
    )
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())
    term = await client.post(
        CALENDAR['terms'],
        json=term_payload(school_year_id, name='Fall Semester', start_date='2025-08-18', end_date='2025-12-19'),
    )
    assert term.status_code == 201, term.text
    grading_period = await client.post(
        CALENDAR['grading_periods'],
        json=grading_period_payload(response_id(term.json()), name='Q1', start_date='2025-08-18', end_date='2025-10-17'),
    )
    assert grading_period.status_code == 201, grading_period.text
    return school_year_id, response_id(grading_period.json())


async def _seed_family_export_data(client: AsyncClient) -> dict[str, int]:
    student = await client.post(STUDENTS['collection'], json=student_payload('Ada Lovelace'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    subject = await client.post(SUBJECTS['collection'], json=subject_payload('Mathematics', '#2563eb'))
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())

    school_year_id, grading_period_id = await _create_school_year_with_period(client)

    assignment = await client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': 'Fractions Worksheet',
            'grading_period_id': grading_period_id,
            'due_date': '2025-09-15T00:00:00Z',
            'targets': [{'student_id': student_id, 'due_date': '2025-09-15T00:00:00Z', 'status': 'assigned'}],
        },
    )
    assert assignment.status_code == 201, assignment.text
    assignment_id = response_id(assignment.json())

    submission = await client.post(
        SUBMISSIONS['collection'],
        data={'assignment_id': str(assignment_id), 'student_id': str(student_id)},
        files={
            'file': (
                'fractions.png',
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0'
                b'\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82',
                'image/png',
            )
        },
    )
    assert submission.status_code in {200, 201, 202}, submission.text
    submission_id = response_id(submission.json())

    grade = await client.post(
        GRADES['collection'],
        json={
            'submission_id': submission_id,
            'student_id': student_id,
            'score': 94,
            'max_score': 100,
            'letter_grade': 'A',
            'graded_by': 'human',
            'notes': 'Strong independent work.',
        },
    )
    assert grade.status_code == 201, grade.text

    attendance = await client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload(
            '2025-09-15',
            [attendance_record_payload(student_id, status='present', instructional_hours='5.25', notes='Full school day')],
        ),
    )
    assert attendance.status_code == 201, attendance.text

    report_card = await client.post(
        REPORT_CARDS['generate'],
        json={'student_id': student_id, 'grading_period_id': grading_period_id, 'notes': 'Excellent quarter.'},
    )
    assert report_card.status_code == 201, report_card.text

    transcript = await client.post(
        TRANSCRIPTS['generate'],
        json={'student_id': student_id, 'notes': 'Transcript for portability package.'},
    )
    assert transcript.status_code == 201, transcript.text

    family_state = await client.put('/api/compliance/family/state', json={'state_code': 'NY'})
    assert family_state.status_code == 200, family_state.text
    compliance_report = await client.post(
        COMPLIANCE_REPORTS['generate'],
        json={'student_id': student_id, 'school_year_id': school_year_id, 'report_type': 'attendance_log'},
    )
    assert compliance_report.status_code == 201, compliance_report.text

    portfolio = await client.post(
        '/api/portfolio/entries',
        json=portfolio_entry_payload(
            student_id,
            entry_type='work_sample',
            title='Fractions reflection',
            subject_id=subject_id,
            assignment_id=assignment_id,
            submission_id=submission_id,
        ),
    )
    assert portfolio.status_code == 201, portfolio.text
    portfolio_id = response_id(portfolio.json())

    attach = await client.post(
        f'/api/portfolio/entries/{portfolio_id}/attach',
        files=[
            (
                'files',
                (
                    'notes.pdf',
                    b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF',
                    'application/pdf',
                ),
            )
        ],
    )
    assert attach.status_code == 200, attach.text

    return {
        'student_id': student_id,
        'subject_id': subject_id,
        'assignment_id': assignment_id,
        'submission_id': submission_id,
        'school_year_id': school_year_id,
        'grading_period_id': grading_period_id,
        'portfolio_id': portfolio_id,
    }


@pytest.mark.asyncio
async def test_full_family_json_export_includes_portable_entities(authorized_client: AsyncClient):
    seeded = await _seed_family_export_data(authorized_client)
    create_response = await authorized_client.post(EXPORTS['collection'], json={'export_type': 'full', 'format': 'json'})
    assert create_response.status_code == 201, create_response.text

    job = await _wait_for_export(authorized_client, create_response.json()['id'])
    assert job['status'] == 'complete'
    assert job['file_size'] > 0

    download = await authorized_client.get(EXPORTS['download'].format(job_id=job['id']))
    assert download.status_code == 200, download.text
    payload = json.loads(download.content)

    assert payload['metadata']['export_type'] == 'full'
    assert payload['metadata']['portable']['self_contained'] is True
    assert payload['metadata']['entity_counts']['students'] == 1
    assert payload['family']['id'] == 1
    assert payload['students'][0]['id'] == seeded['student_id']
    assert payload['assignments'][0]['id'] == seeded['assignment_id']
    assert payload['submissions'][0]['id'] == seeded['submission_id']
    assert payload['grades'][0]['letter_grade'] == 'A'
    assert payload['attendance'][0]['status'] == 'present'
    assert payload['report_cards'][0]['student_id'] == seeded['student_id']
    assert payload['transcripts'][0]['student_id'] == seeded['student_id']
    assert payload['portfolio_entries'][0]['id'] == seeded['portfolio_id']
    assert payload['compliance_reports'][0]['student_id'] == seeded['student_id']
    assert payload['audit_events']


@pytest.mark.asyncio
async def test_incremental_student_csv_export_filters_old_records(authorized_client: AsyncClient):
    old_student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Old Student'))
    assert old_student.status_code == 201, old_student.text
    old_student_id = response_id(old_student.json())

    async with AsyncSessionLocal() as session:
        student = await session.get(Student, old_student_id)
        assert student is not None
        student.created_at = datetime.now(UTC) - timedelta(days=2)
        student.updated_at = datetime.now(UTC) - timedelta(days=2)
        await session.commit()

    new_student = await authorized_client.post(STUDENTS['collection'], json=student_payload('New Student'))
    assert new_student.status_code == 201, new_student.text
    date_from = datetime.now(UTC) - timedelta(minutes=1)

    create_response = await authorized_client.post(
        EXPORTS['collection'],
        json={
            'export_type': 'incremental',
            'format': 'csv',
            'entity_types': ['students'],
            'date_from': date_from.isoformat(),
        },
    )
    assert create_response.status_code == 201, create_response.text

    job = await _wait_for_export(authorized_client, create_response.json()['id'])
    assert job['status'] == 'complete'

    download = await authorized_client.get(EXPORTS['download'].format(job_id=job['id']))
    assert download.status_code == 200, download.text
    rows = list(csv.DictReader(io.StringIO(download.text)))
    assert rows and rows[0]['student_id']
    names = {row['name'] for row in rows}
    assert 'New Student' in names
    assert 'Old Student' not in names


@pytest.mark.asyncio
async def test_zip_export_includes_csv_pdfs_and_attachments(authorized_client: AsyncClient):
    await _seed_family_export_data(authorized_client)
    create_response = await authorized_client.post(EXPORTS['collection'], json={'export_type': 'full', 'format': 'zip'})
    assert create_response.status_code == 201, create_response.text

    job = await _wait_for_export(authorized_client, create_response.json()['id'])
    assert job['status'] == 'complete'

    download = await authorized_client.get(EXPORTS['download'].format(job_id=job['id']))
    assert download.status_code == 200, download.text
    with ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert 'metadata.json' in names
        assert 'family-export.json' in names
        assert 'csv/students.csv' in names
        assert any(name.startswith('pdf/report-cards/') and name.endswith('.pdf') for name in names)
        assert any(name.startswith('pdf/transcripts/') and name.endswith('.pdf') for name in names)
        assert any(name.startswith('attachments/portfolio/') for name in names)
        metadata = json.loads(archive.read('metadata.json'))
        assert metadata['entity_counts']['portfolio_entries'] == 1


@pytest.mark.asyncio
async def test_export_jobs_are_family_scoped_and_download_requires_auth(
    authorized_client: AsyncClient,
    secondary_client: AsyncClient,
    tertiary_client: AsyncClient,
    create_family_user,
):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Scoped Student'))
    assert student.status_code == 201, student.text

    create_response = await authorized_client.post(
        EXPORTS['collection'],
        json={'export_type': 'entity', 'format': 'json', 'entity_types': ['students']},
    )
    assert create_response.status_code == 201, create_response.text
    job = await _wait_for_export(authorized_client, create_response.json()['id'])
    assert job['status'] == 'complete'

    other_family = await create_family_user(
        family_name='Other Family',
        email='other-export@example.com',
        password='strongpass999',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
        student_name='Other Student',
    )
    other_login = await secondary_client.post(
        AUTH['login'],
        json={
            'email': other_family['email'],
            'password': other_family['password'],
            'family_id': other_family['family_id'],
        },
    )
    assert other_login.status_code == 200, other_login.text
    sync_csrf_header(secondary_client)

    other_status = await secondary_client.get(EXPORTS['detail'].format(job_id=job['id']))
    assert other_status.status_code == 404, other_status.text
    other_download = await secondary_client.get(EXPORTS['download'].format(job_id=job['id']))
    assert other_download.status_code == 404, other_download.text

    unauthenticated_download = await tertiary_client.get(EXPORTS['download'].format(job_id=job['id']))
    assert unauthenticated_download.status_code == 401, unauthenticated_download.text

    delete_response = await authorized_client.delete(EXPORTS['delete'].format(job_id=job['id']))
    assert delete_response.status_code == 204, delete_response.text
    missing = await authorized_client.get(EXPORTS['detail'].format(job_id=job['id']))
    assert missing.status_code == 404, missing.text
