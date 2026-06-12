from __future__ import annotations

import json

import pytest

from tests.contracts import AUTH, school_year_payload, subject_payload
from tests.helpers import response_id, sync_csrf_header, update_resource

CURRICULUM = {
    'packages': '/api/curriculum/packages',
    'package_detail': '/api/curriculum/packages/{package_id}',
    'package_clone': '/api/curriculum/packages/{package_id}/clone',
    'units': '/api/curriculum/units',
    'unit_detail': '/api/curriculum/units/{unit_id}',
    'lessons': '/api/curriculum/lessons',
    'lesson_detail': '/api/curriculum/lessons/{lesson_id}',
    'lesson_resource_detail': '/api/curriculum/lessons/{lesson_id}/resources/{resource_id}',
}

RESOURCES = {
    'collection': '/api/resources',
    'detail': '/api/resources/{resource_id}',
}


def curriculum_package_payload(
    school_year_id: int | str,
    subject_id: int | str,
    *,
    name: str = 'Core Math 2025',
    description: str | None = 'Daily spiral review and mastery lessons.',
) -> dict[str, object]:
    payload: dict[str, object] = {
        'school_year_id': school_year_id,
        'subject_id': subject_id,
        'name': name,
    }
    if description is not None:
        payload['description'] = description
    return payload


def curriculum_unit_payload(
    package_id: int | str,
    *,
    name: str = 'Unit 1: Number Sense',
    description: str | None = 'Build number fluency.',
    sequence_order: int = 1,
    standards_tags: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        'package_id': package_id,
        'name': name,
        'sequence_order': sequence_order,
        'standards_tags': standards_tags or ['MATH-NS.1'],
    }
    if description is not None:
        payload['description'] = description
    return payload


def curriculum_lesson_payload(
    unit_id: int | str,
    *,
    name: str = 'Lesson 1: Place value warm-up',
    description: str | None = 'Use base-ten blocks and quick checks.',
    sequence_order: int = 1,
    estimated_duration_minutes: int | None = 45,
    standards_tags: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        'unit_id': unit_id,
        'name': name,
        'sequence_order': sequence_order,
        'standards_tags': standards_tags or ['MATH-NS.1'],
    }
    if description is not None:
        payload['description'] = description
    if estimated_duration_minutes is not None:
        payload['estimated_duration_minutes'] = estimated_duration_minutes
    return payload


def resource_payload(
    *,
    name: str = 'Base ten blocks',
    description: str | None = 'Hands-on manipulative guide.',
    resource_type: str = 'link',
    url: str | None = 'https://example.com/base-ten',
    tags: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        'name': name,
        'resource_type': resource_type,
        'tags': tags or ['manipulative', 'math'],
        'metadata': metadata or {'format': 'pdf'},
    }
    if description is not None:
        payload['description'] = description
    if url is not None:
        payload['url'] = url
    return payload


async def _seed_package_graph(client):
    school_year_create = await client.post('/api/calendar/school-years', json=school_year_payload())
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    subject_create = await client.post('/api/subjects', json=subject_payload())
    assert subject_create.status_code == 201, subject_create.text
    subject_id = response_id(subject_create.json())

    package_create = await client.post(CURRICULUM['packages'], json=curriculum_package_payload(school_year_id, subject_id))
    assert package_create.status_code == 201, package_create.text
    package_id = response_id(package_create.json())

    unit_create = await client.post(CURRICULUM['units'], json=curriculum_unit_payload(package_id))
    assert unit_create.status_code == 201, unit_create.text
    unit_id = response_id(unit_create.json())

    lesson_create = await client.post(CURRICULUM['lessons'], json=curriculum_lesson_payload(unit_id))
    assert lesson_create.status_code == 201, lesson_create.text
    lesson_id = response_id(lesson_create.json())

    return {
        'school_year_id': school_year_id,
        'subject_id': subject_id,
        'package_id': package_id,
        'unit_id': unit_id,
        'lesson_id': lesson_id,
    }


