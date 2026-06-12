from __future__ import annotations

import pytest

from tests.contracts import ASSIGNMENTS, CURRICULUM, RESOURCES, school_year_payload
from tests.helpers import response_id


def curriculum_import_payload(*, name: str = '6th Grade Core', subject_count: int = 1) -> dict[str, object]:
    subjects: list[dict[str, object]] = []
    for index in range(subject_count):
        subject_name = 'Math' if index == 0 else f'Subject {index + 1}'
        lesson_name = 'Ratios Warmup' if index == 0 else f'Lesson {index + 1}'
        subjects.append(
            {
                'name': subject_name,
                'description': f'{subject_name} scope and sequence.',
                'metadata': {
                    'grade_levels': ['6'],
                    'standards_alignment': [f'STD-{index + 1}'],
                    'estimated_hours': 120,
                    'prerequisites': ['5th grade readiness'],
                },
                'units': [
                    {
                        'name': f'Unit {index + 1}',
                        'metadata': {
                            'grade_levels': ['6'],
                            'standards_alignment': [f'UNIT-{index + 1}'],
                            'estimated_hours': 12,
                        },
                        'lessons': [
                            {
                                'name': lesson_name,
                                'description': 'Build confidence with a short launch activity.',
                                'estimated_minutes': 45,
                                'objectives': ['Explain the concept', 'Complete the starter practice'],
                                'resources': [
                                    {
                                        'name': 'Workbook',
                                        'resource_type': 'worksheet',
                                        'url': f'https://example.com/{index + 1}/workbook',
                                        'tags': ['worksheet'],
                                        'metadata': {'format': 'pdf'},
                                    }
                                ],
                                'metadata': {
                                    'grade_levels': ['6'],
                                    'standards_alignment': [f'LESSON-{index + 1}'],
                                    'prerequisites': ['Lesson zero'],
                                },
                            }
                        ],
                    }
                ],
            }
        )

    return {
        'schema_version': '1.0',
        'name': name,
        'description': 'Imported curriculum for backend Phase 1.',
        'source': 'manual',
        'metadata': {
            'grade_levels': ['6'],
            'standards_alignment': ['ROOT-1'],
            'estimated_hours': 720,
            'prerequisites': ['Foundational reading'],
        },
        'subjects': subjects,
    }


@pytest.mark.asyncio
async def test_curriculum_import_schema_and_crud(authorized_client):
    schema_response = await authorized_client.get(CURRICULUM['import_schema'])
    assert schema_response.status_code == 200, schema_response.text
    schema_payload = schema_response.json()
    assert 'subjects' in schema_payload['properties']
    assert 'metadata' in schema_payload['properties']

    create = await authorized_client.post(CURRICULUM['import_create'], json=curriculum_import_payload())
    assert create.status_code == 201, create.text
    curriculum_id = response_id(create.json())
    assert create.json()['subject_count'] == 1
    assert create.json()['lesson_count'] == 1
    assert create.json()['metadata']['estimated_hours'] == 720

    listing = await authorized_client.get(CURRICULUM['imports'])
    assert listing.status_code == 200, listing.text
    assert [item['id'] for item in listing.json()] == [curriculum_id]
    assert listing.json()[0]['is_activated'] is False

    detail = await authorized_client.get(CURRICULUM['import_detail'].format(curriculum_id=curriculum_id))
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload['subjects'][0]['units'][0]['lessons'][0]['objectives'] == [
        'Explain the concept',
        'Complete the starter practice',
    ]
    assert detail_payload['subjects'][0]['units'][0]['lessons'][0]['resources'][0]['url'].startswith('https://example.com/')

    delete = await authorized_client.delete(CURRICULUM['import_detail'].format(curriculum_id=curriculum_id))
    assert delete.status_code == 204, delete.text

    missing = await authorized_client.get(CURRICULUM['import_detail'].format(curriculum_id=curriculum_id))
    assert missing.status_code == 404, missing.text


@pytest.mark.asyncio
async def test_curriculum_activation_creates_packages_resources_and_assignments(authorized_client):
    create = await authorized_client.post(
        CURRICULUM['import_create'],
        json=curriculum_import_payload(name='Activation Curriculum', subject_count=2),
    )
    assert create.status_code == 201, create.text
    curriculum_id = response_id(create.json())

    school_year_create = await authorized_client.post(
        '/api/calendar/school-years',
        json=school_year_payload(name='2026-2027', start_date='2026-08-17', end_date='2027-05-28', is_active=False),
    )
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    activate = await authorized_client.post(
        CURRICULUM['import_activate'].format(curriculum_id=curriculum_id),
        json={'school_year_id': school_year_id, 'generate_assignments': True},
    )
    assert activate.status_code == 200, activate.text
    activation_payload = activate.json()
    assert len(activation_payload['package_ids']) == 2
    assert len(activation_payload['assignment_ids']) == 2

    packages = await authorized_client.get(CURRICULUM['packages'], params={'school_year_id': school_year_id})
    assert packages.status_code == 200, packages.text
    package_payload = packages.json()
    assert len(package_payload) == 2
    assert package_payload[0]['units'][0]['lessons'][0]['name']

    resources = await authorized_client.get(RESOURCES['collection'])
    assert resources.status_code == 200, resources.text
    assert len(resources.json()) == 2

    assignments = await authorized_client.get(ASSIGNMENTS['collection'])
    assert assignments.status_code == 200, assignments.text
    assert len(assignments.json()['items']) == 2
    assert assignments.json()['items'][0]['attachments'][0].startswith('https://example.com/')

    detail = await authorized_client.get(CURRICULUM['import_detail'].format(curriculum_id=curriculum_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()['is_activated'] is True
    assert len(detail.json()['last_activation_summary']['lesson_ids']) == 2

    duplicate_activate = await authorized_client.post(
        CURRICULUM['import_activate'].format(curriculum_id=curriculum_id),
        json={'school_year_id': school_year_id},
    )
    assert duplicate_activate.status_code == 409, duplicate_activate.text


@pytest.mark.asyncio
async def test_curriculum_import_enforces_limits_and_family_isolation(authorized_client, secondary_client, create_family_user):
    oversized = await authorized_client.post(
        CURRICULUM['import_create'],
        json=curriculum_import_payload(name='Too Many Subjects', subject_count=26),
    )
    assert oversized.status_code == 422, oversized.text

    create = await authorized_client.post(CURRICULUM['import_create'], json=curriculum_import_payload(name='Protected Curriculum'))
    assert create.status_code == 201, create.text
    curriculum_id = response_id(create.json())

    other_user = await create_family_user(
        family_name='Another Family',
        email='other@example.com',
        password='other-password',
        display_name='Other User',
    )
    login = await secondary_client.post(
        '/api/auth/login',
        json={'email': other_user['email'], 'password': other_user['password'], 'family_id': other_user['family_id']},
    )
    assert login.status_code == 200, login.text

    isolated = await secondary_client.get(CURRICULUM['import_detail'].format(curriculum_id=curriculum_id))
    assert isolated.status_code == 404, isolated.text
