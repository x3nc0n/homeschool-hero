from __future__ import annotations

import csv
import io
import time
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import inspect

from backend.database import AsyncSessionLocal, engine
from backend.models import (
    Assignment,
    ComplianceRule,
    ComplianceRuleType,
    ExportFormat,
    ExportType,
    Grade,
    Student,
    Subject,
    Submission,
)
from tests.contracts import ASSIGNMENTS, ATTENDANCE, CALENDAR, DASHBOARD, GRADEBOOK, GRADES, STUDENTS
from tests.helpers import response_id

pytestmark = pytest.mark.performance


async def _index_map(table_names: list[str]) -> dict[str, dict[str, tuple[str, ...]]]:
    async with engine.begin() as connection:
        def _collect(sync_connection):
            inspector = inspect(sync_connection)
            return {
                table_name: {
                    item['name']: tuple(item.get('column_names') or ())
                    for item in inspector.get_indexes(table_name)
                }
                for table_name in table_names
            }

        return await connection.run_sync(_collect)


@pytest.mark.asyncio
async def test_performance_indexes_exist(database_schema):
    indexes = await _index_map(
        [
            'assignments',
            'grades',
            'submissions',
            'compliance_statuses',
            'notifications',
            'lesson_plans',
            'pacing_targets',
        ]
    )

    assert indexes['assignments']['ix_assignments_family_subject_grading_period'] == (
        'family_id',
        'subject_id',
        'grading_period_id',
    )
    assert indexes['assignments']['ix_assignments_family_status_due_date'] == ('family_id', 'status', 'due_date')
    assert indexes['grades']['ix_grades_family_student_created_at'] == ('family_id', 'student_id', 'created_at')
    assert indexes['submissions']['ix_submissions_assignment_student_current'] == ('assignment_id', 'student_id', 'is_current')
    assert indexes['compliance_statuses']['ix_compliance_statuses_family_status_school_year'] == (
        'family_id',
        'status',
        'school_year_id',
    )
    assert indexes['notifications']['ix_notifications_user_read_created_at'] == ('user_id', 'read', 'created_at')
    assert indexes['lesson_plans']['ix_lesson_plans_family_student_status_target_date'] == (
        'family_id',
        'student_id',
        'status',
        'target_date',
    )
    assert indexes['pacing_targets']['ix_pacing_targets_family_student_window'] == (
        'family_id',
        'student_id',
        'target_start_date',
        'target_end_date',
    )


