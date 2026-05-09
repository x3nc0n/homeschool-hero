from __future__ import annotations

import pytest

from tests.contracts import (
    ASSIGNMENTS,
    ATTENDANCE,
    AUTH,
    CALENDAR,
    COMPLIANCE_REPORTS,
    GRADES,
    PORTFOLIO,
    STUDENTS,
    SUBJECTS,
    SUBMISSIONS,
    attendance_daily_payload,
    attendance_record_payload,
    assignment_payload,
    grading_period_payload,
    school_year_payload,
    student_payload,
    subject_payload,
    term_payload,
)
from tests.helpers import response_id, sync_csrf_header


async def _create_school_year_with_quarters(authorized_client) -> tuple[int, int, int]:
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())
    term = await authorized_client.post(CALENDAR['terms'], json=term_payload(school_year_id))
    assert term.status_code == 201, term.text
    term_id = response_id(term.json())
    quarter = await authorized_client.post(  # period helper already returns quarter-ish dates
        CALENDAR['grading_periods'],
        json=grading_period_payload(term_id),
    )
    assert quarter.status_code == 201, quarter.text
    return school_year_id, term_id, response_id(quarter.json())


async def _create_graded_assignment(
    authorized_client,
    *,
    subject_id: int,
    student_id: int,
    grading_period_id: int,
    title: str,
    category: str,
    due_date: str,
    score: float,
    max_score: float,
    notes: str,
) -> None:
    assignment = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': title,
            'category': category,
            'due_date': due_date,
            'grading_period_id': grading_period_id,
            'max_score': max_score,
            'targets': [{'student_id': student_id, 'due_date': due_date, 'status': 'assigned'}],
        },
    )
    assert assignment.status_code == 201, assignment.text
    assignment_id = response_id(assignment.json())
    submission = await authorized_client.post(
        SUBMISSIONS['collection'],
        data={'assignment_id': str(assignment_id), 'student_id': str(student_id)},
        files={
            'file': (
                'compliance-report.png',
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
            'max_score': max_score,
            'graded_by': 'human',
            'notes': notes,
        },
    )
    assert grade.status_code == 201, grade.text


@pytest.mark.asyncio
async def test_compliance_report_generation_supports_each_type(authorized_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Ada Lovelace'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    school_year_id, _, grading_period_id = await _create_school_year_with_quarters(authorized_client)
    state = await authorized_client.put('/api/compliance/family/state', json={'state_code': 'NY'})
    assert state.status_code == 200, state.text

    math = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('Math', '#2563eb'))
    assert math.status_code == 201, math.text
    math_id = response_id(math.json())

    await _create_graded_assignment(
        authorized_client,
        subject_id=math_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Quarter test',
        category='test',
        due_date='2025-09-15T00:00:00Z',
        score=92,
        max_score=100,
        notes='Strong mastery.',
    )
    attendance = await authorized_client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload(
            '2025-09-15',
            [attendance_record_payload(student_id, status='present', instructional_hours='5.50')],
        ),
    )
    assert attendance.status_code == 201, attendance.text
    portfolio = await authorized_client.post(
        PORTFOLIO['entry_collection'],
        json={
            'student_id': student_id,
            'entry_type': 'work_sample',
            'title': 'Geometry packet',
            'description': 'Completed geometry review',
            'date': '2025-09-16',
            'subject_id': math_id,
            'tags': ['math', 'review'],
        },
    )
    assert portfolio.status_code == 201, portfolio.text

    annual = await authorized_client.post(
        COMPLIANCE_REPORTS['generate'],
        json={'student_id': student_id, 'school_year_id': school_year_id, 'report_type': 'annual_assessment'},
    )
    assert annual.status_code == 201, annual.text
    assert annual.json()['data']['subject_grades'][0]['subject_name'] == 'Math'

    quarterly = await authorized_client.post(
        COMPLIANCE_REPORTS['generate'],
        json={
            'student_id': student_id,
            'school_year_id': school_year_id,
            'grading_period_id': grading_period_id,
            'report_type': 'quarterly_report',
        },
    )
    assert quarterly.status_code == 201, quarterly.text
    assert quarterly.json()['data']['period']['grading_period_id'] == grading_period_id

    attendance_log = await authorized_client.post(
        COMPLIANCE_REPORTS['generate'],
        json={'student_id': student_id, 'school_year_id': school_year_id, 'report_type': 'attendance_log'},
    )
    assert attendance_log.status_code == 201, attendance_log.text
    assert attendance_log.json()['data']['daily_records'][0]['date'] == '2025-09-15'

    portfolio_review = await authorized_client.post(
        COMPLIANCE_REPORTS['generate'],
        json={'student_id': student_id, 'school_year_id': school_year_id, 'report_type': 'portfolio_review'},
    )
    assert portfolio_review.status_code == 201, portfolio_review.text
    assert portfolio_review.json()['data']['summary']['entry_count'] == 1

    notice = await authorized_client.post(
        COMPLIANCE_REPORTS['generate'],
        json={'student_id': student_id, 'school_year_id': school_year_id, 'report_type': 'notice_of_intent'},
    )
    assert notice.status_code == 201, notice.text
    assert notice.json()['data']['template']['state_code'] == 'NY'

    listing = await authorized_client.get(COMPLIANCE_REPORTS['collection'], params={'student_id': student_id, 'school_year_id': school_year_id})
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 5


