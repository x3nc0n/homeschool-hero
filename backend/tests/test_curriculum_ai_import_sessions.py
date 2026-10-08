from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import update

from backend.database import AsyncSessionLocal
from backend.models import CurriculumAIImportSession
from backend.services import curriculum_ai_import_sessions as sessions_service
from backend.services.curriculum_ai_import import AIImportError, AICurriculumImportService
from tests.contracts import CURRICULUM
from tests.helpers import response_id, sync_csrf_header

SECRET_MARKER = 'SECRET-MODEL-OUTPUT-7731'

DRAFT = {
    'name': 'Model Draft Title',
    'description': 'Drafted by the local model.',
    'source': 'manual',
    'schema_version': '9.9',
    'metadata': {'grade_levels': ['3']},
    'subjects': [
        {
            'name': 'Science',
            'units': [
                {
                    'name': 'Plants',
                    'lessons': [
                        {'name': 'Parts of a Plant', 'objectives': ['Label roots, stem, and leaves']},
                        {'name': 'Photosynthesis Basics', 'objectives': ['Explain how plants make food']},
                        {'name': 'Seed Dispersal'},
                    ],
                }
            ],
        }
    ],
}


class _ScriptedOllama:
    """Fake httpx.AsyncClient that answers native Ollama /api/chat requests from a script."""

    script: list = []
    requests: list[dict] = []
    gate: asyncio.Event | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, params=None, json=None):  # noqa: A002
        type(self).requests.append({'url': url, 'json': json})
        if type(self).gate is not None:
            await type(self).gate.wait()
        step = type(self).script.pop(0) if type(self).script else DRAFT
        request = httpx.Request('POST', url)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, httpx.Response):
            return httpx.Response(step.status_code, content=step.content, request=request)
        content = step if isinstance(step, str) else json_module.dumps(step)
        return httpx.Response(200, json={'message': {'role': 'assistant', 'content': content}, 'done': True}, request=request)


json_module = json


@pytest.fixture
def local_ai(monkeypatch):
    _ScriptedOllama.script = []
    _ScriptedOllama.requests = []
    _ScriptedOllama.gate = None
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_local_only', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_provider', 'ollama', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', None, raising=False)
    monkeypatch.setattr('backend.config.settings.ollama_host', 'http://127.0.0.1:11434', raising=False)
    monkeypatch.setattr('backend.config.settings.ollama_model', 'qwen2.5:14b', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_retry_attempts', 3, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_retry_backoff_seconds', 0.0, raising=False)
    monkeypatch.setattr('backend.services.curriculum_ai_import.httpx.AsyncClient', _ScriptedOllama)
    return _ScriptedOllama


@pytest.fixture
def captured_jobs(monkeypatch):
    jobs: list[tuple] = []

    def _capture(session_id, family_id, revision, source):
        jobs.append((session_id, family_id, revision, source))

    monkeypatch.setattr('backend.routers.curriculum_ai_import_sessions.schedule_processing', _capture)
    return jobs


async def _start(client, *, name: str = 'scope.txt', body: bytes = b'Science scope: plants unit.'):
    return await client.post(CURRICULUM['ai_import_sessions'], files={'file': (name, body, 'text/plain')})


async def _get(client, session_id: int):
    return await client.get(CURRICULUM['ai_import_session_detail'].format(session_id=session_id))


async def _confirm(client, session_id: int, draft: dict, revision: int, acks: list[int] | None = None):
    return await client.post(
        CURRICULUM['ai_import_session_confirm'].format(session_id=session_id),
        json={'draft': draft, 'client_revision': revision, 'acknowledged_duplicate_ids': acks or []},
    )


async def _set_columns(session_id: int, **values):
    async with AsyncSessionLocal() as db:
        await db.execute(update(CurriculumAIImportSession).where(CurriculumAIImportSession.id == session_id).values(**values))
        await db.commit()


async def _ready_session(client, jobs) -> dict:
    created = await _start(client)
    assert created.status_code == 202, created.text
    await sessions_service.run_processing(*jobs[-1])
    ready = await _get(client, created.json()['id'])
    assert ready.status_code == 200, ready.text
    assert ready.json()['status'] == 'ready', ready.text
    return ready.json()


