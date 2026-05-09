from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from backend.database import AsyncSessionLocal
from backend.models import (
    ComplianceRule,
    ComplianceRuleType,
    CurriculumLesson,
    CurriculumPackage,
    CurriculumUnit,
    FamilySettings,
    PacingTarget,
)
from tests.contracts import (
    ASSIGNMENTS,
    ATTENDANCE,
    AUTH,
    CALENDAR,
    DASHBOARD,
    GRADES,
    SCHEDULE,
    STUDENTS,
    SUBJECTS,
    SUBMISSIONS,
    assignment_payload,
    attendance_daily_payload,
    attendance_record_payload,
    schedule_block_payload,
    schedule_payload,
    school_year_payload,
    student_payload,
    subject_payload,
)
from tests.helpers import response_id


def _iso_datetime(day_value: date) -> str:
    return datetime.combine(day_value, datetime.min.time(), tzinfo=UTC).isoformat()


async def _auth_context(client) -> tuple[int, int]:
    response = await client.get(AUTH['me'])
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload['family']['id'], payload['user']['id']


async def _set_family_state(*, family_id: int, state_code: str) -> None:
    async with AsyncSessionLocal() as session:
        family_settings = await session.get(FamilySettings, family_id)
        assert family_settings is not None
        family_settings.state_code = state_code
        await session.commit()


async def _seed_compliance_rule(*, state_code: str) -> None:
    async with AsyncSessionLocal() as session:
        session.add(
            ComplianceRule(
                family_id=None,
                state_code=state_code,
                rule_type=ComplianceRuleType.attendance_days,
                rule_name='Instructional day minimum',
                description='Students must complete the minimum instructional days.',
                threshold_value=Decimal('180'),
                threshold_unit='days',
                is_active=True,
            )
        )
        await session.commit()


async def _seed_pacing_target(
    *,
    family_id: int,
    user_id: int,
    school_year_id: int,
    subject_id: int,
    student_id: int,
    today: date,
) -> None:
    async with AsyncSessionLocal() as session:
        package = CurriculumPackage(
            family_id=family_id,
            school_year_id=school_year_id,
            name='Math Core',
            description='Core pacing package',
            subject_id=subject_id,
            created_by_user_id=user_id,
        )
        session.add(package)
        await session.flush()

        unit = CurriculumUnit(
            package_id=package.id,
            name='Fractions Unit',
            description='Fractions pacing',
            sequence_order=1,
            standards_tags=[],
        )
        session.add(unit)
        await session.flush()

        session.add_all(
            [
                CurriculumLesson(unit_id=unit.id, name='Lesson 1', sequence_order=1, standards_tags=[]),
                CurriculumLesson(unit_id=unit.id, name='Lesson 2', sequence_order=2, standards_tags=[]),
            ]
        )
        session.add(
            PacingTarget(
                family_id=family_id,
                curriculum_unit_id=unit.id,
                student_id=student_id,
                target_start_date=today - timedelta(days=10),
                target_end_date=today - timedelta(days=1),
                actual_completion_date=None,
            )
        )
        await session.commit()


async def _create_submission_and_grade(authorized_client, *, assignment_id: int, student_id: int, score: int = 92) -> dict[str, object]:
    submission = await authorized_client.post(
        SUBMISSIONS['collection'],
        data={'assignment_id': str(assignment_id), 'student_id': str(student_id)},
        files={
            'file': (
                'dashboard.png',
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0'
                b'\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82',
                'image/png',
            )
        },
    )
    assert submission.status_code in {200, 201, 202}, submission.text

    grade = await authorized_client.post(
        GRADES['collection'],
        json={
            'submission_id': response_id(submission.json()),
            'student_id': student_id,
            'score': score,
            'max_score': 100,
            'graded_by': 'human',
            'notes': 'Dashboard grade',
        },
    )
    assert grade.status_code == 201, grade.text
    return grade.json()


