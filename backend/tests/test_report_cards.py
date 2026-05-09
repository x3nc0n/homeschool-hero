from __future__ import annotations

import pytest

from tests.contracts import (
    ASSIGNMENTS,
    ATTENDANCE,
    AUTH,
    CALENDAR,
    GRADEBOOK,
    GRADES,
    REPORT_CARDS,
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


async def _create_grading_period(authorized_client) -> tuple[int, int]:
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())

    term = await authorized_client.post(CALENDAR['terms'], json=term_payload(school_year_id))
    assert term.status_code == 201, term.text

    grading_period = await authorized_client.post(CALENDAR['grading_periods'], json=grading_period_payload(response_id(term.json())))
    assert grading_period.status_code == 201, grading_period.text
    return school_year_id, response_id(grading_period.json())


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
                'report-card.png',
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
async def test_report_card_generation_aggregates_grades_and_attendance(authorized_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Ada Lovelace'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    school_year_id, grading_period_id = await _create_grading_period(authorized_client)

    math = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('Math', '#2563eb'))
    science = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('Science', '#16a34a'))
    assert math.status_code == 201, math.text
    assert science.status_code == 201, science.text
    math_id = response_id(math.json())
    science_id = response_id(science.json())

    for subject_id in (math_id, science_id):
        categories = await authorized_client.put(
            GRADEBOOK['categories'],
            json={'subject_id': subject_id, 'categories': [{'name': 'homework', 'weight': 1.0, 'drop_lowest': 0}]},
        )
        assert categories.status_code == 200, categories.text

    await _create_graded_assignment(
        authorized_client,
        subject_id=math_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Fractions Quiz',
        category='homework',
        due_date='2025-09-01T00:00:00Z',
        score=86,
        max_score=100,
        notes='Solid understanding of fractions.',
    )
    await _create_graded_assignment(
        authorized_client,
        subject_id=science_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Lab Report',
        category='homework',
        due_date='2025-09-10T00:00:00Z',
        score=95,
        max_score=100,
        notes='Excellent observations and conclusions.',
    )

    attendance = await authorized_client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload(
            '2025-09-08',
            [attendance_record_payload(student_id, status='present', instructional_hours='5.50')],
        ),
    )
    assert attendance.status_code == 201, attendance.text
    tardy = await authorized_client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload(
            '2025-09-09',
            [attendance_record_payload(student_id, status='tardy', instructional_hours='4.25', notes='Arrived late')],
        ),
    )
    assert tardy.status_code == 201, tardy.text

    generated = await authorized_client.post(
        REPORT_CARDS['generate'],
        json={'student_id': student_id, 'grading_period_id': grading_period_id, 'notes': 'Great momentum this quarter.'},
    )
    assert generated.status_code == 201, generated.text
    payload = generated.json()
    assert payload['school_year_id'] == school_year_id
    assert payload['status'] == 'draft'
    assert payload['gpa'] == 3.5
    assert payload['overall_percentage'] == 90.5
    assert len(payload['entries']) == 2

    math_entry = next(entry for entry in payload['entries'] if entry['subject']['name'] == 'Math')
    assert math_entry['letter_grade'] == 'B'
    assert math_entry['percentage'] == 86.0
    assert math_entry['category_breakdown']['homework'] == 86.0
    assert math_entry['teacher_comments'] == 'Solid understanding of fractions.'
    assert math_entry['attendance_summary']['total_records'] == 2
    assert math_entry['attendance_summary']['tardy'] == 1
    assert math_entry['attendance_summary']['attendance_rate'] == 100.0

    listing = await authorized_client.get(REPORT_CARDS['collection'], params={'student_id': student_id})
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 1
    assert listing.json()[0]['grading_period_id'] == grading_period_id


@pytest.mark.asyncio
async def test_report_card_pdf_and_finalize_workflow(authorized_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Grace Hopper'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    _, grading_period_id = await _create_grading_period(authorized_client)

    subject = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('History', '#7c3aed'))
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())
    categories = await authorized_client.put(
        GRADEBOOK['categories'],
        json={'subject_id': subject_id, 'categories': [{'name': 'homework', 'weight': 1.0, 'drop_lowest': 0}]},
    )
    assert categories.status_code == 200, categories.text

    await _create_graded_assignment(
        authorized_client,
        subject_id=subject_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Essay',
        category='homework',
        due_date='2025-09-12T00:00:00Z',
        score=91,
        max_score=100,
        notes='Insightful writing with clear evidence.',
    )

    generated = await authorized_client.post(REPORT_CARDS['generate'], json={'student_id': student_id, 'grading_period_id': grading_period_id})
    assert generated.status_code == 201, generated.text
    report_card_id = generated.json()['id']
    entry_id = generated.json()['entries'][0]['id']

    updated = await authorized_client.patch(
        REPORT_CARDS['detail'].format(report_card_id=report_card_id),
        json={
            'notes': 'Parent conference scheduled next week.',
            'entries': [{'entry_id': entry_id, 'teacher_comments': 'Keep expanding your thesis statements.'}],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['notes'] == 'Parent conference scheduled next week.'
    assert updated.json()['entries'][0]['teacher_comments'] == 'Keep expanding your thesis statements.'

    pdf = await authorized_client.get(REPORT_CARDS['pdf'].format(report_card_id=report_card_id))
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers['content-type'].startswith('application/pdf')
    assert pdf.content.startswith(b'%PDF')

    finalized = await authorized_client.post(REPORT_CARDS['finalize'].format(report_card_id=report_card_id))
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()['status'] == 'final'

    forbidden = await authorized_client.patch(
        REPORT_CARDS['detail'].format(report_card_id=report_card_id),
        json={'notes': 'Should not save'},
    )
    assert forbidden.status_code == 409, forbidden.text
    assert 'immutable' in forbidden.json()['detail']


@pytest.mark.asyncio
async def test_report_cards_are_family_scoped(authorized_client, tertiary_client, create_family_user):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Primary Student'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    _, grading_period_id = await _create_grading_period(authorized_client)
    subject = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('English', '#dc2626'))
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())
    categories = await authorized_client.put(
        GRADEBOOK['categories'],
        json={'subject_id': subject_id, 'categories': [{'name': 'homework', 'weight': 1.0, 'drop_lowest': 0}]},
    )
    assert categories.status_code == 200, categories.text
    await _create_graded_assignment(
        authorized_client,
        subject_id=subject_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Book Report',
        category='homework',
        due_date='2025-09-15T00:00:00Z',
        score=88,
        max_score=100,
        notes='Good summary and reflection.',
    )

    generated = await authorized_client.post(REPORT_CARDS['generate'], json={'student_id': student_id, 'grading_period_id': grading_period_id})
    assert generated.status_code == 201, generated.text
    report_card_id = generated.json()['id']

    other_family = await create_family_user(
        family_name='Other Family',
        email='other-report@example.com',
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

    other_list = await tertiary_client.get(REPORT_CARDS['collection'])
    assert other_list.status_code == 200, other_list.text
    assert other_list.json() == []

    other_detail = await tertiary_client.get(REPORT_CARDS['detail'].format(report_card_id=report_card_id))
    assert other_detail.status_code == 404, other_detail.text

    other_generate = await tertiary_client.post(
        REPORT_CARDS['generate'],
        json={'student_id': student_id, 'grading_period_id': grading_period_id},
    )
    assert other_generate.status_code == 404, other_generate.text