@pytest.mark.asyncio
async def test_session_create_returns_202_then_ready_and_confirms(authorized_client, local_ai, captured_jobs):
    created = await _start(authorized_client)

    assert created.status_code == 202, created.text
    payload = created.json()
    assert set(payload) == {
        'id', 'status', 'source_kind', 'source_name', 'warnings', 'revision',
        'expires_at', 'created_at', 'updated_at', 'draft', 'error',
    }
    assert payload['status'] == 'processing'
    assert payload['source_kind'] == 'file'
    assert payload['source_name'] == 'scope.txt'
    assert payload['revision'] == 1
    assert payload['draft'] is None and payload['error'] is None
    assert created.headers['location'].endswith(f"/api/curriculum/ai-import-sessions/{payload['id']}")
    assert created.headers['retry-after'] == '2'
    expires = datetime.fromisoformat(payload['expires_at'])
    assert timedelta(hours=23) < expires - datetime.now(UTC) <= timedelta(hours=24)
    assert local_ai.requests == []

    processing = await _get(authorized_client, payload['id'])
    assert processing.json()['status'] == 'processing'
    assert processing.headers['retry-after'] == '2'

    assert len(captured_jobs) == 1
    await sessions_service.run_processing(*captured_jobs[0])
    assert captured_jobs[0][3].payload is None
    ready = (await _get(authorized_client, payload['id'])).json()
    assert ready['status'] == 'ready'
    assert ready['revision'] == 2
    assert ready['error'] is None
    assert ready['draft']['name'] == 'Model Draft Title'
    assert ready['draft']['source'] == 'ai-import'
    assert ready['draft']['schema_version'] == '1.0'
    assert local_ai.requests[0]['url'] == 'http://127.0.0.1:11434/api/chat'

    draft = ready['draft']
    draft['name'] = 'Reviewed Plants'
    confirmed = await _confirm(authorized_client, payload['id'], draft, ready['revision'])
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()['name'] == 'Reviewed Plants'

    after = (await _get(authorized_client, payload['id'])).json()
    assert after['status'] == 'confirmed'
    assert after['draft'] is None

    again = await _confirm(authorized_client, payload['id'], draft, after['revision'])
    assert again.status_code == 409
    assert again.json()['error']['code'] == 'curriculum_ai_import_session_confirmed'
    delete = await authorized_client.delete(CURRICULUM['ai_import_session_detail'].format(session_id=payload['id']))
    assert delete.status_code == 409
    assert delete.json()['error']['code'] == 'curriculum_ai_import_session_confirmed'


@pytest.mark.asyncio
async def test_session_post_is_prompt_while_inference_blocks(authorized_client, local_ai):
    local_ai.gate = asyncio.Event()
    created = await asyncio.wait_for(_start(authorized_client), timeout=5)
    assert created.status_code == 202, created.text
    session_id = created.json()['id']

    for _ in range(50):
        if local_ai.requests:
            break
        await asyncio.sleep(0.01)
    assert len(local_ai.requests) == 1
    task = sessions_service._TASKS[session_id]
    assert not task.done()

    deleted = await authorized_client.delete(CURRICULUM['ai_import_session_detail'].format(session_id=session_id))
    assert deleted.status_code == 204
    await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert session_id not in sessions_service._TASKS
    local_ai.gate.set()

    body = (await _get(authorized_client, session_id)).json()
    assert body['status'] == 'expired'
    assert body['draft'] is None


@pytest.mark.asyncio
async def test_late_worker_cannot_overwrite_cancelled_session(authorized_client, local_ai, captured_jobs, caplog):
    created = await _start(authorized_client)
    session_id = created.json()['id']
    deleted = await authorized_client.delete(CURRICULUM['ai_import_session_detail'].format(session_id=session_id))
    assert deleted.status_code == 204

    with caplog.at_level(logging.WARNING):
        await sessions_service.run_processing(*captured_jobs[0])
    body = (await _get(authorized_client, session_id)).json()
    assert body['status'] == 'expired'
    assert body['draft'] is None
    assert 'AI curriculum import worker result discarded.' in caplog.text
    assert 'Parts of a Plant' not in caplog.text

    repeat = await authorized_client.delete(CURRICULUM['ai_import_session_detail'].format(session_id=session_id))
    assert repeat.status_code == 204


@pytest.mark.asyncio
async def test_stale_processing_session_fails_and_late_worker_is_discarded(authorized_client, local_ai, captured_jobs):
    created = await _start(authorized_client)
    session_id = created.json()['id']
    await _set_columns(session_id, updated_at=datetime.now(UTC) - timedelta(hours=6))

    stale = (await _get(authorized_client, session_id)).json()
    assert stale['status'] == 'failed'
    assert stale['error'] == {
        'code': 'processing_stale',
        'message': 'AI curriculum import processing did not finish. Please retry the import.',
    }
    assert stale['revision'] == 2

    await sessions_service.run_processing(*captured_jobs[0])
    assert (await _get(authorized_client, session_id)).json()['status'] == 'failed'

    not_ready = await _confirm(authorized_client, session_id, DRAFT, stale['revision'])
    assert not_ready.status_code == 409
    assert not_ready.json()['error']['code'] == 'curriculum_ai_import_session_not_ready'


