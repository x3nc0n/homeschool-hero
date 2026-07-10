from __future__ import annotations

import pytest

from tests.contracts import ASSIGNMENTS, CALENDAR, GRADES, STUDENTS, SUBMISSIONS, assignment_payload, grading_period_payload, school_year_payload, student_payload, term_payload
from tests.helpers import assert_validation_error, response_id, update_resource


async def _create_grading_period(authorized_client) -> int:
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())

    term = await authorized_client.post(CALENDAR['terms'], json=term_payload(school_year_id))
    assert term.status_code == 201, term.text
    term_id = response_id(term.json())

    grading_period = await authorized_client.post(CALENDAR['grading_periods'], json=grading_period_payload(term_id))
    assert grading_period.status_code == 201, grading_period.text
    return response_id(grading_period.json())


@pytest.mark.asyncio
async def test_assignments_crud_happy_path_with_multi_student_targets(authorized_client, seeded_subject, seeded_student):
    grading_period_id = await _create_grading_period(authorized_client)
    second_student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Grace Hopper'))
    assert second_student.status_code in {200, 201}, second_student.text
    second_student_id = response_id(second_student.json())

    create = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(response_id(seeded_subject)),
            'category': 'project',
            'grading_period_id': grading_period_id,
            'weight': 2.5,
            'max_score': 50,
            'recurrence': 'weekly',
            'recurrence_end_date': '2026-06-05',
            'rubric_description': 'Demonstrate fraction fluency and explain your reasoning.',
            'attachments': ['uploads/rubrics/fractions.pdf'],
            'targets': [
                {'student_id': response_id(seeded_student), 'due_date': '2026-05-15T00:00:00Z', 'status': 'assigned'},
                {'student_id': second_student_id, 'due_date': '2026-05-17T00:00:00Z', 'status': 'assigned'},
            ],
        },
    )
    assert create.status_code == 201, create.text
    created = create.json()
    assignment_id = response_id(created)
    assert created['category'] == 'project'
    assert created['grading_period_id'] == grading_period_id
    assert created['weight'] == 2.5
    assert created['max_score'] == 50
    assert created['recurrence'] == 'weekly'
    assert created['targets'][0]['student_id'] == response_id(seeded_student)
    assert len(created['targets']) == 2

    listing = await authorized_client.get(ASSIGNMENTS['collection'], params={'page': 1, 'page_size': 10})
    assert listing.status_code == 200, listing.text
    listing_payload = listing.json()
    assert listing_payload['total'] == 1
    assert listing_payload['items'][0]['id'] == assignment_id

    detail = await authorized_client.get(ASSIGNMENTS['detail'].format(assignment_id=assignment_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()['title'] == 'Fractions Worksheet'
    assert detail.json()['grading_period']['id'] == grading_period_id

    update = await update_resource(
        authorized_client,
        ASSIGNMENTS['detail'].format(assignment_id=assignment_id),
        {
            **assignment_payload(response_id(seeded_subject)),
            'status': 'graded',
            'category': 'test',
            'grading_period_id': grading_period_id,
            'weight': 3.0,
            'max_score': 60,
            'recurrence': 'weekly',
            'recurrence_end_date': '2026-06-12',
            'rubric_description': 'Updated rubric',
            'attachments': ['uploads/rubrics/fractions-v2.pdf'],
            'due_date': '2026-05-18T00:00:00Z',
            'targets': [
                {'student_id': response_id(seeded_student), 'due_date': '2026-05-18T00:00:00Z', 'status': 'graded'},
                {'student_id': second_student_id, 'due_date': '2026-05-19T00:00:00Z', 'status': 'assigned'},
            ],
        },
    )
    assert update.status_code == 200, update.text
    updated = update.json()
    assert updated['status'] == 'graded'
    assert updated['category'] == 'test'
    assert updated['weight'] == 3.0
    history_fields = {entry['field'] for entry in updated['status_history']}
    assert 'due_date' in history_fields
    assert 'weight' in history_fields
    assert 'target_due_date' in history_fields

    status_update = await authorized_client.patch(
        ASSIGNMENTS['status'].format(assignment_id=assignment_id),
        json={'status': 'complete'},
    )
    assert status_update.status_code == 200, status_update.text
    assert status_update.json()['status'] == 'complete'

    delete = await authorized_client.delete(ASSIGNMENTS['detail'].format(assignment_id=assignment_id))
    assert delete.status_code == 204, delete.text


@pytest.mark.asyncio
async def test_assignments_support_filtering_and_pagination(authorized_client, seeded_subject, seeded_student):
    grading_period_id = await _create_grading_period(authorized_client)
    second_student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Katherine Johnson'))
    assert second_student.status_code in {200, 201}, second_student.text
    second_student_id = response_id(second_student.json())

    first = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(response_id(seeded_subject)),
            'title': 'Weekly homework',
            'category': 'homework',
            'grading_period_id': grading_period_id,
            'targets': [{'student_id': response_id(seeded_student), 'due_date': '2026-05-15T00:00:00Z', 'status': 'assigned'}],
        },
    )
    assert first.status_code == 201, first.text

    second = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(response_id(seeded_subject)),
            'title': 'Unit quiz',
            'category': 'quiz',
            'due_date': '2026-05-25T00:00:00Z',
            'targets': [{'student_id': second_student_id, 'due_date': '2026-05-25T00:00:00Z', 'status': 'submitted'}],
        },
    )
    assert second.status_code == 201, second.text

    category_filtered = await authorized_client.get(ASSIGNMENTS['collection'], params={'category': 'quiz'})
    assert category_filtered.status_code == 200, category_filtered.text
    assert [item['title'] for item in category_filtered.json()['items']] == ['Unit quiz']

    grading_period_filtered = await authorized_client.get(
        ASSIGNMENTS['collection'],
        params={'grading_period_id': grading_period_id},
    )
    assert grading_period_filtered.status_code == 200, grading_period_filtered.text
    assert grading_period_filtered.json()['total'] == 1

    student_filtered = await authorized_client.get(
        ASSIGNMENTS['collection'],
        params={'student_id': second_student_id},
    )
    assert student_filtered.status_code == 200, student_filtered.text
    assert [item['title'] for item in student_filtered.json()['items']] == ['Unit quiz']

    status_filtered = await authorized_client.get(
        ASSIGNMENTS['collection'],
        params={'status': 'submitted'},
    )
    assert status_filtered.status_code == 200, status_filtered.text
    assert [item['title'] for item in status_filtered.json()['items']] == ['Unit quiz']

    date_filtered = await authorized_client.get(
        ASSIGNMENTS['collection'],
        params={'due_from': '2026-05-20', 'due_to': '2026-05-30'},
    )
    assert date_filtered.status_code == 200, date_filtered.text
    assert [item['title'] for item in date_filtered.json()['items']] == ['Unit quiz']

    paged = await authorized_client.get(
        ASSIGNMENTS['collection'],
        params={'page': 1, 'page_size': 1},
    )
    assert paged.status_code == 200, paged.text
    assert paged.json()['page_size'] == 1
    assert paged.json()['total_pages'] == 2