@pytest.mark.asyncio
async def test_gradebook_returns_conditional_cache_headers_and_invalidates_on_grade_change(
    authorized_client,
    seeded_student,
    seeded_assignment,
    seeded_grade,
):
    student_id = response_id(seeded_student)
    first = await authorized_client.get(GRADEBOOK['detail'].format(student_id=student_id))
    assert first.status_code == 200, first.text
    etag = first.headers.get('etag')
    assert etag

    not_modified = await authorized_client.get(
        GRADEBOOK['detail'].format(student_id=student_id),
        headers={'If-None-Match': etag},
    )
    assert not_modified.status_code == 304, not_modified.text

    updated = await authorized_client.put(
        GRADES['detail'].format(grade_id=response_id(seeded_grade)),
        json={
            'score': 88,
            'max_score': seeded_grade['max_score'],
            'letter_grade': None,
            'notes': 'Updated for cache invalidation',
            'graded_by': seeded_grade['graded_by'],
            'ai_confidence': seeded_grade['ai_confidence'],
        },
    )
    assert updated.status_code == 200, updated.text

    refreshed = await authorized_client.get(
        GRADEBOOK['detail'].format(student_id=student_id),
        headers={'If-None-Match': etag},
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.headers.get('etag') != etag


@pytest.mark.asyncio
async def test_compliance_student_status_cache_invalidates_after_attendance_change(authorized_client):
    me = await authorized_client.get('/api/auth/me')
    family_id = me.json()['family']['id']

    student = await authorized_client.post(STUDENTS['collection'], json={'name': 'Cache Student'})
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    school_year = await authorized_client.post(
        CALENDAR['school_years'],
        json={'name': '2026-2027', 'start_date': '2026-08-01', 'end_date': '2027-05-31', 'is_active': True},
    )
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())

    await authorized_client.put('/api/compliance/family/state', json={'state_code': 'CUSTOM'})
    async with AsyncSessionLocal() as session:
        session.add(
            ComplianceRule(
                family_id=family_id,
                state_code='CUSTOM',
                rule_type=ComplianceRuleType.attendance_days,
                rule_name='Attendance cache rule',
                description='Ensure cache invalidation refreshes attendance totals.',
                threshold_value=10,
                threshold_unit='days',
                is_active=True,
            )
        )
        await session.commit()

    first = await authorized_client.get(f'/api/compliance/{student_id}/status?school_year_id={school_year_id}')
    assert first.status_code == 200, first.text
    etag = first.headers.get('etag')
    assert etag

    not_modified = await authorized_client.get(
        f'/api/compliance/{student_id}/status?school_year_id={school_year_id}',
        headers={'If-None-Match': etag},
    )
    assert not_modified.status_code == 304, not_modified.text

    attendance = await authorized_client.post(
        ATTENDANCE['daily'],
        json={
            'date': date(2026, 9, 1).isoformat(),
            'records': [{'student_id': student_id, 'status': 'present', 'instructional_hours': '5.00'}],
        },
    )
    assert attendance.status_code == 201, attendance.text

    refreshed = await authorized_client.get(
        f'/api/compliance/{student_id}/status?school_year_id={school_year_id}',
        headers={'If-None-Match': etag},
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.headers.get('etag') != etag
    assert refreshed.json()['statuses'][0]['current_value'] == '1.00'


@pytest.mark.asyncio
async def test_grade_and_submission_pagination_handles_empty_pages(
    authorized_client,
    seeded_submission,
    seeded_student,
    seeded_grade,
):
    grades_page = await authorized_client.get(GRADES['collection'], params={'page': 1, 'page_size': 1})
    assert grades_page.status_code == 200, grades_page.text
    grades_payload = grades_page.json()
    assert grades_payload['total'] == 1
    assert grades_payload['total_pages'] == 1
    assert len(grades_payload['items']) == 1

    empty_grades_page = await authorized_client.get(GRADES['collection'], params={'page': 2, 'page_size': 1})
    assert empty_grades_page.status_code == 200, empty_grades_page.text
    assert empty_grades_page.json()['items'] == []

    history_page = await authorized_client.get(GRADES['history'], params={'page': 1, 'page_size': 1})
    assert history_page.status_code == 200, history_page.text
    assert history_page.json()['total'] == 1

    empty_history_page = await authorized_client.get(GRADES['history'], params={'page': 2, 'page_size': 1})
    assert empty_history_page.status_code == 200, empty_history_page.text
    assert empty_history_page.json()['items'] == []

    submissions_page = await authorized_client.get('/api/submissions', params={'page': 1, 'page_size': 1})
    assert submissions_page.status_code == 200, submissions_page.text
    submissions_payload = submissions_page.json()
    assert submissions_payload['total'] == 1
    assert len(submissions_payload['items']) == 1

    empty_submissions_page = await authorized_client.get('/api/submissions', params={'page': 2, 'page_size': 1})
    assert empty_submissions_page.status_code == 200, empty_submissions_page.text
    assert empty_submissions_page.json()['items'] == []


async def _auth_context(client) -> tuple[int, int]:
    response = await client.get('/api/auth/me')
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload['family']['id'], payload['user']['id']


@pytest.mark.asyncio
async def test_gradebook_handles_large_assignment_volume(authorized_client):
    family_id, _ = await _auth_context(authorized_client)
    student = await authorized_client.post(STUDENTS['collection'], json={'name': 'Performance Student'})
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    subject = await authorized_client.post('/api/subjects', json={'name': 'Performance Math', 'color': '#2563eb'})
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())
    categories = await authorized_client.put(
        '/api/gradebook/categories',
        json={'subject_id': subject_id, 'categories': [{'name': 'homework', 'weight': 1.0, 'drop_lowest': 0}]},
    )
    assert categories.status_code == 200, categories.text

    async with AsyncSessionLocal() as session:
        assignments = []
        submissions = []
        grades = []
        for index in range(120):
            assignment = Assignment(
                family_id=family_id,
                subject_id=subject_id,
                title=f'Performance Assignment {index}',
                description='Bulk gradebook fixture',
            )
            session.add(assignment)
            await session.flush()
            assignments.append(assignment)
            submission = Submission(
                family_id=family_id,
                assignment_id=assignment.id,
                student_id=student_id,
                file_path=f'performance/{index}.txt',
                original_filename=f'{index}.txt',
                file_name=f'{index}.txt',
                file_type='text/plain',
                file_size_bytes=8,
            )
            session.add(submission)
            await session.flush()
            submissions.append(submission)
            grades.append(
                Grade(
                    family_id=family_id,
                    submission_id=submission.id,
                    student_id=student_id,
                    score=90 + (index % 10),
                    max_score=100,
                    graded_by='human',
                    notes='bulk grade',
                )
            )
        session.add_all(grades)
        await session.commit()

    started = time.perf_counter()
    response = await authorized_client.get(GRADEBOOK['detail'].format(student_id=student_id), params={'subject_id': subject_id})
    elapsed = time.perf_counter() - started

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['subjects'][0]['categories'][0]['assignment_count'] == 120
    assert elapsed < 5.0


