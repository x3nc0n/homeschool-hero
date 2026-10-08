from __future__ import annotations

import asyncio
import copy
import json
from time import perf_counter

import pytest
from sqlalchemy import update

from backend.database import AsyncSessionLocal
from backend.models import CurriculumAIImportSession
from backend.schemas.curriculum import CurriculumImportDocument
from backend.services import curriculum_ai_import_sessions as sessions_service
from backend.services.curriculum_ai_import import AICurriculumImportService, ExtractedSource
from tests.contracts import CURRICULUM
from backend.tests.test_curriculum_ai_import_sessions import (
    DRAFT,
    _confirm,
    _get,
    _ready_session,
    _start,
    captured_jobs,
    local_ai,
)


@pytest.mark.asyncio
async def test_url_session_returns_202_before_slow_source_fetch_finishes(authorized_client, local_ai, monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()
    monkeypatch.setattr('backend.config.settings.online_curriculum_enabled', True)

    async def slow_extract(self, url):
        started.set()
        await release.wait()
        return ExtractedSource('url', 'plants.txt', 'text/plain', 'Science: plants', source_url=url)

    monkeypatch.setattr(AICurriculumImportService, '_extract_from_url', slow_extract)
    worker = None
    try:
        before = perf_counter()
        created = await asyncio.wait_for(
            authorized_client.post(CURRICULUM['ai_import_sessions'], json={'url': 'https://example.com/plants.txt'}),
            timeout=2,
        )
        elapsed = perf_counter() - before
        assert created.status_code == 202, created.text
        assert elapsed < 2
        await asyncio.wait_for(started.wait(), timeout=2)
        session_id = created.json()['id']
        worker = sessions_service._TASKS[session_id]
        assert not worker.done()
        assert local_ai.requests == []
        assert (await _get(authorized_client, session_id)).json()['status'] == 'processing'
        release.set()
        await asyncio.wait_for(worker, timeout=5)
        ready = (await _get(authorized_client, session_id)).json()
        assert ready['status'] == 'ready'
        assert ready['source_kind'] == 'url'
        assert ready['draft']['name'] == DRAFT['name']
    finally:
        release.set()
        if worker is not None and not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.parametrize('invalid_output', [False, True], ids=['ready-result', 'failed-result'])
@pytest.mark.asyncio
async def test_revision_only_change_discards_inflight_worker_result(
    authorized_client, local_ai, captured_jobs, invalid_output,
):
    local_ai.gate = asyncio.Event()
    if invalid_output:
        local_ai.script = ['invalid model response']
    created = await _start(authorized_client)
    session_id = created.json()['id']
    worker = asyncio.create_task(sessions_service.run_processing(*captured_jobs[0]))
    try:
        for _ in range(200):
            if local_ai.requests:
                break
            await asyncio.sleep(0.01)
        assert local_ai.requests, 'Worker did not reach the provider'
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(CurriculumAIImportSession)
                .where(CurriculumAIImportSession.id == session_id)
                .values(revision=2, warnings=['Newer revision'])
            )
            await db.commit()
        local_ai.gate.set()
        await asyncio.wait_for(worker, timeout=5)
        current = (await _get(authorized_client, session_id)).json()
        assert current['status'] == 'processing'
        assert current['revision'] == 2
        assert current['warnings'] == ['Newer revision']
        assert current['draft'] is None
        assert current['error'] is None
    finally:
        local_ai.gate.set()
        if not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancel_after_inference_started_discards_late_result(authorized_client, local_ai, captured_jobs):
    local_ai.gate = asyncio.Event()
    created = await _start(authorized_client)
    session_id = created.json()['id']
    worker = asyncio.create_task(sessions_service.run_processing(*captured_jobs[0]))
    try:
        for _ in range(200):
            if local_ai.requests:
                break
            await asyncio.sleep(0.01)
        assert local_ai.requests, 'Worker did not reach the provider'
        detail = CURRICULUM['ai_import_session_detail'].format(session_id=session_id)
        assert (await authorized_client.delete(detail)).status_code == 204
        local_ai.gate.set()
        await asyncio.wait_for(worker, timeout=5)
        cancelled = (await _get(authorized_client, session_id)).json()
        assert cancelled['status'] == 'expired'
        assert cancelled['revision'] == 2
        assert cancelled['draft'] is None
        assert (await authorized_client.get(CURRICULUM['imports'])).json() == []
    finally:
        local_ai.gate.set()
        if not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_concurrent_same_session_confirmation_creates_exactly_one_curriculum(
    authorized_client, local_ai, captured_jobs,
):
    ready = await _ready_session(authorized_client, captured_jobs)
    responses = await asyncio.gather(*[
        _confirm(authorized_client, ready['id'], ready['draft'], ready['revision'])
        for _ in range(2)
    ])
    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()['error']['code'] in {
        'curriculum_ai_import_session_stale', 'curriculum_ai_import_session_confirmed',
    }
    assert len((await authorized_client.get(CURRICULUM['imports'])).json()) == 1
    assert (await _get(authorized_client, ready['id'])).json()['status'] == 'confirmed'


@pytest.mark.asyncio
async def test_concurrent_different_titles_recheck_content_duplicates_atomically(authorized_client):
    drafts = [{**copy.deepcopy(DRAFT), 'name': title} for title in ('First upload.txt', 'Second upload.pdf')]
    responses = await asyncio.gather(*[
        authorized_client.post(CURRICULUM['import_confirm'], json={'draft': draft})
        for draft in drafts
    ])
    assert sorted(response.status_code for response in responses) == [201, 409]
    imported = next(response for response in responses if response.status_code == 201).json()
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()['error']['code'] == 'curriculum_import_duplicate_conflict'
    assert [match['id'] for match in conflict.json()['error']['details']['matches']] == [imported['id']]
    assert len((await authorized_client.get(CURRICULUM['imports'])).json()) == 1


@pytest.mark.asyncio
async def test_native_format_expands_real_pydantic_refs_and_preserves_nullable_constraints(local_ai):
    raw_schema = CurriculumImportDocument.model_json_schema()
    assert raw_schema['$defs']
    assert '$ref' in json.dumps(raw_schema)
    model_response = copy.deepcopy(DRAFT)
    model_response['description'] = None
    model_response['metadata']['edition'] = None
    lesson = model_response['subjects'][0]['units'][0]['lessons'][0]
    lesson['estimated_minutes'] = None
    lesson['resources'] = [{'name': 'Plant diagram', 'url': None, 'description': None}]
    local_ai.script = [model_response]
    draft, _ = await AICurriculumImportService().build_draft_from_bytes(
        b'Plants scope', filename='plants.txt', content_type='text/plain',
    )
    sent_schema = local_ai.requests[0]['json']['format']
    assert '$ref' not in json.dumps(sent_schema)
    assert '$defs' not in json.dumps(sent_schema)
    assert sent_schema['additionalProperties'] is False
    lesson_schema = sent_schema['properties']['subjects']['items']['properties']['units']['items']['properties']['lessons']['items']
    assert {'type': 'null'} in lesson_schema['properties']['estimated_minutes']['anyOf']
    assert {'type': 'null'} in lesson_schema['properties']['resources']['items']['properties']['url']['anyOf']
    assert draft.subjects[0].units[0].lessons[0].estimated_minutes is None
    assert len(local_ai.requests) == 1