@pytest.mark.asyncio
async def test_dashboard_aggregates_family_widgets(authorized_client):
    today = datetime.now(UTC).date()
    family_id, user_id = await _auth_context(authorized_client)

    student_one = await authorized_client.post(STUDENTS['collection'], json=student_payload('Ada Lovelace'))
    assert student_one.status_code == 201, student_one.text
    student_one_id = response_id(student_one.json())

    student_two = await authorized_client.post(STUDENTS['collection'], json=student_payload('Grace Hopper'))
    assert student_two.status_code == 201, student_two.text
    student_two_id = response_id(student_two.json())

    subject = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('Math', '#2563eb'))
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())

    school_year = await authorized_client.post(
        CALENDAR['school_years'],
        json=school_year_payload(
            name='Current Year',
            start_date=(today - timedelta(days=30)).isoformat(),
            end_date=(today + timedelta(days=30)).isoformat(),
            is_active=True,
        ),
    )
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())

    schedule = await authorized_client.post(
        SCHEDULE['collection'],
        json=schedule_payload(student_one_id, school_year_id, name='Main Schedule'),
    )
    assert schedule.status_code == 201, schedule.text
    schedule_id = response_id(schedule.json())

    block = await authorized_client.post(
        SCHEDULE['blocks'].format(schedule_id=schedule_id),
        json=schedule_block_payload(subject_id, day_of_week=today.weekday(), start_time='09:00', end_time='10:00'),
    )
    assert block.status_code == 201, block.text

    attendance = await authorized_client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload(
            today.isoformat(),
            [
                attendance_record_payload(
                    student_one_id,
                    status='present',
                    instructional_hours='5.50',
                    notes='On time',
                )
            ],
        ),
    )
    assert attendance.status_code == 201, attendance.text

    upcoming_assignment = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': 'Fractions Check',
            'due_date': _iso_datetime(today + timedelta(days=3)),
            'targets': [{'student_id': student_one_id, 'due_date': _iso_datetime(today + timedelta(days=3)), 'status': 'assigned'}],
        },
    )
    assert upcoming_assignment.status_code == 201, upcoming_assignment.text

    graded_assignment = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': 'Completed Quiz',
            'due_date': _iso_datetime(today + timedelta(days=1)),
            'targets': [{'student_id': student_one_id, 'due_date': _iso_datetime(today + timedelta(days=1)), 'status': 'assigned'}],
        },
    )
    assert graded_assignment.status_code == 201, graded_assignment.text
    assignment_id = response_id(graded_assignment.json())

    future_assignment = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': 'Out of range',
            'due_date': _iso_datetime(today + timedelta(days=12)),
            'targets': [{'student_id': student_two_id, 'due_date': _iso_datetime(today + timedelta(days=12)), 'status': 'assigned'}],
        },
    )
    assert future_assignment.status_code == 201, future_assignment.text

    await _create_submission_and_grade(authorized_client, assignment_id=assignment_id, student_id=student_one_id)
    await _set_family_state(family_id=family_id, state_code='TX')
    await _seed_compliance_rule(state_code='TX')
    await _seed_pacing_target(
        family_id=family_id,
        user_id=user_id,
        school_year_id=school_year_id,
        subject_id=subject_id,
        student_id=student_one_id,
        today=today,
    )

    response = await authorized_client.get(DASHBOARD['summary'])
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload['role'] == 'parent'
    assert payload['today_schedule'][0]['student_id'] == student_one_id
    assert [item['title'] for item in payload['upcoming_assignments']] == ['Fractions Check']
    assert payload['recent_grades'][0]['assignment_title'] == 'Completed Quiz'
    assert {item['student_id']: item['status'] for item in payload['attendance_today']} == {
        student_one_id: 'present',
        student_two_id: 'not_recorded',
    }
    assert payload['pacing_alerts'][0]['student_id'] == student_one_id
    assert payload['compliance_warnings'][0]['student_id'] == student_one_id
    assert payload['system_status'] is not None
    summary_by_student = {item['student_id']: item for item in payload['student_summaries']}
    assert summary_by_student[student_one_id]['assignments_due_count'] == 1
    assert summary_by_student[student_one_id]['current_gpa'] is not None
    assert summary_by_student[student_one_id]['pacing_status'] == 'behind'
    assert summary_by_student[student_one_id]['compliance_status'] in {'warning', 'non_compliant'}


