from __future__ import annotations

import pytest

from tests.contracts import (
    ASSIGNMENTS,
    AUTH,
    CALENDAR,
    GRADEBOOK,
    GRADES,
    STUDENTS,
    SUBJECTS,
    SUBMISSIONS,
    TRANSCRIPTS,
    assignment_payload,
    grading_period_payload,
    school_year_payload,
    student_payload,
    subject_payload,
    term_payload,
)
from tests.helpers import response_id, sync_csrf_header


async def _create_grading_period(authorized_client, *, name: str, school_year_name: str, start: str, end: str) -> tuple[int, int]:
    school_year = await authorized_client.post(
        CALENDAR['school_years'],
        json=school_year_payload(name=school_year_name, start_date=start, end_date=end),
    )
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())

    term = await authorized_client.post(
        CALENDAR['terms'],
        json=term_payload(
            school_year_id,
            name=f'{name} Term',
            start_date=start,
            end_date=end,
        ),
    )
    assert term.status_code == 201, term.text

    grading_period = await authorized_client.post(
        CALENDAR['grading_periods'],
        json=grading_period_payload(
            response_id(term.json()),
            name=name,
            start_date=start,
            end_date=end,
        ),
    )
    assert grading_period.status_code == 201, grading_period.text
    return school_year_id, response_id(grading_period.json())


async def _create_graded_assignment(
    authorized_client,
    *,
    subject_id: int,
    student_id: int,
    grading_period_id: int,
    title: str,
    due_date: str,
    score: float,
    max_score: float,
) -> None:
    assignment = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(subject_id),
            'title': title,
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
                'transcript.png',
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
        },
    )
    assert grade.status_code == 201, grade.text


@pytest.mark.asyncio
async def test_transcript_generation_aggregates_years_and_weighting(authorized_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Ada Lovelace'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    year_one_id, period_one_id = await _create_grading_period(
        authorized_client,
        name='Quarter 1',
        school_year_name='2024-2025',
        start='2024-08-01',
        end='2025-05-31',
    )
    year_two_id, period_two_id = await _create_grading_period(
        authorized_client,
        name='Quarter 1',
        school_year_name='2025-2026',
        start='2025-08-01',
        end='2026-05-31',
    )

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
        grading_period_id=period_one_id,
        title='Linear Equations',
        due_date='2024-09-10T00:00:00Z',
        score=86,
        max_score=100,
    )
    await _create_graded_assignment(
        authorized_client,
        subject_id=science_id,
        student_id=student_id,
        grading_period_id=period_two_id,
        title='Physics Lab',
        due_date='2025-09-10T00:00:00Z',
        score=95,
        max_score=100,
    )

    generated = await authorized_client.post(TRANSCRIPTS['generate'], json={'student_id': student_id, 'notes': 'Generated for review.'})
    assert generated.status_code == 201, generated.text
    payload = generated.json()
    assert payload['status'] == 'draft'
    assert payload['cumulative_gpa'] == 3.5
    assert payload['weighted_gpa'] == 3.5
    assert payload['total_credits'] == 2.0
    assert payload['entry_count'] == 2
    assert {entry['school_year_id'] for entry in payload['entries']} == {year_one_id, year_two_id}

    math_entry = next(entry for entry in payload['entries'] if entry['subject_name'] == 'Math')
    science_entry = next(entry for entry in payload['entries'] if entry['subject_name'] == 'Science')
    assert math_entry['letter_grade'] == 'B'
    assert science_entry['letter_grade'] == 'A'

    updated = await authorized_client.patch(
        TRANSCRIPTS['detail'].format(transcript_id=payload['id']),
        json={
            'notes': 'Ready for college packet.',
            'entries': [
                {'entry_id': math_entry['id'], 'credits': 1.5, 'is_honors': True, 'notes': 'Honors algebra'},
                {'entry_id': science_entry['id'], 'credits': 1.0, 'is_ap': True, 'notes': 'AP lab science'},
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload['notes'] == 'Ready for college packet.'
    assert updated_payload['total_credits'] == 2.5
    assert updated_payload['cumulative_gpa'] == 3.4
    assert updated_payload['weighted_gpa'] == 4.1
    updated_math = next(entry for entry in updated_payload['entries'] if entry['subject_name'] == 'Math')
    updated_science = next(entry for entry in updated_payload['entries'] if entry['subject_name'] == 'Science')
    assert updated_math['weighted_gpa_points'] == 3.5
    assert updated_science['weighted_gpa_points'] == 5.0

    listing = await authorized_client.get(TRANSCRIPTS['collection'], params={'student_id': student_id})
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 1
    assert listing.json()[0]['entry_count'] == 2


@pytest.mark.asyncio
async def test_transcript_pdf_and_finalize_workflow(authorized_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Grace Hopper'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    _, grading_period_id = await _create_grading_period(
        authorized_client,
        name='Semester 1',
        school_year_name='2025-2026',
        start='2025-08-01',
        end='2026-05-31',
    )
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
        title='Historical Essay',
        due_date='2025-09-12T00:00:00Z',
        score=91,
        max_score=100,
    )

    generated = await authorized_client.post(TRANSCRIPTS['generate'], json={'student_id': student_id})
    assert generated.status_code == 201, generated.text
    transcript_id = generated.json()['id']
    entry_id = generated.json()['entries'][0]['id']

    updated = await authorized_client.patch(
        TRANSCRIPTS['detail'].format(transcript_id=transcript_id),
        json={'entries': [{'entry_id': entry_id, 'credits': 0.5, 'subject_name': 'Modern History Honors'}]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['entries'][0]['credits'] == 0.5
    assert updated.json()['entries'][0]['subject_name'] == 'Modern History Honors'

    pdf = await authorized_client.get(TRANSCRIPTS['pdf'].format(transcript_id=transcript_id))
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers['content-type'].startswith('application/pdf')
    assert pdf.content.startswith(b'%PDF')

    finalized = await authorized_client.post(TRANSCRIPTS['finalize'].format(transcript_id=transcript_id))
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()['status'] == 'final'

    forbidden = await authorized_client.patch(
        TRANSCRIPTS['detail'].format(transcript_id=transcript_id),
        json={'notes': 'Should not save'},
    )
    assert forbidden.status_code == 409, forbidden.text
    assert 'immutable' in forbidden.json()['detail']


@pytest.mark.asyncio
async def test_transcripts_are_family_scoped(authorized_client, tertiary_client, create_family_user):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Primary Student'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    _, grading_period_id = await _create_grading_period(
        authorized_client,
        name='Quarter 1',
        school_year_name='2025-2026',
        start='2025-08-01',
        end='2026-05-31',
    )
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
        due_date='2025-09-15T00:00:00Z',
        score=88,
        max_score=100,
    )

    generated = await authorized_client.post(TRANSCRIPTS['generate'], json={'student_id': student_id})
    assert generated.status_code == 201, generated.text
    transcript_id = generated.json()['id']

    other_family = await create_family_user(
        family_name='Other Family',
        email='other-transcript@example.com',
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

    other_list = await tertiary_client.get(TRANSCRIPTS['collection'])
    assert other_list.status_code == 200, other_list.text
    assert other_list.json() == []

    other_detail = await tertiary_client.get(TRANSCRIPTS['detail'].format(transcript_id=transcript_id))
    assert other_detail.status_code == 404, other_detail.text

    other_generate = await tertiary_client.post(TRANSCRIPTS['generate'], json={'student_id': student_id})
    assert other_generate.status_code == 404, other_generate.text
