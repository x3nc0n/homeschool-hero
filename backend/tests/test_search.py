from __future__ import annotations

import pytest

from tests.contracts import (
    ASSIGNMENTS,
    AUTH,
    CALENDAR,
    GRADES,
    INVITATIONS,
    SEARCH,
    STUDENTS,
    SUBJECTS,
    SUBMISSIONS,
    assignment_payload,
    calendar_event_payload,
    grade_payload,
    grading_period_payload,
    school_year_payload,
    student_payload,
    subject_payload,
    term_payload,
)
from tests.helpers import response_id, sync_csrf_header

CURRICULUM = {
    'packages': '/api/curriculum/packages',
    'units': '/api/curriculum/units',
    'lessons': '/api/curriculum/lessons',
}

RESOURCES = {
    'collection': '/api/resources',
}

PDF_BYTES = b'%PDF-1.4 search test document'


def curriculum_package_payload(
    school_year_id: int | str,
    subject_id: int | str,
    *,
    name: str,
) -> dict[str, object]:
    return {
        'school_year_id': school_year_id,
        'subject_id': subject_id,
        'name': name,
        'description': f'{name} description',
    }


def curriculum_unit_payload(package_id: int | str, *, name: str) -> dict[str, object]:
    return {
        'package_id': package_id,
        'name': name,
        'description': f'{name} description',
        'sequence_order': 1,
        'standards_tags': ['GEOM-1'],
    }


def curriculum_lesson_payload(unit_id: int | str, *, name: str) -> dict[str, object]:
    return {
        'unit_id': unit_id,
        'name': name,
        'description': f'{name} description',
        'sequence_order': 1,
        'estimated_duration_minutes': 45,
        'standards_tags': ['GEOM-1'],
    }


async def _seed_search_graph(client):
    school_year_response = await client.post(CALENDAR['school_years'], json=school_year_payload(name='Geometry Year'))
    assert school_year_response.status_code == 201, school_year_response.text
    school_year_id = response_id(school_year_response.json())

    term_response = await client.post(CALENDAR['terms'], json=term_payload(school_year_id, name='Geometry Term'))
    assert term_response.status_code == 201, term_response.text
    term_id = response_id(term_response.json())

    grading_period_response = await client.post(
        CALENDAR['grading_periods'],
        json=grading_period_payload(term_id, name='Geometry Quarter'),
    )
    assert grading_period_response.status_code == 201, grading_period_response.text
    grading_period_id = response_id(grading_period_response.json())

    subject_response = await client.post(SUBJECTS['collection'], json=subject_payload(name='Geometry'))
    assert subject_response.status_code == 201, subject_response.text
    subject_id = response_id(subject_response.json())

    student_response = await client.post(STUDENTS['collection'], json=student_payload('Geometry Student'))
    assert student_response.status_code == 201, student_response.text
    student_id = response_id(student_response.json())

    assignment = assignment_payload(subject_id)
    assignment['title'] = 'Geometry Proof Packet'
    assignment['description'] = 'Write a geometry proof and explain each step.'
    assignment['grading_period_id'] = grading_period_id
    assignment['targets'] = [{'student_id': student_id, 'status': 'assigned'}]
    assignment_response = await client.post(ASSIGNMENTS['collection'], json=assignment)
    assert assignment_response.status_code == 201, assignment_response.text
    assignment_id = response_id(assignment_response.json())

    submission_response = await client.post(
        SUBMISSIONS['collection'],
        data={'assignment_id': str(assignment_id), 'student_id': str(student_id)},
        files={'file': ('geometry.pdf', PDF_BYTES, 'application/pdf')},
    )
    assert submission_response.status_code == 201, submission_response.text
    submission_id = response_id(submission_response.json())

    grade = grade_payload(submission_id, student_id)
    grade['notes'] = 'Geometry reasoning is strong.'
    grade_response = await client.post(GRADES['collection'], json=grade)
    assert grade_response.status_code == 201, grade_response.text

    package_response = await client.post(
        CURRICULUM['packages'],
        json=curriculum_package_payload(school_year_id, subject_id, name='Geometry Mastery'),
    )
    assert package_response.status_code == 201, package_response.text
    package_id = response_id(package_response.json())

    unit_response = await client.post(CURRICULUM['units'], json=curriculum_unit_payload(package_id, name='Geometry Unit'))
    assert unit_response.status_code == 201, unit_response.text
    unit_id = response_id(unit_response.json())

    lesson_response = await client.post(CURRICULUM['lessons'], json=curriculum_lesson_payload(unit_id, name='Geometry Warmup'))
    assert lesson_response.status_code == 201, lesson_response.text
    assert lesson_response.status_code == 201, lesson_response.text

    resource_response = await client.post(
        RESOURCES['collection'],
        json={
            'name': 'Geometry note',
            'description': 'Geometry note about triangle congruence.',
            'resource_type': 'note',
            'tags': ['geometry'],
            'metadata': {'format': 'note'},
        },
    )
    assert resource_response.status_code == 201, resource_response.text

    invitation_response = await client.post(
        INVITATIONS['collection'],
        json={'email': 'geometry-helper@example.com', 'role': 'tutor', 'expires_in_days': 7},
    )
    assert invitation_response.status_code == 201, invitation_response.text

    event_response = await client.post(
        CALENDAR['events'],
        json=calendar_event_payload(
            school_year_id,
            name='Geometry attendance',
            notes='Geometry attendance reminder for lab day.',
        ),
    )
    assert event_response.status_code == 201, event_response.text

    return {
        'student_id': student_id,
        'subject_id': subject_id,
        'grading_period_id': grading_period_id,
        'term_id': term_id,
        'invitation_id': response_id(invitation_response.json()),
    }