@pytest.mark.asyncio
async def test_dashboard_filters_student_viewer_scope(authorized_client, secondary_client, create_family_user):
    today = datetime.now(UTC).date()
    family_id, _user_id = await _auth_context(authorized_client)

    student_one = await authorized_client.post(STUDENTS['collection'], json=student_payload('Ada Lovelace'))
    assert student_one.status_code == 201, student_one.text
    student_one_id = response_id(student_one.json())

    student_two = await authorized_client.post(STUDENTS['collection'], json=student_payload('Grace Hopper'))
    assert student_two.status_code == 201, student_two.text
    student_two_id = response_id(student_two.json())

    subject = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('Science', '#16a34a'))
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())

    school_year = await authorized_client.post(
        CALENDAR['school_years'],
        json=school_year_payload(
            name='Current Year',
            start_date=(today - timedelta(days=30)).isoformat(),
            end_date=(today + timedelta(days=30)).isoformat(),
            is_active=True,
        ),
    )
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())

    for student_id in (student_one_id, student_two_id):
        schedule = await authorized_client.post(
            SCHEDULE['collection'],
            json=schedule_payload(student_id, school_year_id, name=f'Schedule {student_id}'),
        )
        assert schedule.status_code == 201, schedule.text
        block = await authorized_client.post(
            SCHEDULE['blocks'].format(schedule_id=response_id(schedule.json())),
            json=schedule_block_payload(subject_id, day_of_week=today.weekday(), start_time='10:00', end_time='11:00'),
        )
        assert block.status_code == 201, block.text

    assignment_one = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': 'Student One Assignment',
            'due_date': _iso_datetime(today + timedelta(days=2)),
            'targets': [{'student_id': student_one_id, 'due_date': _iso_datetime(today + timedelta(days=2)), 'status': 'assigned'}],
        },
    )
    assert assignment_one.status_code == 201, assignment_one.text
    await _create_submission_and_grade(
        authorized_client,
        assignment_id=response_id(assignment_one.json()),
        student_id=student_one_id,
        score=95,
    )

    assignment_two = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': 'Student Two Assignment',
            'due_date': _iso_datetime(today + timedelta(days=2)),
            'targets': [{'student_id': student_two_id, 'due_date': _iso_datetime(today + timedelta(days=2)), 'status': 'assigned'}],
        },
    )
    assert assignment_two.status_code == 201, assignment_two.text
    await _create_submission_and_grade(
        authorized_client,
        assignment_id=response_id(assignment_two.json()),
        student_id=student_two_id,
        score=87,
    )

    viewer = await create_family_user(
        family_name='Ignored',
        family_id=family_id,
        email='viewer@example.com',
        password='viewerpass123',
        display_name='Student Viewer',
        role='student_viewer',
        student_id=student_one_id,
    )
    login = await secondary_client.post(
        AUTH['login'],
        json={'email': viewer['email'], 'password': viewer['password'], 'family_id': family_id},
    )
    assert login.status_code == 200, login.text

    response = await secondary_client.get(DASHBOARD['summary'])
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload['role'] == 'student_viewer'
    assert {item['student_id'] for item in payload['today_schedule']} == {student_one_id}
    assert {item['student_id'] for item in payload['upcoming_assignments']} == {student_one_id}
    assert {item['student_id'] for item in payload['recent_grades']} == {student_one_id}
    assert {item['student_id'] for item in payload['student_summaries']} == {student_one_id}
    assert payload['attendance_today'] == []
    assert payload['pacing_alerts'] == []
    assert payload['compliance_warnings'] == []
    assert payload['system_status'] is None


@pytest.mark.asyncio
async def test_dashboard_handles_empty_state(authorized_client):
    response = await authorized_client.get(DASHBOARD['summary'])
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload['today_schedule'] == []
    assert payload['upcoming_assignments'] == []
    assert payload['recent_grades'] == []
    assert payload['attendance_today'] == []
    assert payload['pacing_alerts'] == []
    assert payload['compliance_warnings'] == []
    assert payload['student_summaries'] == []
    assert payload['system_status'] is not None


@pytest.mark.asyncio
async def test_dashboard_selected_student_handles_optional_widget_failures(authorized_client, monkeypatch):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('New Kid'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    async def _boom(*_args, **_kwargs):
        raise RuntimeError('boom')

    monkeypatch.setattr('backend.routers.dashboard.calculate_gradebook_summary', _boom)
    monkeypatch.setattr('backend.routers.dashboard._build_pacing_status_payload', _boom)
    monkeypatch.setattr('backend.routers.dashboard.get_dashboard_payload', _boom)
    monkeypatch.setattr('backend.routers.dashboard.collect_service_health', _boom)

    response = await authorized_client.get(f"{DASHBOARD['summary']}?student_id={student_id}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload['selected_student_id'] == student_id
    assert len(payload['student_summaries']) == 1
    assert payload['student_summaries'][0]['student_id'] == student_id
    assert payload['student_summaries'][0]['current_gpa'] is None
    assert payload['attendance_today'][0]['student_id'] == student_id
    assert payload['pacing_alerts'] == []
    assert payload['compliance_warnings'] == []
    assert payload['system_status'] is None
