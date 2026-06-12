from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from tests.contracts import ASSIGNMENTS, AUTH, CALENDAR, STUDENTS, school_year_payload, student_payload
from tests.helpers import assert_validation_error, sync_csrf_header

CURRICULUM_IMPORT = {
    'collection': '/api/curriculum/',
    'detail': '/api/curriculum/{curriculum_id}',
    'import': '/api/curriculum/import',
    'activate': '/api/curriculum/{curriculum_id}/activate',
    'schema': '/api/curriculum/schema',
}

PENDING_IMPORT_REASON = 'Issue #165 Phase 1 curriculum import endpoints are pending Ray implementation.'
MAX_CURRICULUM_LESSONS = 1000
VALID_GRADE_LEVELS = frozenset({'K', *(str(level) for level in range(1, 13))})


class ContractModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CurriculumImportResource(ContractModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    resource_type: Literal['file', 'link', 'note'] = 'link'
    url: str | None = Field(default=None, max_length=1000)


class CurriculumImportLesson(ContractModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    objectives: list[str] = Field(default_factory=list)
    standards_alignment: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    estimated_hours: float | None = Field(default=None, gt=0, le=24)
    resources: list[CurriculumImportResource] = Field(default_factory=list)


class CurriculumImportUnit(ContractModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    lessons: list[CurriculumImportLesson] = Field(min_length=1)


class CurriculumImportSubject(ContractModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    units: list[CurriculumImportUnit] = Field(min_length=1)


class CurriculumImportPayload(ContractModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    grade_levels: list[str] = Field(min_length=1)
    standards_alignment: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    estimated_hours: float | None = Field(default=None, gt=0, le=5000)
    subjects: list[CurriculumImportSubject] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_grade_levels_subject_names_and_size(self) -> 'CurriculumImportPayload':
        invalid_grade_levels = [grade_level for grade_level in self.grade_levels if grade_level not in VALID_GRADE_LEVELS]
        if invalid_grade_levels:
            raise ValueError(f'Unsupported grade levels: {", ".join(invalid_grade_levels)}')

        seen_subject_names: set[str] = set()
        for subject in self.subjects:
            normalized_name = subject.name.strip().casefold()
            if normalized_name in seen_subject_names:
                raise ValueError('Subject names must be unique within a curriculum import')
            seen_subject_names.add(normalized_name)

        lesson_count = sum(len(unit.lessons) for subject in self.subjects for unit in subject.units)
        if lesson_count > MAX_CURRICULUM_LESSONS:
            raise ValueError(f'Curriculum imports may contain at most {MAX_CURRICULUM_LESSONS} lessons')
        return self


def curriculum_import_payload(*, name: str = 'Biology Foundations') -> dict[str, Any]:
    return {
        'name': name,
        'description': 'Full-year biology with labs, notebooking, and family field studies.',
        'grade_levels': ['8'],
        'standards_alignment': ['NGSS-MS-LS1-1', 'OKLA.SCI.8.1'],
        'prerequisites': ['General science notebooking'],
        'estimated_hours': 132,
        'subjects': [
            {
                'name': 'Science',
                'description': 'Core life-science strand.',
                'units': [
                    {
                        'name': 'Cells & Systems',
                        'description': 'Structure and function of living systems.',
                        'lessons': [
                            {
                                'name': 'Cell theory',
                                'description': 'Microscope lab and observation journal.',
                                'objectives': ['Describe core parts of a cell', 'Compare plant and animal cells'],
                                'standards_alignment': ['NGSS-MS-LS1-1'],
                                'prerequisites': ['Lab safety basics'],
                                'estimated_hours': 1.5,
                                'resources': [
                                    {
                                        'name': 'Cell sketch notebook page',
                                        'resource_type': 'note',
                                        'description': 'Guided notebook template',
                                    },
                                    {
                                        'name': 'Microscope warm-up',
                                        'resource_type': 'link',
                                        'url': 'https://example.com/microscope-warmup',
                                    },
                                ],
                            },
                            {
                                'name': 'Organelles in action',
                                'objectives': ['Explain organelle roles in cell survival'],
                                'estimated_hours': 1.25,
                            },
                        ],
                    }
                ],
            }
        ],
    }


def _resolve_route(app: Any, method: str, *candidates: str) -> str:
    target_method = method.upper()
    available = {
        (allowed_method, route.path)
        for route in getattr(app, 'routes', [])
        for allowed_method in (getattr(route, 'methods', None) or set())
    }
    for candidate in candidates:
        if (target_method, candidate) in available:
            return candidate
    pytest.skip(f"Route not implemented yet: {target_method} {' or '.join(candidates)}")


def _curriculum_id(payload: dict[str, Any]) -> int:
    for key in ('id', 'curriculum_id'):
        if key in payload:
            return int(payload[key])
    pytest.fail(f'Curriculum response payload does not expose an id field: {payload}')


async def _login(client, *, email: str, password: str, family_id: int) -> None:
    login = await client.post(AUTH['login'], json={'email': email, 'password': password, 'family_id': family_id})
    assert login.status_code == 200, login.text
    sync_csrf_header(client)


async def _import_curriculum(client, app, payload: dict[str, Any]) -> dict[str, Any]:
    route = _resolve_route(app, 'POST', CURRICULUM_IMPORT['import'])
    response = await client.post(route, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_curriculum_import_contract_accepts_valid_complete_payload() -> None:
    payload = curriculum_import_payload()
    validated = CurriculumImportPayload.model_validate(payload)

    assert validated.name == 'Biology Foundations'
    assert validated.subjects[0].units[0].lessons[0].resources[0].name == 'Cell sketch notebook page'


@pytest.mark.parametrize(
    ('mutator', 'expected_field'),
    [
        (lambda payload: payload.pop('name'), 'name'),
        (lambda payload: payload.pop('subjects'), 'subjects'),
    ],
)
def test_curriculum_import_contract_rejects_missing_required_fields(mutator, expected_field: str) -> None:
    payload = curriculum_import_payload()
    mutator(payload)

    with pytest.raises(ValidationError) as exc_info:
        CurriculumImportPayload.model_validate(payload)

    assert expected_field in str(exc_info.value)


def test_curriculum_import_contract_rejects_invalid_grade_levels() -> None:
    payload = curriculum_import_payload()
    payload['grade_levels'] = ['13']

    with pytest.raises(ValidationError) as exc_info:
        CurriculumImportPayload.model_validate(payload)

    assert 'Unsupported grade levels' in str(exc_info.value)


def test_curriculum_import_contract_rejects_nested_lessons_outside_units() -> None:
    payload = curriculum_import_payload()
    payload['subjects'][0].pop('units')
    payload['subjects'][0]['lessons'] = [{'name': 'Misplaced lesson', 'estimated_hours': 1}]

    with pytest.raises(ValidationError) as exc_info:
        CurriculumImportPayload.model_validate(payload)

    rendered = str(exc_info.value)
    assert 'units' in rendered
    assert 'lessons' in rendered


@pytest.mark.skip(reason='awaiting implementation decision on empty-curriculum behavior')
def test_curriculum_import_contract_rejects_empty_curriculum() -> None:
    payload = curriculum_import_payload()
    payload['subjects'] = []

    with pytest.raises(ValidationError):
        CurriculumImportPayload.model_validate(payload)


def test_curriculum_import_contract_rejects_large_payloads() -> None:
    payload = curriculum_import_payload()
    lessons = [
        {
            'name': f'Lesson {index}',
            'objectives': [f'Objective {index}'],
            'estimated_hours': 1,
        }
        for index in range(1, MAX_CURRICULUM_LESSONS + 2)
    ]
    payload['subjects'][0]['units'][0]['lessons'] = lessons

    with pytest.raises(ValidationError) as exc_info:
        CurriculumImportPayload.model_validate(payload)

    assert str(MAX_CURRICULUM_LESSONS) in str(exc_info.value)


def test_curriculum_import_contract_accepts_special_characters_and_long_descriptions() -> None:
    payload = curriculum_import_payload(name='Español & Biology — “Cells/Systems” ✨')
    payload['description'] = 'Lab notebook reflection. ' * 120
    payload['subjects'][0]['units'][0]['lessons'][0]['description'] = 'Microscope notes & drawing prompts. ' * 80

    validated = CurriculumImportPayload.model_validate(payload)

    assert validated.name == 'Español & Biology — “Cells/Systems” ✨'
    assert validated.description is not None
    assert len(validated.description) > 2000


def test_curriculum_import_contract_rejects_duplicate_subject_names() -> None:
    payload = curriculum_import_payload()
    duplicate_subject = deepcopy(payload['subjects'][0])
    duplicate_subject['name'] = 'science'
    payload['subjects'].append(duplicate_subject)

    with pytest.raises(ValidationError) as exc_info:
        CurriculumImportPayload.model_validate(payload)

    assert 'Subject names must be unique' in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_schema_endpoint_exposes_expected_contract(authorized_client, app):
    route = _resolve_route(app, 'GET', CURRICULUM_IMPORT['schema'])
    response = await authorized_client.get(route)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload['type'] == 'object'
    assert {'name', 'grade_levels', 'subjects'}.issubset(set(payload['properties']))
    assert {'name', 'grade_levels', 'subjects'}.issubset(set(payload['required']))


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_import_creates_curriculum_linked_to_current_user(authorized_client, app):
    created = await _import_curriculum(authorized_client, app, curriculum_import_payload())
    collection_route = _resolve_route(app, 'GET', CURRICULUM_IMPORT['collection'], '/api/curriculum')
    list_response = await authorized_client.get(collection_route)
    assert list_response.status_code == 200, list_response.text

    me = await authorized_client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    user_id = me.json()['user']['id']
    items = list_response.json()
    imported = next(item for item in items if _curriculum_id(item) == _curriculum_id(created))
    assert imported['created_by_user_id'] == user_id


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_list_returns_only_current_users_curricula(
    authorized_client,
    secondary_client,
    create_family_user,
    app,
):
    family_id = (await authorized_client.get(AUTH['me'])).json()['family']['id']
    secondary_user = await create_family_user(
        family_name='Other Family',
        email='curriculum-other@example.com',
        password='strongpass991',
        display_name='Other Teacher',
        role='tutor',
    )
    await _login(
        secondary_client,
        email=secondary_user['email'],
        password=secondary_user['password'],
        family_id=secondary_user['family_id'],
    )

    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='curriculum-teacher@example.com',
        password='strongpass990',
        display_name='Curriculum Teacher',
        role='tutor',
    )

    await _import_curriculum(authorized_client, app, curriculum_import_payload(name='Family A Biology'))
    await _import_curriculum(secondary_client, app, curriculum_import_payload(name='Family B Biology'))

    collection_route = _resolve_route(app, 'GET', CURRICULUM_IMPORT['collection'], '/api/curriculum')
    own_list = await authorized_client.get(collection_route)
    other_list = await secondary_client.get(collection_route)
    assert own_list.status_code == 200, own_list.text
    assert other_list.status_code == 200, other_list.text
    assert {item['name'] for item in own_list.json()} == {'Family A Biology'}
    assert {item['name'] for item in other_list.json()} == {'Family B Biology'}


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_detail_returns_full_nested_structure(authorized_client, app):
    created = await _import_curriculum(authorized_client, app, curriculum_import_payload())
    detail_route = CURRICULUM_IMPORT['detail'].format(curriculum_id=_curriculum_id(created))
    _resolve_route(app, 'GET', CURRICULUM_IMPORT['detail'])

    detail = await authorized_client.get(detail_route)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload['subjects'][0]['units'][0]['lessons'][0]['name'] == 'Cell theory'
    assert payload['subjects'][0]['units'][0]['lessons'][0]['resources'][0]['resource_type'] == 'note'


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_delete_removes_curriculum_and_associated_data(authorized_client, app):
    created = await _import_curriculum(authorized_client, app, curriculum_import_payload())
    curriculum_id = _curriculum_id(created)
    detail_route_template = CURRICULUM_IMPORT['detail']
    _resolve_route(app, 'DELETE', detail_route_template)
    _resolve_route(app, 'GET', detail_route_template)
    collection_route = _resolve_route(app, 'GET', CURRICULUM_IMPORT['collection'], '/api/curriculum')

    delete_response = await authorized_client.delete(detail_route_template.format(curriculum_id=curriculum_id))
    assert delete_response.status_code == 204, delete_response.text

    detail_response = await authorized_client.get(detail_route_template.format(curriculum_id=curriculum_id))
    assert detail_response.status_code == 404, detail_response.text
    list_response = await authorized_client.get(collection_route)
    assert list_response.status_code == 200, list_response.text
    assert list_response.json() == []


@pytest.mark.asyncio
@pytest.mark.xfail(reason='Issue #165 contract calls for 403; existing family-scoped curriculum resources usually fail closed with 404.')
async def test_curriculum_detail_blocks_cross_family_access_with_forbidden(
    authorized_client,
    secondary_client,
    create_family_user,
    app,
):
    created = await _import_curriculum(authorized_client, app, curriculum_import_payload())
    other_user = await create_family_user(
        family_name='Other Family',
        email='curriculum-viewer@example.com',
        password='strongpass989',
        display_name='Other Viewer',
        role='tutor',
    )
    await _login(
        secondary_client,
        email=other_user['email'],
        password=other_user['password'],
        family_id=other_user['family_id'],
    )
    _resolve_route(app, 'GET', CURRICULUM_IMPORT['detail'])

    response = await secondary_client.get(CURRICULUM_IMPORT['detail'].format(curriculum_id=_curriculum_id(created)))
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_activation_creates_assignments_from_lessons(authorized_client, app):
    _resolve_route(app, 'POST', CURRICULUM_IMPORT['activate'])
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text

    created = await _import_curriculum(authorized_client, app, curriculum_import_payload())
    activate = await authorized_client.post(CURRICULUM_IMPORT['activate'].format(curriculum_id=_curriculum_id(created)))
    assert activate.status_code == 200, activate.text

    assignments = await authorized_client.get(ASSIGNMENTS['collection'])
    assert assignments.status_code == 200, assignments.text
    titles = {item['title'] for item in assignments.json().get('items', assignments.json())}
    assert {'Cell theory', 'Organelles in action'}.issubset(titles)


@pytest.mark.asyncio
@pytest.mark.skip(reason='awaiting implementation')
async def test_curriculum_activation_respects_school_year_calendar(authorized_client, app):
    _resolve_route(app, 'POST', CURRICULUM_IMPORT['activate'])
    school_year = await authorized_client.post(
        CALENDAR['school_years'],
        json=school_year_payload(name='2026-2027', start_date='2026-08-17', end_date='2027-05-28', is_active=True),
    )
    assert school_year.status_code == 201, school_year.text

    created = await _import_curriculum(authorized_client, app, curriculum_import_payload())
    activate = await authorized_client.post(CURRICULUM_IMPORT['activate'].format(curriculum_id=_curriculum_id(created)))
    assert activate.status_code == 200, activate.text

    assignments = await authorized_client.get(ASSIGNMENTS['collection'])
    assert assignments.status_code == 200, assignments.text
    items = assignments.json().get('items', assignments.json())
    assert items
    assert all('2026-08-17' <= item['due_date'] <= '2027-05-28' for item in items)


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_activation_is_idempotent_when_called_twice(authorized_client, app):
    _resolve_route(app, 'POST', CURRICULUM_IMPORT['activate'])
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text

    created = await _import_curriculum(authorized_client, app, curriculum_import_payload())
    first_activation = await authorized_client.post(CURRICULUM_IMPORT['activate'].format(curriculum_id=_curriculum_id(created)))
    second_activation = await authorized_client.post(CURRICULUM_IMPORT['activate'].format(curriculum_id=_curriculum_id(created)))
    assert first_activation.status_code == 200, first_activation.text
    assert second_activation.status_code in {200, 409}, second_activation.text

    assignments = await authorized_client.get(ASSIGNMENTS['collection'])
    assert assignments.status_code == 200, assignments.text
    items = assignments.json().get('items', assignments.json())
    assert len(items) == 2


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_activation_requires_school_year_configuration(authorized_client, app):
    _resolve_route(app, 'POST', CURRICULUM_IMPORT['activate'])
    created = await _import_curriculum(authorized_client, app, curriculum_import_payload())

    response = await authorized_client.post(CURRICULUM_IMPORT['activate'].format(curriculum_id=_curriculum_id(created)))
    assert response.status_code in {400, 409}, response.text
    assert 'school year' in response.json()['detail'].lower()


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_teacher_role_can_import_activate_and_delete_curriculum(
    authorized_client,
    secondary_client,
    create_family_user,
    app,
):
    family_id = (await authorized_client.get(AUTH['me'])).json()['family']['id']
    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='curriculum-rbac-teacher@example.com',
        password='strongpass988',
        display_name='Curriculum RBAC Teacher',
        role='tutor',
    )
    await _login(
        secondary_client,
        email='curriculum-rbac-teacher@example.com',
        password='strongpass988',
        family_id=family_id,
    )
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text

    created = await _import_curriculum(secondary_client, app, curriculum_import_payload(name='Teacher Import'))
    activate = await secondary_client.post(CURRICULUM_IMPORT['activate'].format(curriculum_id=_curriculum_id(created)))
    assert activate.status_code == 200, activate.text

    delete_response = await secondary_client.delete(CURRICULUM_IMPORT['detail'].format(curriculum_id=_curriculum_id(created)))
    assert delete_response.status_code == 204, delete_response.text


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_viewer_role_cannot_import_curriculum(
    authorized_client,
    secondary_client,
    create_family_user,
    app,
):
    family_id = (await authorized_client.get(AUTH['me'])).json()['family']['id']
    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='curriculum-viewer-blocked@example.com',
        password='strongpass987',
        display_name='Viewer Blocked',
        role='student_viewer',
    )
    await _login(
        secondary_client,
        email='curriculum-viewer-blocked@example.com',
        password='strongpass987',
        family_id=family_id,
    )
    route = _resolve_route(app, 'POST', CURRICULUM_IMPORT['import'])

    response = await secondary_client.post(route, json=curriculum_import_payload())
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_student_role_cannot_import_curriculum(
    authorized_client,
    secondary_client,
    create_family_user,
    app,
):
    family_id = (await authorized_client.get(AUTH['me'])).json()['family']['id']
    student = await authorized_client.post(STUDENTS['collection'], json=student_payload('Learner Linked'))
    assert student.status_code == 201, student.text
    student_id = student.json()['id']
    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='curriculum-student-blocked@example.com',
        password='strongpass986',
        display_name='Student Blocked',
        role='student_viewer',
        student_id=student_id,
    )
    await _login(
        secondary_client,
        email='curriculum-student-blocked@example.com',
        password='strongpass986',
        family_id=family_id,
    )
    route = _resolve_route(app, 'POST', CURRICULUM_IMPORT['import'])

    response = await secondary_client.post(route, json=curriculum_import_payload())
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
@pytest.mark.skip(reason='awaiting implementation')
async def test_curriculum_import_supports_concurrent_requests(authorized_client, app):
    route = _resolve_route(app, 'POST', CURRICULUM_IMPORT['import'])
    payload_a = curriculum_import_payload(name='Concurrent Biology A')
    payload_b = curriculum_import_payload(name='Concurrent Biology B')

    responses = await asyncio.gather(
        authorized_client.post(route, json=payload_a),
        authorized_client.post(route, json=payload_b),
    )
    assert {response.status_code for response in responses} == {201}

    collection_route = _resolve_route(app, 'GET', CURRICULUM_IMPORT['collection'], '/api/curriculum')
    listing = await authorized_client.get(collection_route)
    assert listing.status_code == 200, listing.text
    assert {item['name'] for item in listing.json()} == {'Concurrent Biology A', 'Concurrent Biology B'}


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PENDING_IMPORT_REASON)
async def test_curriculum_import_rejects_invalid_grade_levels_at_api(authorized_client, app):
    route = _resolve_route(app, 'POST', CURRICULUM_IMPORT['import'])
    payload = curriculum_import_payload()
    payload['grade_levels'] = ['13']

    response = await authorized_client.post(route, json=payload)
    assert_validation_error(response)
    assert 'grade' in response.text.lower()