@pytest.mark.asyncio
async def test_confirm_rejects_processing_stale_revision_and_expired(authorized_client, local_ai, captured_jobs):
    processing = await _start(authorized_client)
    early = await _confirm(authorized_client, processing.json()['id'], DRAFT, 1)
    assert early.status_code == 409
    assert early.json()['error']['code'] == 'curriculum_ai_import_session_not_ready'

    ready = await _ready_session(authorized_client, captured_jobs)
    stale = await _confirm(authorized_client, ready['id'], ready['draft'], ready['revision'] - 1)
    assert stale.status_code == 409
    assert stale.json()['error']['code'] == 'curriculum_ai_import_session_stale'

    await _set_columns(ready['id'], expires_at=datetime.now(UTC) - timedelta(minutes=1))
    expired = await _confirm(authorized_client, ready['id'], ready['draft'], ready['revision'])
    assert expired.status_code == 409
    assert expired.json()['error']['code'] == 'curriculum_ai_import_session_expired'
    body = (await _get(authorized_client, ready['id'])).json()
    assert body['status'] == 'expired' and body['draft'] is None
    listing = await authorized_client.get(CURRICULUM['imports'])
    assert listing.json() == []


@pytest.mark.asyncio
async def test_session_confirm_duplicate_preserves_ready_draft(authorized_client, local_ai, captured_jobs):
    existing = await authorized_client.post(
        CURRICULUM['import_confirm'],
        json={'draft': {**DRAFT, 'name': 'Plants From Another File'}},
    )
    assert existing.status_code == 201, existing.text
    existing_id = response_id(existing.json())

    ready = await _ready_session(authorized_client, captured_jobs)
    check = await authorized_client.post(CURRICULUM['import_duplicate_check'], json={'draft': ready['draft']})
    assert [item['id'] for item in check.json()['matches']] == [existing_id]

    rejected = await _confirm(authorized_client, ready['id'], ready['draft'], ready['revision'])
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()['error']['code'] == 'curriculum_import_duplicate_conflict'
    assert rejected.json()['error']['details']['matches'][0]['matched_lessons'] == [
        'Parts of a Plant', 'Photosynthesis Basics', 'Seed Dispersal'
    ]
    preserved = (await _get(authorized_client, ready['id'])).json()
    assert preserved['status'] == 'ready'
    assert preserved['revision'] == ready['revision']
    assert preserved['draft'] == ready['draft']

    accepted = await _confirm(authorized_client, ready['id'], ready['draft'], ready['revision'], [existing_id])
    assert accepted.status_code == 201, accepted.text


