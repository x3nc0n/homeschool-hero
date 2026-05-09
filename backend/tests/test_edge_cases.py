from __future__ import annotations

import asyncio

import pytest

from backend.config import settings
from tests.contracts import DASHBOARD, GRADEBOOK, SEARCH
from tests.helpers import response_id


@pytest.mark.asyncio
async def test_empty_state_endpoints_return_stable_payloads(authorized_client, seeded_student):
    dashboard = await authorized_client.get(DASHBOARD['summary'])
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()['recent_grades'] == []
    assert len(dashboard.json()['student_summaries']) == 1

    gradebook = await authorized_client.get(GRADEBOOK['detail'].format(student_id=response_id(seeded_student)))
    assert gradebook.status_code == 200, gradebook.text
    assert gradebook.json()['subjects'] == []
    assert gradebook.json()['gpa'] is None

    search = await authorized_client.get(f"{SEARCH['collection']}?q=definitely-no-results")
    assert search.status_code == 200, search.text
    assert search.json()['total'] == 0


@pytest.mark.asyncio
async def test_upload_limits_and_special_character_payloads(monkeypatch, authorized_client, seeded_assignment, seeded_student, seeded_subject):
    special_subject = await authorized_client.put(
        f"/api/subjects/{seeded_subject['id']}",
        json={'name': 'Español & Geometry — Δ', 'color': '#16a34a'},
    )
    assert special_subject.status_code == 200, special_subject.text
    assert 'Δ' in special_subject.json()['name']

    monkeypatch.setattr(settings, 'upload_max_bytes', 10)
    too_large = await authorized_client.post(
        '/api/submissions',
        data={'assignment_id': str(seeded_assignment['id']), 'student_id': str(seeded_student['id'])},
        files={'file': ('big.txt', b'01234567890', 'text/plain')},
    )
    assert too_large.status_code == 413, too_large.text


@pytest.mark.asyncio
async def test_concurrent_resubmissions_keep_one_current_version(authorized_client, seeded_assignment, seeded_student):
    original = await authorized_client.post(
        '/api/submissions',
        data={'assignment_id': str(seeded_assignment['id']), 'student_id': str(seeded_student['id'])},
        files={'file': ('original.png', b'\x89PNG\r\n\x1a\n', 'image/png')},
    )
    assert original.status_code in {200, 201, 202}, original.text
    original_id = response_id(original.json())

    async def _resubmit(name: str, payload: bytes):
        return await authorized_client.post(
            '/api/submissions',
            data={
                'assignment_id': str(seeded_assignment['id']),
                'student_id': str(seeded_student['id']),
                'resubmission_of_submission_id': str(original_id),
            },
            files={'file': (name, payload, 'image/png')},
        )

    first, second = await asyncio.gather(
        _resubmit('resubmit-1.png', b'\x89PNG\r\n\x1a\none'),
        _resubmit('resubmit-2.png', b'\x89PNG\r\n\x1a\ntwo'),
    )
    assert first.status_code in {200, 201, 202}, first.text
    assert second.status_code in {200, 201, 202}, second.text

    detail = await authorized_client.get(f"/api/submissions/{response_id(second.json())}")
    assert detail.status_code == 200, detail.text
    versions = detail.json()['version_history']
    assert len(versions) == 3
    assert sum(1 for item in versions if item['is_current']) == 1
    assert min(item['submission_version'] for item in versions) == 1
    assert max(item['submission_version'] for item in versions) >= 2
