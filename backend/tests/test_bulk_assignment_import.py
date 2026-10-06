from __future__ import annotations

import json

import pytest

from backend.schemas.bulk_assignment_import import ParsedAssignmentCandidate, ParsedAssignmentDocument
from backend.services.bulk_assignment_import import BulkAssignmentImportService
from backend.services.curriculum_ai_import import AIImportError, ExtractedSource
from tests.contracts import ASSIGNMENTS, AUTH, SUBJECTS, password_for_test, subject_payload
from tests.helpers import response_id, sync_csrf_header

ASSIGNMENT_IMPORTS = '/api/assignment-import-sessions'


def _contains_json_schema_ref(value):
    if isinstance(value, dict):
        if '$ref' in value or '$defs' in value:
            return True
        return any(_contains_json_schema_ref(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_json_schema_ref(item) for item in value)
    return False


def _extracted_source() -> ExtractedSource:
    return ExtractedSource(
        source_kind='file',
        source_name='assignments.txt',
        content_type='text/plain',
        text='Math worksheet',
        warnings=[],
    )


def _configure_local_ai(monkeypatch):
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_local_only', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_provider', 'ollama', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', None, raising=False)
    monkeypatch.setattr('backend.config.settings.ollama_host', 'http://127.0.0.1:11434', raising=False)
    monkeypatch.setattr('backend.config.settings.ollama_model', 'llama3.1:8b', raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize('encoded_assignments', [False, True], ids=['native-array', 'json-string-array'])
async def test_bulk_assignment_import_accepts_native_and_json_string_assignments(monkeypatch, encoded_assignments):
    _configure_local_ai(monkeypatch)
    assignments = [{'client_item_id': 'item_0001', 'title': 'Math worksheet'}]
    payload_assignments = json.dumps(assignments) if encoded_assignments else assignments

    async def fake_call(extracted):  # noqa: ARG001
        return {'schema_version': '1.0', 'assignments': payload_assignments}

    service = BulkAssignmentImportService()
    monkeypatch.setattr(service, '_call_ai_parser', fake_call)

    parsed = await service.parse_with_ai(_extracted_source())

    assert parsed.assignments[0].title == 'Math worksheet'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('assignments', 'message'),
    [
        ('[{', 'not valid JSON'),
        ('{"title": "Object"}', 'decode to a list'),
        ('1', 'decode to a list'),
    ],
    ids=['malformed-string', 'decoded-object', 'decoded-number'],
)
async def test_bulk_assignment_import_rejects_bad_json_string_assignments(monkeypatch, assignments, message):
    _configure_local_ai(monkeypatch)

    async def fake_call(extracted):  # noqa: ARG001
        return {'schema_version': '1.0', 'assignments': assignments}

    service = BulkAssignmentImportService()
    monkeypatch.setattr(service, '_call_ai_parser', fake_call)

    with pytest.raises(AIImportError, match=message):
        await service.parse_with_ai(_extracted_source())


@pytest.mark.asyncio
async def test_bulk_assignment_import_revalidates_entries_decoded_from_json_string(monkeypatch):
    _configure_local_ai(monkeypatch)

    async def fake_call(extracted):  # noqa: ARG001
        return {'schema_version': '1.0', 'assignments': json.dumps([{'title': 'x' * 300}])}

    service = BulkAssignmentImportService()
    monkeypatch.setattr(service, '_call_ai_parser', fake_call)

    with pytest.raises(AIImportError, match='invalid assignment draft'):
        await service.parse_with_ai(_extracted_source())


def test_bulk_assignment_import_tool_schema_inlines_refs():
    payload = BulkAssignmentImportService()._build_request_payload(_extracted_source(), model='llama3.1:8b')
    schema = payload['tools'][0]['function']['parameters']

    assert not _contains_json_schema_ref(schema)


@pytest.mark.asyncio
async def test_bulk_assignment_import_ai_disabled_returns_503(authorized_client, monkeypatch):
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', False, raising=False)

    response = await authorized_client.post(
        ASSIGNMENT_IMPORTS,
        files={'file': ('plan.txt', b'Math worksheet', 'text/plain')},
    )

    assert response.status_code == 503, response.text
    assert response.json()['code'] == 'ai_import_unavailable'


@pytest.mark.asyncio
async def test_bulk_assignment_import_clarify_and_confirm(authorized_client, seeded_subject, seeded_student, monkeypatch):
    async def fake_parse(self, extracted):  # noqa: ARG001
        return ParsedAssignmentDocument(
            assignments=[
                ParsedAssignmentCandidate(
                    client_item_id='item_0001',
                    title='Fractions worksheet',
                    subject_ref='Math',
                    student_refs=['Ada Lovelace'],
                    due_date='2026-10-13',
                    category='homework',
                    max_score=50,
                    weight=2,
                    source_excerpt='Fractions worksheet due Oct 13',
                    confidence=0.9,
                ),
                ParsedAssignmentCandidate(
                    client_item_id='item_0002',
                    title='Reading log',
                    student_refs=[],
                    source_excerpt='Reading log',
                    confidence=0.8,
                ),
            ]
        )

    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.services.bulk_assignment_import.BulkAssignmentImportService.parse_with_ai', fake_parse)

    create = await authorized_client.post(
        ASSIGNMENT_IMPORTS,
        files={'file': ('week.md', b'- Math: Fractions worksheet\n- Reading log', 'text/markdown')},
    )
    assert create.status_code == 201, create.text
    created = create.json()
    assert created['items'] == []
    assert created['summary'] == {'total': 2, 'ready': 1, 'needs_clarification': 1, 'invalid': 0}
    assert created['questions'][0]['field'] == 'subject_id'

    detail = await authorized_client.get(f'{ASSIGNMENT_IMPORTS}/{created["id"]}')
    assert detail.status_code == 200, detail.text
    draft = detail.json()
    second = next(item for item in draft['items'] if item['client_item_id'] == 'item_0002')
    second['subject_id'] = response_id(seeded_subject)
    second['targets'] = [{'student_id': response_id(seeded_student), 'status': 'assigned'}]

    patch = await authorized_client.patch(
        f'{ASSIGNMENT_IMPORTS}/{created["id"]}',
        json={'items': [second]},
    )
    assert patch.status_code == 200, patch.text
    patched = patch.json()
    assert patched['status'] == 'ready'
    assert patched['summary']['ready'] == 2

    confirm = await authorized_client.post(
        f'{ASSIGNMENT_IMPORTS}/{created["id"]}/confirm',
        json={'client_revision': patched['revision'], 'item_ids': ['item_0001', 'item_0002']},
    )
    assert confirm.status_code == 201, confirm.text
    assert confirm.json()['assignment_count'] == 2

    assignments = await authorized_client.get(ASSIGNMENTS['collection'], params={'page_size': 10})
    assert assignments.status_code == 200, assignments.text
    titles = {item['title'] for item in assignments.json()['items']}
    assert titles == {'Fractions worksheet', 'Reading log'}


@pytest.mark.asyncio
async def test_bulk_assignment_import_rejects_cross_family_subject(authorized_client, create_family_user, monkeypatch):
    current = await authorized_client.get(AUTH['me'])
    family_id = current.json()['family']['id']
    other = await create_family_user(
        family_name='Other Family',
        email='other@example.com',
        password='strongpass123',
        display_name='Other Parent',
        role='parent',
    )
    other_subject_response = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('Science'))
    assert other_subject_response.status_code == 201, other_subject_response.text
    same_family_subject = response_id(other_subject_response.json())

    async def fake_parse(self, extracted):  # noqa: ARG001
        return ParsedAssignmentDocument(
            assignments=[ParsedAssignmentCandidate(client_item_id='item_0001', title='Unsafe row', subject_ref=None)]
        )

    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.services.bulk_assignment_import.BulkAssignmentImportService.parse_with_ai', fake_parse)
    create = await authorized_client.post(
        ASSIGNMENT_IMPORTS,
        files={'file': ('plan.txt', b'Unsafe row', 'text/plain')},
    )
    assert create.status_code == 201, create.text

    other_login = await authorized_client.post(
        AUTH['login'],
        json={'email': other['email'], 'password': other['password'], 'family_id': other['family_id']},
    )
    assert other_login.status_code == 200, other_login.text
    sync_csrf_header(authorized_client)
    other_subject = await authorized_client.post(SUBJECTS['collection'], json=subject_payload('History'))
    assert other_subject.status_code == 201, other_subject.text
    other_subject_id = response_id(other_subject.json())

    relogin = await authorized_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': password_for_test('bootstrap-owner'), 'family_id': family_id},
    )
    assert relogin.status_code == 200, relogin.text
    sync_csrf_header(authorized_client)

    patch = await authorized_client.patch(
        f'{ASSIGNMENT_IMPORTS}/{create.json()["id"]}',
        json={
            'items': [
                {
                    'client_item_id': 'item_0001',
                    'title': 'Unsafe row',
                    'subject_id': other_subject_id,
                    'category': 'homework',
                    'max_score': 100,
                    'weight': 1,
                    'recurrence': 'none',
                    'targets': [],
                }
            ]
        },
    )
    assert patch.status_code == 404, patch.text

    safe_patch = await authorized_client.patch(
        f'{ASSIGNMENT_IMPORTS}/{create.json()["id"]}',
        json={
            'items': [
                {
                    'client_item_id': 'item_0001',
                    'title': 'Safe row',
                    'subject_id': same_family_subject,
                    'category': 'homework',
                    'max_score': 100,
                    'weight': 1,
                    'recurrence': 'none',
                    'targets': [],
                }
            ]
        },
    )
    assert safe_patch.status_code == 200, safe_patch.text


@pytest.mark.asyncio
async def test_bulk_assignment_import_denies_student_viewer(async_client, create_family_user):
    viewer = await create_family_user(
        family_name='Viewer Family',
        email='viewer@example.com',
        password='strongpass456',
        role='student_viewer',
        student_name='Viewer Student',
    )
    login = await async_client.post(
        AUTH['login'],
        json={'email': viewer['email'], 'password': viewer['password'], 'family_id': viewer['family_id']},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(async_client)

    response = await async_client.post(
        ASSIGNMENT_IMPORTS,
        files={'file': ('plan.txt', b'Math worksheet', 'text/plain')},
    )

    assert response.status_code == 403, response.text