@pytest.mark.asyncio
async def test_dashboard_aggregates_multiple_students_quickly(authorized_client):
    family_id, _ = await _auth_context(authorized_client)

    async with AsyncSessionLocal() as session:
        students = [Student(family_id=family_id, name=f'Dashboard Student {index}') for index in range(12)]
        session.add_all(students)
        await session.commit()

    started = time.perf_counter()
    response = await authorized_client.get(DASHBOARD['summary'])
    elapsed = time.perf_counter() - started

    assert response.status_code == 200, response.text
    assert len(response.json()['student_summaries']) == 12
    assert elapsed < 5.0


@pytest.mark.asyncio
async def test_search_handles_many_records(authorized_client):
    family_id, _ = await _auth_context(authorized_client)

    async with AsyncSessionLocal() as session:
        session.add_all(Student(family_id=family_id, name=f'Perf Search Student {index}') for index in range(220))
        await session.commit()

    started = time.perf_counter()
    response = await authorized_client.get('/api/search', params={'q': 'Perf Search', 'type': 'student', 'page_size': 50})
    elapsed = time.perf_counter() - started

    assert response.status_code == 200, response.text
    assert response.json()['total'] == 220
    assert elapsed < 5.0


@pytest.mark.asyncio
async def test_export_handles_large_student_dataset(authorized_client):
    family_id, _ = await _auth_context(authorized_client)
    async with AsyncSessionLocal() as session:
        session.add_all(Student(family_id=family_id, name=f'Export Student {index}') for index in range(180))
        await session.commit()

    create_response = await authorized_client.post(
        '/api/exports',
        json={'export_type': ExportType.entity.value, 'format': ExportFormat.csv.value, 'entity_types': ['students']},
    )
    assert create_response.status_code == 201, create_response.text
    job_id = create_response.json()['id']

    deadline = time.perf_counter() + 10.0
    while True:
        response = await authorized_client.get(f'/api/exports/{job_id}/status')
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload['status'] in {'complete', 'failed'}:
            break
        if time.perf_counter() >= deadline:
            pytest.fail(f'Export job {job_id} did not finish in time: {payload}')

    assert payload['status'] == 'complete'
    download_started = time.perf_counter()
    download = await authorized_client.get(f'/api/exports/{job_id}/download')
    download_elapsed = time.perf_counter() - download_started
    assert download.status_code == 200, download.text
    rows = list(csv.DictReader(io.StringIO(download.content.decode('utf-8'))))
    assert len(rows) == 180
    assert download_elapsed < 5.0
