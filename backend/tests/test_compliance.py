from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models import (
    AttendanceRecord,
    AttendanceStatus,
    ComplianceRule,
    ComplianceRuleType,
    ComplianceState,
    FamilySettings,
    Notification,
    NotificationType,
    PortfolioEntry,
    PortfolioEntryType,
    Quiz,
    QuizAttempt,
    SchoolYear,
    Student,
    Subject,
)


async def _auth_context(client) -> tuple[int, int]:
    response = await client.get('/api/auth/me')
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload['family']['id'], payload['user']['id']


async def _set_family_state(family_id: int, state_code: str) -> None:
    async with AsyncSessionLocal() as session:
        family_settings = await session.get(FamilySettings, family_id)
        assert family_settings is not None
        family_settings.state_code = state_code
        await session.commit()


async def _create_school_year(*, family_id: int, start_date: date, end_date: date, is_active: bool = False) -> SchoolYear:
    async with AsyncSessionLocal() as session:
        school_year = SchoolYear(
            family_id=family_id,
            name=f'{start_date.year}-{end_date.year}',
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
        )
        session.add(school_year)
        await session.commit()
        await session.refresh(school_year)
        return school_year


async def _create_student(*, family_id: int, name: str = 'Ada Lovelace') -> Student:
    async with AsyncSessionLocal() as session:
        student = Student(family_id=family_id, name=name)
        session.add(student)
        await session.commit()
        await session.refresh(student)
        return student


async def _create_subject(*, family_id: int, name: str) -> Subject:
    async with AsyncSessionLocal() as session:
        subject = Subject(family_id=family_id, name=name, color='#2563eb')
        session.add(subject)
        await session.commit()
        await session.refresh(subject)
        return subject