@pytest.mark.asyncio
async def test_compliance_report_pdf_finalize_and_required_logic(authorized_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Grace Hopper'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    school_year_id, _, grading_period_id = await _create_school_year_with_quarters(authorized_client)
    state = await authorized_client.put('/api/compliance/family/state', json={'state_code': 'NY'})
    assert state.status_code == 200, state.text

    history = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('History', '#7c3aed'))
    assert history.status_code == 201, history.text
    history_id = response_id(history.json())
    await _create_graded_assignment(
        authorized_client,
        subject_id=history_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Colonial test',
        category='test',
        due_date='2025-09-17T00:00:00Z',
        score=89,
        max_score=100,
        notes='Good recall.',
    )

    generated = await authorized_client.post(
        COMPLIANCE_REPORTS['generate'],
        json={'student_id': student_id, 'school_year_id': school_year_id, 'report_type': 'annual_assessment'},
    )
    assert generated.status_code == 201, generated.text
    report_id = generated.json()['id']

    pdf = await authorized_client.get(COMPLIANCE_REPORTS['pdf'].format(report_id=report_id))
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers['content-type'].startswith('application/pdf')
    assert pdf.content.startswith(b'%PDF')

    finalized = await authorized_client.post(COMPLIANCE_REPORTS['finalize'].format(report_id=report_id))
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()['status'] == 'final'

    required_before = await authorized_client.get(
        COMPLIANCE_REPORTS['required'],
        params={'state': 'NY', 'student_id': student_id, 'school_year_id': school_year_id},
    )
    assert required_before.status_code == 200, required_before.text
    quarterly_item = next(item for item in required_before.json()['items'] if item['report_type'] == 'quarterly_report')
    assert quarterly_item['required_count'] == 4
    assert quarterly_item['outstanding_count'] == 4
    annual_item = next(item for item in required_before.json()['items'] if item['report_type'] == 'annual_assessment')
    assert annual_item['completed_count'] == 1


@pytest.mark.asyncio
async def test_compliance_reports_are_family_scoped(authorized_client, tertiary_client, create_family_user):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Primary Student'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    school_year_id, _, _ = await _create_school_year_with_quarters(authorized_client)
    generated = await authorized_client.post(
        COMPLIANCE_REPORTS['generate'],
        json={'student_id': student_id, 'school_year_id': school_year_id, 'report_type': 'attendance_log'},
    )
    assert generated.status_code == 201, generated.text
    report_id = generated.json()['id']

    other_family = await create_family_user(
        family_name='Other Family',
        email='other-compliance@example.com',
        password='strongpass999',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
        student_name='Other Student',
    )
    other_login = await tertiary_client.post(
        AUTH['login'],
        json={
            'email': other_family['email'],
            'password': other_family['password'],
            'family_id': other_family['family_id'],
        },
    )
    assert other_login.status_code == 200, other_login.text
    sync_csrf_header(tertiary_client)

    other_list = await tertiary_client.get(COMPLIANCE_REPORTS['collection'])
    assert other_list.status_code == 200, other_list.text
    assert other_list.json() == []

    other_detail = await tertiary_client.get(COMPLIANCE_REPORTS['detail'].format(report_id=report_id))
    assert other_detail.status_code == 404, other_detail.text

    other_required = await tertiary_client.get(COMPLIANCE_REPORTS['required'], params={'state': 'TX'})
    assert other_required.status_code == 200, other_required.text
    assert all(item['generated_count'] == 0 for item in other_required.json()['items'])
