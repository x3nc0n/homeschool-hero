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
    assignment_payload,
    grading_period_payload,
    school_year_payload,
    student_payload,
    subject_payload,
    term_payload,
)
from tests.helpers import response_id, sync_csrf_header, update_resource


async def _create_grading_period(authorized_client) -> int:
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text
    term = await authorized_client.post(CALENDAR['terms'], json=term_payload(response_id(school_year.json())))
    assert term.status_code == 201, term.text
    grading_period = await authorized_client.post(CALENDAR['grading_periods'], json=grading_period_payload(response_id(term.json())))
    assert grading_period.status_code == 201, grading_period.text
    return response_id(grading_period.json())


async def _create_graded_assignment(
    authorized_client,
    *,
    subject_id: int,
    student_id: int,
    grading_period_id: int | None,
    title: str,
    category: str,
    due_date: str,
    score: float,
    max_score: float,
) -> tuple[dict[str, object], dict[str, object]]:
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
                'gradebook.png',
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
            'notes': f'{title} scored',
        },
    )
    assert grade.status_code == 201, grade.text
    return assignment.json(), grade.json()


@pytest.mark.asyncio
async def test_gradebook_calculates_weighted_categories_with_drop_lowest(authorized_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload())
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    subject = await authorized_client.post(SUBJECTS['collection'], json=subject_payload())
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())
    grading_period_id = await _create_grading_period(authorized_client)

    categories = await authorized_client.put(
        GRADEBOOK['categories'],
        json={
            'subject_id': subject_id,
            'categories': [
                {'name': 'homework', 'weight': 0.4, 'drop_lowest': 1},
                {'name': 'test', 'weight': 0.6, 'drop_lowest': 0},
            ],
        },
    )
    assert categories.status_code == 200, categories.text

    await _create_graded_assignment(
        authorized_client,
        subject_id=subject_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Homework 1',
        category='homework',
        due_date='2026-05-12T00:00:00Z',
        score=80,
        max_score=100,
    )
    await _create_graded_assignment(
        authorized_client,
        subject_id=subject_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Homework 2',
        category='homework',
        due_date='2026-05-13T00:00:00Z',
        score=60,
        max_score=100,
    )
    await _create_graded_assignment(
        authorized_client,
        subject_id=subject_id,
        student_id=student_id,
        grading_period_id=grading_period_id,
        title='Unit Test',
        category='test',
        due_date='2026-05-14T00:00:00Z',
        score=90,
        max_score=100,
    )

    gradebook = await authorized_client.get(
        GRADEBOOK['detail'].format(student_id=student_id),
        params={'subject_id': subject_id, 'grading_period_id': grading_period_id},
    )
    assert gradebook.status_code == 200, gradebook.text
    payload = gradebook.json()
    assert payload['gpa'] == 3.0
    assert len(payload['subjects']) == 1
    subject_view = payload['subjects'][0]
    assert subject_view['overall_percent'] == 86.0
    assert subject_view['letter_grade'] == 'B'
    homework = next(category for category in subject_view['categories'] if category['name'] == 'homework')
    assert homework['average_percent'] == 80.0
    assert sum(1 for item in homework['items'] if item['is_dropped']) == 1
    unit_test = next(item for item in next(category for category in subject_view['categories'] if category['name'] == 'test')['items'] if item['assignment_title'] == 'Unit Test')
    assert unit_test['running_overall_percent'] == 86.0

    summary = await authorized_client.get(GRADEBOOK['summary'].format(student_id=student_id))
    assert summary.status_code == 200, summary.text
    assert summary.json()['subjects'][0]['letter_grade'] == 'B'
    assert summary.json()['gpa'] == 3.0

    recalculated = await authorized_client.post(
        GRADEBOOK['calculate'],
        json={'student_id': student_id, 'subject_id': subject_id, 'grading_period_id': grading_period_id},
    )
    assert recalculated.status_code == 200, recalculated.text
    assert recalculated.json()['subjects'][0]['overall_percent'] == 86.0