@pytest.mark.asyncio
async def test_curriculum_package_unit_lesson_crud_and_clone(authorized_client):
    seeded = await _seed_package_graph(authorized_client)

    package_detail = await authorized_client.get(CURRICULUM['package_detail'].format(package_id=seeded['package_id']))
    assert package_detail.status_code == 200, package_detail.text
    detail_payload = package_detail.json()
    assert detail_payload['units'][0]['lessons'][0]['name'] == 'Lesson 1: Place value warm-up'

    updated_package = await update_resource(
        authorized_client,
        CURRICULUM['package_detail'].format(package_id=seeded['package_id']),
        curriculum_package_payload(
            seeded['school_year_id'],
            seeded['subject_id'],
            name='Core Math 2025 Revised',
            description='Updated pacing guide.',
        ),
    )
    assert updated_package.status_code == 200, updated_package.text
    assert updated_package.json()['name'] == 'Core Math 2025 Revised'

    updated_unit = await update_resource(
        authorized_client,
        CURRICULUM['unit_detail'].format(unit_id=seeded['unit_id']),
        curriculum_unit_payload(
            seeded['package_id'],
            name='Unit 1: Number Foundations',
            sequence_order=2,
            standards_tags=['MATH-NS.2'],
        ),
    )
    assert updated_unit.status_code == 200, updated_unit.text
    assert updated_unit.json()['sequence_order'] == 2

    updated_lesson = await update_resource(
        authorized_client,
        CURRICULUM['lesson_detail'].format(lesson_id=seeded['lesson_id']),
        curriculum_lesson_payload(
            seeded['unit_id'],
            name='Lesson 1: Place value checks',
            estimated_duration_minutes=60,
            standards_tags=['MATH-NS.2', 'MATH-NS.3'],
        ),
    )
    assert updated_lesson.status_code == 200, updated_lesson.text
    assert updated_lesson.json()['estimated_duration_minutes'] == 60

    target_school_year_create = await authorized_client.post(
        '/api/calendar/school-years',
        json=school_year_payload(name='2026-2027', start_date='2026-08-17', end_date='2027-05-28', is_active=False),
    )
    assert target_school_year_create.status_code == 201, target_school_year_create.text
    target_school_year_id = response_id(target_school_year_create.json())

    clone = await authorized_client.post(
        CURRICULUM['package_clone'].format(package_id=seeded['package_id']),
        json={'target_school_year_id': target_school_year_id, 'name': 'Core Math 2026'},
    )
    assert clone.status_code == 201, clone.text
    clone_payload = clone.json()
    assert clone_payload['school_year_id'] == target_school_year_id
    assert clone_payload['units'][0]['lessons'][0]['name'] == 'Lesson 1: Place value checks'

    delete_lesson = await authorized_client.delete(CURRICULUM['lesson_detail'].format(lesson_id=seeded['lesson_id']))
    assert delete_lesson.status_code == 204, delete_lesson.text
    delete_unit = await authorized_client.delete(CURRICULUM['unit_detail'].format(unit_id=seeded['unit_id']))
    assert delete_unit.status_code == 204, delete_unit.text
    delete_package = await authorized_client.delete(CURRICULUM['package_detail'].format(package_id=seeded['package_id']))
    assert delete_package.status_code == 204, delete_package.text


