from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import inspect

from backend.database import AsyncSessionLocal, engine
from backend.models import ComplianceRule, ComplianceRuleType
from tests.contracts import ATTENDANCE, CALENDAR, GRADEBOOK, GRADES, STUDENTS
from tests.helpers import response_id


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