@pytest.mark.asyncio
async def test_gradebook_supports_percentage_mode_averaging(authorized_client):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Grace Hopper'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    subject = await authorized_client.post(
        SUBJECTS['collection'],
        json={**subject_payload('Science', '#16a34a'), 'grading_mode': 'percentage'},
    )
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
        grading_period_id=None,
        title='Lab 1',
        category='homework',
        due_date='2026-05-15T00:00:00Z',
        score=5,
        max_score=10,
    )
    await _create_graded_assignment(
        authorized_client,
        subject_id=subject_id,
        student_id=student_id,
        grading_period_id=None,
        title='Lab 2',
        category='homework',
        due_date='2026-05-16T00:00:00Z',
        score=45,
        max_score=50,
    )

    gradebook = await authorized_client.get(
        GRADEBOOK['detail'].format(student_id=student_id),
        params={'subject_id': subject_id},
    )
    assert gradebook.status_code == 200, gradebook.text
    subject_view = gradebook.json()['subjects'][0]
    assert subject_view['grading_mode'] == 'percentage'
    assert subject_view['overall_percent'] == 70.0

    trends = await authorized_client.get(GRADEBOOK['trends'].format(student_id=student_id), params={'subject_id': subject_id})
    assert trends.status_code == 200, trends.text
    assert len(trends.json()['series'][0]['points']) == 2
    assert trends.json()['series'][0]['points'][-1]['overall_percent'] == 70.0


@pytest.mark.asyncio
async def test_gradebook_scales_and_categories_are_family_scoped(
    authorized_client,
    tertiary_client,
    create_family_user,
):
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Katherine Johnson'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())
    subject = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('History', '#7c3aed'))
    assert subject.status_code == 201, subject.text
    subject_id = response_id(subject.json())

    initial_scales = await authorized_client.get(GRADEBOOK['scales'])
    assert initial_scales.status_code == 200, initial_scales.text
    default_scale = initial_scales.json()[0]

    updated_scales = await authorized_client.put(
        GRADEBOOK['scales'],
        json={
            'scales': [
                {
                    'id': default_scale['id'],
                    'name': default_scale['name'],
                    'is_default': False,
                    'ranges': default_scale['ranges'],
                },
                {
                    'name': 'Honors 4.0',
                    'is_default': True,
                    'ranges': [
                        {'letter': 'A', 'min': 85, 'max': 100, 'gpa_points': 4.0},
                        {'letter': 'B', 'min': 75, 'max': 84.99, 'gpa_points': 3.0},
                        {'letter': 'C', 'min': 65, 'max': 74.99, 'gpa_points': 2.0},
                        {'letter': 'D', 'min': 55, 'max': 64.99, 'gpa_points': 1.0},
                        {'letter': 'F', 'min': 0, 'max': 54.99, 'gpa_points': 0.0},
                    ],
                },
            ]
        },
    )
    assert updated_scales.status_code == 200, updated_scales.text
    honors_scale = next(scale for scale in updated_scales.json() if scale['name'] == 'Honors 4.0')

    subject_update = await update_resource(
        authorized_client,
        SUBJECTS['detail'].format(subject_id=subject_id),
        {**subject_payload('History', '#7c3aed'), 'grading_mode': 'points', 'grade_scale_id': honors_scale['id']},
    )
    assert subject_update.status_code == 200, subject_update.text

    categories = await authorized_client.put(
        GRADEBOOK['categories'],
        json={'subject_id': subject_id, 'categories': [{'name': 'homework', 'weight': 1.0, 'drop_lowest': 0}]},
    )
    assert categories.status_code == 200, categories.text

    await _create_graded_assignment(
        authorized_client,
        subject_id=subject_id,
        student_id=student_id,
        grading_period_id=None,
        title='Essay',
        category='homework',
        due_date='2026-05-18T00:00:00Z',
        score=86,
        max_score=100,
    )
    summary = await authorized_client.get(GRADEBOOK['summary'].format(student_id=student_id))
    assert summary.status_code == 200, summary.text
    assert summary.json()['subjects'][0]['letter_grade'] == 'A'
    assert summary.json()['subjects'][0]['gpa_points'] == 4.0

    other_family = await create_family_user(
        family_name='Other Family',
        email='other-owner@example.com',
        password='strongpass678',
        display_name='Owner Other',
        role='parent',
        is_owner=True,
    )
    login = await tertiary_client.post(
        AUTH['login'],
        json={'email': 'other-owner@example.com', 'password': 'strongpass678', 'family_id': other_family['family_id']},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(tertiary_client)

    other_scales = await tertiary_client.get(GRADEBOOK['scales'])
    assert other_scales.status_code == 200, other_scales.text
    assert [scale['name'] for scale in other_scales.json()] == ['Default 4.0 Scale']

    forbidden_categories = await tertiary_client.get(GRADEBOOK['categories'], params={'subject_id': subject_id})
    assert forbidden_categories.status_code == 404, forbidden_categories.text