@pytest.mark.asyncio
async def test_resource_crud_file_upload_search_and_linking(authorized_client):
    seeded = await _seed_package_graph(authorized_client)

    link_resource_create = await authorized_client.post(
        RESOURCES['collection'],
        json=resource_payload(tags=['math', 'warmup'], metadata={'format': 'web'}),
    )
    assert link_resource_create.status_code == 201, link_resource_create.text
    link_resource_id = response_id(link_resource_create.json())

    file_resource_create = await authorized_client.post(
        RESOURCES['collection'],
        data={
            'name': 'Printable practice',
            'description': 'PDF worksheet',
            'resource_type': 'file',
            'tags': json.dumps(['worksheet', 'math']),
            'metadata': json.dumps({'format': 'pdf'}),
        },
        files={'file': ('practice.pdf', b'%PDF-1.4 curriculum practice', 'application/pdf')},
    )
    assert file_resource_create.status_code == 201, file_resource_create.text
    file_resource_payload = file_resource_create.json()
    file_resource_id = response_id(file_resource_payload)
    assert file_resource_payload['file_url'].startswith('/api/files/resources/')

    search = await authorized_client.get(f"{RESOURCES['collection']}?tag=worksheet&search=Printable")
    assert search.status_code == 200, search.text
    assert [resource['id'] for resource in search.json()] == [file_resource_id]

    link = await authorized_client.post(
        CURRICULUM['lesson_resource_detail'].format(lesson_id=seeded['lesson_id'], resource_id=link_resource_id)
    )
    assert link.status_code == 204, link.text

    lesson_detail = await authorized_client.get(CURRICULUM['lesson_detail'].format(lesson_id=seeded['lesson_id']))
    assert lesson_detail.status_code == 200, lesson_detail.text
    assert lesson_detail.json()['resources'][0]['id'] == link_resource_id

    resource_detail = await authorized_client.get(RESOURCES['detail'].format(resource_id=link_resource_id))
    assert resource_detail.status_code == 200, resource_detail.text
    assert resource_detail.json()['lesson_ids'] == [seeded['lesson_id']]

    resource_update = await update_resource(
        authorized_client,
        RESOURCES['detail'].format(resource_id=link_resource_id),
        resource_payload(name='Base ten blocks guide', tags=['math', 'guide'], metadata={'format': 'html'}),
    )
    assert resource_update.status_code == 200, resource_update.text
    assert resource_update.json()['name'] == 'Base ten blocks guide'

    unlink = await authorized_client.delete(
        CURRICULUM['lesson_resource_detail'].format(lesson_id=seeded['lesson_id'], resource_id=link_resource_id)
    )
    assert unlink.status_code == 204, unlink.text

    delete_file_resource = await authorized_client.delete(RESOURCES['detail'].format(resource_id=file_resource_id))
    assert delete_file_resource.status_code == 204, delete_file_resource.text
    delete_link_resource = await authorized_client.delete(RESOURCES['detail'].format(resource_id=link_resource_id))
    assert delete_link_resource.status_code == 204, delete_link_resource.text


@pytest.mark.asyncio
async def test_curriculum_family_isolation_and_tutor_access(
    authorized_client,
    secondary_client,
    tertiary_client,
    create_family_user,
):
    seeded = await _seed_package_graph(authorized_client)

    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']

    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='tutor-curriculum@example.com',
        password='strongpass997',
        display_name='Tutor User',
        role='tutor',
    )
    other_family = await create_family_user(
        family_name='Other Family',
        email='other-curriculum@example.com',
        password='strongpass996',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
    )

    tutor_login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'tutor-curriculum@example.com', 'password': 'strongpass997', 'family_id': family_id},
    )
    assert tutor_login.status_code == 200, tutor_login.text
    sync_csrf_header(secondary_client)

    tutor_resource = await secondary_client.post(
        RESOURCES['collection'],
        json=resource_payload(name='Tutor shared note', resource_type='note', url=None, metadata={'format': 'note'}),
    )
    assert tutor_resource.status_code == 201, tutor_resource.text

    other_login = await tertiary_client.post(
        AUTH['login'],
        json={'email': 'other-curriculum@example.com', 'password': 'strongpass996', 'family_id': other_family['family_id']},
    )
    assert other_login.status_code == 200, other_login.text
    sync_csrf_header(tertiary_client)

    other_package = await tertiary_client.get(CURRICULUM['package_detail'].format(package_id=seeded['package_id']))
    assert other_package.status_code == 404, other_package.text

    other_resource = await tertiary_client.get(RESOURCES['detail'].format(resource_id=response_id(tutor_resource.json())))
    assert other_resource.status_code == 404, other_resource.text
