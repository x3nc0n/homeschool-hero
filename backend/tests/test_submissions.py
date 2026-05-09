from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import GradingJob, GradingJobStatus
from tests.contracts import SUBMISSIONS, UPLOADS_DIR
from tests.helpers import assert_validation_error, require_route, response_id

PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0'
    b'\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82'
)


@pytest.mark.asyncio
async def test_submissions_accept_file_upload_and_queue_grading(
    authorized_client,
    seeded_assignment,
    seeded_student,
    app,
):
    require_route(app, 'POST', SUBMISSIONS['upload'])
    response = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('fractions.png', PNG_BYTES, 'image/png')},
    )

    assert response.status_code in {200, 201, 202}, response.text
    payload = response.json()
    assert payload['assignment_id'] == response_id(seeded_assignment)
    assert payload['student_id'] == response_id(seeded_student)
    assert payload['file_type'] == 'image/png'
    assert payload['submission_version'] == 1
    assert payload['is_current'] is True
    assert payload['file_size_bytes'] == len(PNG_BYTES)
    assert payload['image_width'] == 1
    assert payload['image_height'] == 1
    assert payload['page_count'] is None
    assert 'file' not in payload, 'raw file bytes should never be echoed back'


@pytest.mark.asyncio
async def test_submissions_list_and_detail_return_current_submission_history(authorized_client, seeded_submission, app):
    require_route(app, 'GET', SUBMISSIONS['collection'])
    require_route(app, 'GET', SUBMISSIONS['detail'].format(submission_id='{submission_id}'))
    submission_id = response_id(seeded_submission)

    listing = await authorized_client.get(SUBMISSIONS['collection'])
    assert listing.status_code == 200, listing.text
    assert [response_id(item) for item in listing.json()] == [submission_id]

    detail = await authorized_client.get(SUBMISSIONS['detail'].format(submission_id=submission_id))
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert response_id(payload) == submission_id
    assert len(payload['version_history']) == 1
    assert payload['version_history'][0]['submission_version'] == 1


@pytest.mark.asyncio
async def test_submissions_reject_missing_file(authorized_client, seeded_assignment, seeded_student):
    response = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
    )

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_submissions_reject_unsupported_mime_type(authorized_client, seeded_assignment, seeded_student):
    response = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('notes.txt', b'not allowed', 'text/plain')},
    )

    assert response.status_code == 400, response.text
    assert response.json()['detail'] == 'Unsupported file type'


@pytest.mark.asyncio
async def test_submissions_reject_oversized_files(monkeypatch, authorized_client, seeded_assignment, seeded_student):
    monkeypatch.setattr(settings, 'upload_max_bytes', 8)
    response = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('fractions.png', PNG_BYTES, 'image/png')},
    )

    assert response.status_code == 413, response.text
    assert response.json()['detail'] == 'Uploaded file exceeds size limit'


@pytest.mark.asyncio
async def test_submissions_sanitize_path_traversal_filenames(authorized_client, seeded_assignment, seeded_student):
    response = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('..\\..\\bad<>name?.png', PNG_BYTES, 'image/png')},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload['file_name'] == 'bad_name_.png'
    assert '..' not in payload['file_path']
    assert payload['file_path'].replace('\\', '/').endswith('/bad_name_.png')


@pytest.mark.asyncio
async def test_submissions_resubmission_preserves_version_history_and_current_flag(
    authorized_client,
    seeded_assignment,
    seeded_student,
):
    first_response = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('draft-one.png', PNG_BYTES, 'image/png')},
    )
    assert first_response.status_code == 201, first_response.text
    first_submission = first_response.json()

    second_response = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
            'resubmission_of_submission_id': str(first_submission['id']),
        },
        files={'file': ('draft-two.png', PNG_BYTES, 'image/png')},
    )
    assert second_response.status_code == 201, second_response.text
    resubmission = second_response.json()

    assert resubmission['submission_version'] == 2
    assert resubmission['parent_submission_id'] == first_submission['id']
    assert resubmission['is_current'] is True
    assert [item['submission_version'] for item in resubmission['version_history']] == [2, 1]
    assert resubmission['version_history'][0]['is_current'] is True
    assert resubmission['version_history'][1]['id'] == first_submission['id']
    assert resubmission['version_history'][1]['is_current'] is False

    listing = await authorized_client.get(SUBMISSIONS['collection'])
    assert listing.status_code == 200, listing.text
    assert [item['id'] for item in listing.json()] == [resubmission['id']]

    detail = await authorized_client.get(SUBMISSIONS['detail'].format(submission_id=first_submission['id']))
    assert detail.status_code == 200, detail.text
    assert [item['submission_version'] for item in detail.json()['version_history']] == [2, 1]

    async with AsyncSessionLocal() as session:
        jobs = (await session.execute(select(GradingJob).order_by(GradingJob.submission_id))).scalars().all()
    assert [job.status for job in jobs] == [GradingJobStatus.final, GradingJobStatus.pending]


@pytest.mark.asyncio
async def test_submissions_store_files_in_deterministic_paths(authorized_client, seeded_assignment, seeded_student):
    response = await authorized_client.post(
        SUBMISSIONS['upload'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('fractions.png', PNG_BYTES, 'image/png')},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    normalized_path = payload['file_path'].replace('\\', '/')
    path_parts = normalized_path.split('/')
    assert len(path_parts) == 5
    assert path_parts[0].isdigit()
    expected_suffix = f"{payload['student_id']}/{payload['assignment_id']}/{payload['id']}/{payload['file_name']}"
    assert normalized_path.endswith(expected_suffix)
    stored_file = UPLOADS_DIR / Path(payload['file_path'])
    assert stored_file.exists()


@pytest.mark.asyncio
async def test_submissions_require_authentication(async_client):
    response = await async_client.post(
        SUBMISSIONS['upload'],
        data={'assignment_id': '1', 'student_id': '1'},
        files={'file': ('fractions.png', PNG_BYTES, 'image/png')},
    )

    assert response.status_code == 401, response.text