@pytest.mark.asyncio
async def test_search_returns_results_across_entity_types(authorized_client):
    await _seed_search_graph(authorized_client)

    response = await authorized_client.get(f"{SEARCH['collection']}?q=geometry")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload['total'] >= 7
    facets = payload['facets']
    assert facets['assignment'] >= 1
    assert facets['grade'] >= 1
    assert facets['student'] >= 1
    assert facets['subject'] >= 1
    assert facets['curriculum'] >= 1
    assert facets['note'] >= 1
    assert facets['attendance_note'] >= 1
    assert facets['audit_log'] >= 1


@pytest.mark.asyncio
async def test_search_rbac_hides_other_students_data(authorized_client, secondary_client, create_family_user):
    subject_response = await authorized_client.post(SUBJECTS['collection'], json=subject_payload(name='Search Subject'))
    assert subject_response.status_code == 201, subject_response.text
    subject_id = response_id(subject_response.json())

    allowed_student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Visible Student'))
    assert allowed_student.status_code == 201, allowed_student.text
    allowed_student_id = response_id(allowed_student.json())

    private_student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Private Student'))
    assert private_student.status_code == 201, private_student.text
    private_student_id = response_id(private_student.json())

    assignment = assignment_payload(subject_id)
    assignment['title'] = 'Private Search Assignment'
    assignment['targets'] = [{'student_id': private_student_id, 'status': 'assigned'}]
    assignment_response = await authorized_client.post(ASSIGNMENTS['collection'], json=assignment)
    assert assignment_response.status_code == 201, assignment_response.text
    assignment_id = response_id(assignment_response.json())

    submission_response = await authorized_client.post(
        SUBMISSIONS['collection'],
        data={'assignment_id': str(assignment_id), 'student_id': str(private_student_id)},
        files={'file': ('private.pdf', PDF_BYTES, 'application/pdf')},
    )
    assert submission_response.status_code == 201, submission_response.text
    submission_id = response_id(submission_response.json())

    grade = grade_payload(submission_id, private_student_id)
    grade['notes'] = 'Private Student only note'
    grade_response = await authorized_client.post(GRADES['collection'], json=grade)
    assert grade_response.status_code == 201, grade_response.text

    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']
    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='viewer-search@example.com',
        password='viewerpass123',
        display_name='Viewer Search',
        role='student_viewer',
        student_id=allowed_student_id,
    )

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'viewer-search@example.com', 'password': 'viewerpass123', 'family_id': family_id},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    response = await secondary_client.get(f"{SEARCH['collection']}?q=Private")
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 0

    scoped_response = await secondary_client.get(f"{SEARCH['collection']}?student_id={private_student_id}")
    assert scoped_response.status_code == 403, scoped_response.text


@pytest.mark.asyncio
async def test_search_supports_pagination(authorized_client):
    for index in range(12):
        response = await authorized_client.post(STUDENTS['collection'], json=student_payload(f'Paged Student {index}'))
        assert response.status_code == 201, response.text

    response = await authorized_client.get(f"{SEARCH['collection']}?q=Paged&type=student&page=2&page_size=5")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload['total'] == 12
    assert payload['page'] == 2
    assert payload['page_size'] == 5
    assert payload['total_pages'] == 3
    assert len(payload['items']) == 5
    assert all(item['entity_type'] == 'student' for item in payload['items'])


@pytest.mark.asyncio
async def test_search_returns_empty_results(authorized_client):
    response = await authorized_client.get(f"{SEARCH['collection']}?q=does-not-exist")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload['items'] == []
    assert payload['total'] == 0
    assert payload['facets'] == {}