@pytest.mark.asyncio
async def test_assignments_preserve_backward_compatible_payloads(authorized_client, seeded_subject):
    create = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json=assignment_payload(response_id(seeded_subject)),
    )
    assert create.status_code == 201, create.text
    payload = create.json()
    assert payload['targets'] == []
    assert payload['category'] == 'homework'
    assert payload['status_history'] == []

    listing = await authorized_client.get(ASSIGNMENTS['collection'])
    assert listing.status_code == 200, listing.text
    assert listing.json()['items'][0]['id'] == payload['id']


@pytest.mark.asyncio
async def test_assignment_target_status_updates_with_submission_and_grade(
    authorized_client,
    seeded_subject,
    seeded_student,
):
    assignment_response = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={
            **assignment_payload(response_id(seeded_subject)),
            'targets': [{'student_id': response_id(seeded_student), 'due_date': '2026-05-15T00:00:00Z', 'status': 'assigned'}],
        },
    )
    assert assignment_response.status_code == 201, assignment_response.text
    assignment_id = response_id(assignment_response.json())

    submission = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={'assignment_id': str(assignment_id), 'student_id': str(response_id(seeded_student))},
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

    after_submission = await authorized_client.get(ASSIGNMENTS['detail'].format(assignment_id=assignment_id))
    assert after_submission.status_code == 200, after_submission.text
    assert after_submission.json()['targets'][0]['status'] == 'submitted'

    grade = await authorized_client.post(
        GRADES['collection'],
        json={
            'submission_id': response_id(submission.json()),
            'student_id': response_id(seeded_student),
            'score': 45,
            'max_score': 50,
            'letter_grade': 'A-',
            'notes': 'Great work',
            'graded_by': 'human',
        },
    )
    assert grade.status_code == 201, grade.text

    after_grade = await authorized_client.get(ASSIGNMENTS['detail'].format(assignment_id=assignment_id))
    assert after_grade.status_code == 200, after_grade.text
    assert after_grade.json()['targets'][0]['status'] == 'graded'


@pytest.mark.asyncio
async def test_assignments_reject_invalid_payload(authorized_client):
    response = await authorized_client.post(ASSIGNMENTS['collection'], json={'status': 'pending'})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_assignments_return_404_for_missing_id(authorized_client):
    response = await authorized_client.get(ASSIGNMENTS['detail'].format(assignment_id=999999))

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_assignments_require_authentication(async_client):
    response = await async_client.get(ASSIGNMENTS['collection'])

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_assignments_past_due_filter(authorized_client, seeded_subject, seeded_student):
    """?status=past_due returns ungraded overdue assignments and excludes graded and future ones."""
    from datetime import UTC, date, datetime, timedelta

    today = datetime.now(UTC).date()
    subject_id = response_id(seeded_subject)

    def _iso(d: date) -> str:
        return datetime.combine(d, datetime.min.time(), tzinfo=UTC).isoformat()

    # Past-due, pending — should appear in past_due results
    r1 = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={**assignment_payload(subject_id), 'title': 'Overdue Pending', 'due_date': _iso(today - timedelta(days=2)), 'status': 'pending'},
    )
    assert r1.status_code == 201, r1.text

    # Past-due, graded — must NOT appear
    r2 = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={**assignment_payload(subject_id), 'title': 'Overdue Graded', 'due_date': _iso(today - timedelta(days=4)), 'status': 'graded'},
    )
    assert r2.status_code == 201, r2.text

    # Future, pending — must NOT appear
    r3 = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json={**assignment_payload(subject_id), 'title': 'Future Pending', 'due_date': _iso(today + timedelta(days=2)), 'status': 'pending'},
    )
    assert r3.status_code == 201, r3.text

    response = await authorized_client.get(ASSIGNMENTS['collection'], params={'status': 'past_due'})
    assert response.status_code == 200, response.text
    data = response.json()
    titles = [item['title'] for item in data['items']]

    assert 'Overdue Pending' in titles, 'Past-due ungraded assignment must be returned by ?status=past_due'
    assert 'Overdue Graded' not in titles, 'Graded assignment must not be returned by ?status=past_due'
    assert 'Future Pending' not in titles, 'Future assignment must not be returned by ?status=past_due'