async def _seed_rule(
    *,
    state_code: str,
    rule_type: ComplianceRuleType,
    rule_name: str,
    threshold_value: Decimal | int,
    threshold_unit: str,
    description: str,
    subjects_list: list[str] | None = None,
    family_id: int | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        session.add(
            ComplianceRule(
                family_id=family_id,
                state_code=state_code,
                rule_type=rule_type,
                rule_name=rule_name,
                description=description,
                threshold_value=Decimal(str(threshold_value)),
                threshold_unit=threshold_unit,
                subjects_list=subjects_list,
                is_active=True,
            )
        )
        await session.commit()


async def _add_attendance_days(*, family_id: int, student_id: int, start_date: date, total_days: int, hours: Decimal = Decimal('5')) -> None:
    async with AsyncSessionLocal() as session:
        records = [
            AttendanceRecord(
                family_id=family_id,
                student_id=student_id,
                date=start_date + timedelta(days=index),
                status=AttendanceStatus.present,
                instructional_hours=hours,
            )
            for index in range(total_days)
        ]
        session.add_all(records)
        await session.commit()


async def _add_quiz_attempt(*, family_id: int, student_id: int, subject_id: int, completed_at: datetime) -> None:
    async with AsyncSessionLocal() as session:
        quiz = Quiz(
            family_id=family_id,
            title='Annual assessment',
            subject_id=subject_id,
            questions=[{'prompt': 'Q1', 'answer': 'A'}],
        )
        session.add(quiz)
        await session.flush()
        session.add(
            QuizAttempt(
                family_id=family_id,
                quiz_id=quiz.id,
                student_id=student_id,
                answers=['A'],
                score=1,
                max_score=1,
                completed_at=completed_at,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_compliance_rules_follow_family_state(authorized_client):
    family_id, _ = await _auth_context(authorized_client)
    await _seed_rule(
        state_code='TX',
        rule_type=ComplianceRuleType.attendance_days,
        rule_name='Texas minimum instructional days',
        threshold_value=180,
        threshold_unit='days',
        description='Texas requires 180 instructional days.',
    )
    await _seed_rule(
        state_code='CA',
        rule_type=ComplianceRuleType.attendance_days,
        rule_name='California instructional days',
        threshold_value=175,
        threshold_unit='days',
        description='California targets 175 instructional days.',
    )

    update_response = await authorized_client.put('/api/compliance/family/state', json={'state_code': 'TX'})
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()['state_code'] == 'TX'

    rules_response = await authorized_client.get('/api/compliance/rules')
    assert rules_response.status_code == 200, rules_response.text
    payload = rules_response.json()
    assert payload['state_code'] == 'TX'
    assert [rule['rule_name'] for rule in payload['rules']] == ['Texas minimum instructional days']

    async with AsyncSessionLocal() as session:
        family_settings = await session.get(FamilySettings, family_id)
        assert family_settings is not None
        assert family_settings.state_code == 'TX'


@pytest.mark.asyncio
async def test_student_compliance_reports_attendance_and_subject_gaps(authorized_client):
    family_id, _ = await _auth_context(authorized_client)
    school_year = await _create_school_year(family_id=family_id, start_date=date(2024, 8, 1), end_date=date(2025, 5, 31))
    student = await _create_student(family_id=family_id)
    await _set_family_state(family_id, 'TX')
    await _seed_rule(
        state_code='TX',
        rule_type=ComplianceRuleType.attendance_days,
        rule_name='Texas minimum instructional days',
        threshold_value=180,
        threshold_unit='days',
        description='Texas requires 180 instructional days.',
    )
    await _seed_rule(
        state_code='TX',
        rule_type=ComplianceRuleType.subjects_required,
        rule_name='Texas core subjects',
        threshold_value=5,
        threshold_unit='count',
        description='Texas requires math, reading, spelling, grammar, and citizenship.',
        subjects_list=['math', 'reading', 'spelling', 'grammar', 'citizenship'],
    )
    await _create_subject(family_id=family_id, name='Math')
    await _create_subject(family_id=family_id, name='Reading')
    await _create_subject(family_id=family_id, name='Spelling')
    await _add_attendance_days(
        family_id=family_id,
        student_id=student.id,
        start_date=school_year.start_date,
        total_days=170,
    )

    response = await authorized_client.get(f'/api/compliance/{student.id}/status?school_year_id={school_year.id}')
    assert response.status_code == 200, response.text
    payload = response.json()
    statuses = {item['rule']['rule_type']: item for item in payload['statuses']}
    assert statuses['attendance_days']['status'] == ComplianceState.non_compliant.value
    assert statuses['attendance_days']['current_value'] == '170.00'
    assert statuses['attendance_days']['required_value'] == '180.00'
    assert statuses['subjects_required']['status'] == ComplianceState.non_compliant.value
    assert statuses['subjects_required']['current_value'] == '3.00'
    assert 'grammar' in statuses['subjects_required']['notes'].lower()
    assert 'citizenship' in statuses['subjects_required']['notes'].lower()


@pytest.mark.asyncio
async def test_assessment_rule_uses_quiz_evidence(authorized_client):
    family_id, _ = await _auth_context(authorized_client)
    school_year = await _create_school_year(family_id=family_id, start_date=date(2024, 8, 1), end_date=date(2025, 5, 31))
    student = await _create_student(family_id=family_id, name='Grace Hopper')
    subject = await _create_subject(family_id=family_id, name='Science')
    await _set_family_state(family_id, 'VA')
    await _seed_rule(
        state_code='VA',
        rule_type=ComplianceRuleType.assessment_required,
        rule_name='Virginia annual assessment',
        threshold_value=1,
        threshold_unit='count',
        description='Virginia requires annual assessment evidence.',
    )

    first_response = await authorized_client.get(f'/api/compliance/{student.id}/status?school_year_id={school_year.id}')
    assert first_response.status_code == 200, first_response.text
    first_status = first_response.json()['statuses'][0]
    assert first_status['status'] == ComplianceState.non_compliant.value
    assert first_status['current_value'] == '0.00'

    await _add_quiz_attempt(
        family_id=family_id,
        student_id=student.id,
        subject_id=subject.id,
        completed_at=datetime(2025, 2, 1, tzinfo=UTC),
    )

    second_response = await authorized_client.get(f'/api/compliance/{student.id}/status?school_year_id={school_year.id}')
    assert second_response.status_code == 200, second_response.text
    second_status = second_response.json()['statuses'][0]
    assert second_status['status'] == ComplianceState.compliant.value
    assert second_status['current_value'] == '1.00'


@pytest.mark.asyncio
async def test_custom_rules_are_family_scoped(authorized_client, secondary_client, create_family_user):
    family_id, _ = await _auth_context(authorized_client)
    second_family = await create_family_user(
        family_name='Second Family',
        email='second@example.com',
        password='strongpass1234',
    )
    login_response = await secondary_client.post(
        '/api/auth/login',
        json={'email': second_family['email'], 'password': second_family['password']},
    )
    assert login_response.status_code == 200, login_response.text

    create_response = await authorized_client.post(
        '/api/compliance/rules/custom',
        json={
            'rule_type': 'portfolio_required',
            'rule_name': 'Custom portfolio review',
            'description': 'Keep at least 2 portfolio entries for this year.',
            'threshold_value': '2',
            'threshold_unit': 'count',
            'subjects_list': None,
            'is_active': True,
        },
    )
    assert create_response.status_code == 201, create_response.text
    created_rule = create_response.json()
    assert created_rule['is_custom'] is True
    assert created_rule['family_id'] == family_id

    primary_rules = await authorized_client.get('/api/compliance/rules?state=CUSTOM')
    assert primary_rules.status_code == 200, primary_rules.text
    assert primary_rules.json()['summary']['total_rules'] == 1

    secondary_rules = await secondary_client.get('/api/compliance/rules?state=CUSTOM')
    assert secondary_rules.status_code == 200, secondary_rules.text
    assert secondary_rules.json()['summary']['total_rules'] == 0


@pytest.mark.asyncio
async def test_compliance_dashboard_creates_warning_notifications(authorized_client):
    family_id, user_id = await _auth_context(authorized_client)
    today = datetime.now(UTC).date()
    school_year = await _create_school_year(
        family_id=family_id,
        start_date=today - timedelta(days=270),
        end_date=today + timedelta(days=10),
        is_active=True,
    )
    student = await _create_student(family_id=family_id, name='Katherine Johnson')
    await _add_attendance_days(
        family_id=family_id,
        student_id=student.id,
        start_date=school_year.start_date,
        total_days=20,
        hours=Decimal('4'),
    )
    create_rule_response = await authorized_client.post(
        '/api/compliance/rules/custom',
        json={
            'rule_type': 'attendance_hours',
            'rule_name': 'Minimum instructional hours',
            'description': 'Track 100 hours before the school year ends.',
            'threshold_value': '100',
            'threshold_unit': 'hours',
            'subjects_list': None,
            'is_active': True,
        },
    )
    assert create_rule_response.status_code == 201, create_rule_response.text

    dashboard_response = await authorized_client.get(f'/api/compliance/dashboard?school_year_id={school_year.id}')
    assert dashboard_response.status_code == 200, dashboard_response.text
    payload = dashboard_response.json()
    assert payload['school_year_id'] == school_year.id
    assert len(payload['students']) == 1
    student_row = payload['students'][0]
    assert student_row['student']['id'] == student.id
    assert student_row['statuses'][0]['status'] == ComplianceState.warning.value
    assert student_row['statuses'][0]['current_value'] == '80.00'

    async with AsyncSessionLocal() as session:
        notifications = (
            await session.execute(
                select(Notification).where(
                    Notification.family_id == family_id,
                    Notification.user_id == user_id,
                    Notification.type == NotificationType.compliance_reminder,
                )
            )
        ).scalars().all()
        assert len(notifications) == 1
        assert 'Katherine Johnson' in notifications[0].title