@pytest.mark.asyncio
async def test_sessions_are_family_scoped(authorized_client, secondary_client, create_family_user, local_ai, captured_jobs):
    ready = await _ready_session(authorized_client, captured_jobs)

    other = await create_family_user(family_name='Session Other', email='session-other@example.com', password='other-password')
    login = await secondary_client.post(
        '/api/auth/login',
        json={'email': other['email'], 'password': other['password'], 'family_id': other['family_id']},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    detail = CURRICULUM['ai_import_session_detail'].format(session_id=ready['id'])
    assert (await secondary_client.get(detail)).status_code == 404
    assert (await secondary_client.delete(detail)).status_code == 404
    assert (await _confirm(secondary_client, ready['id'], ready['draft'], ready['revision'])).status_code == 404
    assert (await _get(authorized_client, ready['id'])).json()['status'] == 'ready'


@pytest.mark.asyncio
async def test_worker_failure_is_safe_and_not_retried(authorized_client, local_ai, captured_jobs, caplog):
    local_ai.script = [f'not json {SECRET_MARKER}']
    created = await _start(authorized_client)
    with caplog.at_level(logging.DEBUG):
        await sessions_service.run_processing(*captured_jobs[0])

    body = (await _get(authorized_client, created.json()['id'])).json()
    assert body['status'] == 'failed'
    assert body['draft'] is None
    assert body['error']['code'] == 'ai_response_invalid'
    assert SECRET_MARKER not in json.dumps(body)
    assert SECRET_MARKER not in caplog.text
    assert len(local_ai.requests) == 1


@pytest.mark.asyncio
async def test_session_upload_limits_and_source_validation(authorized_client, local_ai, captured_jobs, monkeypatch):
    monkeypatch.setattr('backend.config.settings.upload_max_bytes', 16, raising=False)
    too_large = await _start(authorized_client, body=b'x' * 17)
    assert too_large.status_code == 413
    assert too_large.json()['error']['code'] == 'document_too_large'

    empty = await _start(authorized_client, body=b'')
    assert empty.status_code == 400

    unsupported = await authorized_client.post(
        CURRICULUM['ai_import_sessions'], files={'file': ('scope.exe', b'MZ', 'application/octet-stream')}
    )
    assert unsupported.status_code == 400
    assert unsupported.json()['error']['code'] == 'unsupported_document_type'
    assert captured_jobs == []


@pytest.mark.asyncio
async def test_session_url_disabled_offline_and_unavailable(authorized_client, local_ai, captured_jobs, monkeypatch):
    monkeypatch.setattr('backend.config.settings.online_curriculum_enabled', False, raising=False)
    offline = await authorized_client.post(CURRICULUM['ai_import_sessions'], json={'url': 'https://example.com/a.txt'})
    assert offline.status_code == 503

    monkeypatch.setattr('backend.config.settings.ai_import_enabled', False, raising=False)
    disabled = await _start(authorized_client)
    assert disabled.status_code == 503
    assert captured_jobs == []


@pytest.mark.asyncio
async def test_native_ollama_decodes_fenced_json(local_ai):
    local_ai.script = ['```json\n' + json.dumps(DRAFT) + '\n```']
    draft, _ = await AICurriculumImportService().build_draft_from_bytes(b'plants', filename='a.txt', content_type='text/plain')
    assert draft.name == 'Model Draft Title'
    assert draft.schema_version == '1.0'
    assert len(local_ai.requests) == 1


@pytest.mark.asyncio
async def test_native_ollama_decodes_schema_guided_stringified_lists(local_ai):
    stringified = json.loads(json.dumps(DRAFT))
    lessons = stringified['subjects'][0]['units'][0]['lessons']
    lessons[0]['objectives'] = json.dumps(lessons[0]['objectives'])
    stringified['subjects'][0]['units'][0]['lessons'] = json.dumps(lessons)
    stringified['subjects'] = json.dumps(stringified['subjects'])
    local_ai.script = [stringified]

    draft, _ = await AICurriculumImportService().build_draft_from_bytes(b'plants', filename='a.txt', content_type='text/plain')
    lesson = draft.subjects[0].units[0].lessons[0]
    assert lesson.name == 'Parts of a Plant'
    assert lesson.objectives == ['Label roots, stem, and leaves']


@pytest.mark.parametrize(
    'content',
    [
        pytest.param(f'here you go: {SECRET_MARKER}', id='prose'),
        pytest.param({**DRAFT, 'subjects': f'not a list {SECRET_MARKER}'}, id='strlist'),
        pytest.param({**DRAFT, 'subjects': [{'name': SECRET_MARKER, 'units': []}]}, id='empty-units'),
        pytest.param({**DRAFT, 'unexpected': SECRET_MARKER}, id='extra'),
        pytest.param({**DRAFT, 'subjects': json.dumps({'name': SECRET_MARKER})}, id='strobj'),
    ],
)
@pytest.mark.asyncio
async def test_invalid_model_output_fails_safely_without_parser_retry(local_ai, caplog, content):
    local_ai.script = [content, DRAFT, DRAFT]
    with caplog.at_level(logging.DEBUG), pytest.raises(AIImportError) as raised:
        await AICurriculumImportService().build_draft_from_bytes(b'plants', filename='a.txt', content_type='text/plain')
    assert raised.value.code == 'ai_response_invalid'
    assert SECRET_MARKER not in raised.value.message
    assert SECRET_MARKER not in str(raised.value)
    assert SECRET_MARKER not in caplog.text
    assert len(local_ai.requests) == 1


@pytest.mark.asyncio
async def test_transport_failures_are_retried_but_http_errors_are_not(local_ai):
    local_ai.script = [httpx.ReadTimeout('slow'), httpx.ConnectError('down'), DRAFT]
    draft, _ = await AICurriculumImportService().build_draft_from_bytes(b'plants', filename='a.txt', content_type='text/plain')
    assert draft.name == 'Model Draft Title'
    assert len(local_ai.requests) == 3

    local_ai.requests.clear()
    local_ai.script = [httpx.ReadTimeout('slow')] * 3
    with pytest.raises(AIImportError) as timed_out:
        await AICurriculumImportService().build_draft_from_bytes(b'plants', filename='a.txt', content_type='text/plain')
    assert timed_out.value.code == 'ai_provider_timeout'
    assert len(local_ai.requests) == 3

    local_ai.requests.clear()
    local_ai.script = [httpx.Response(400, content=SECRET_MARKER.encode()), DRAFT]
    with pytest.raises(AIImportError) as rejected:
        await AICurriculumImportService().build_draft_from_bytes(b'plants', filename='a.txt', content_type='text/plain')
    assert rejected.value.code == 'ai_provider_error'
    assert SECRET_MARKER not in rejected.value.message
    assert len(local_ai.requests) == 1


@pytest.mark.asyncio
async def test_sync_ai_import_returns_safe_error_code(authorized_client, local_ai):
    local_ai.script = [f'garbage {SECRET_MARKER}']
    response = await authorized_client.post(
        CURRICULUM['ai_import'], files={'file': ('scope.txt', b'plants', 'text/plain')}
    )
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'ai_response_invalid'
    assert SECRET_MARKER not in response.text
    assert len(local_ai.requests) == 1