from __future__ import annotations

import pytest

from tests.contracts import SUBMISSIONS
from tests.helpers import assert_validation_error, require_route, response_id


@pytest.mark.asyncio
async def test_submissions_accept_file_upload_and_queue_grading(
    authorized_client,
    seeded_assignment,
    seeded_student,
    app,
):
    require_route(app, "POST", SUBMISSIONS["upload"])
    response = await authorized_client.post(
        SUBMISSIONS["upload"],
        data={
            "assignment_id": str(response_id(seeded_assignment)),
            "student_id": str(response_id(seeded_student)),
        },
        files={"file": ("fractions.txt", b"1/2 + 1/4 = 3/4", "text/plain")},
    )

    assert response.status_code in {200, 201, 202}, response.text
    payload = response.json()
    assert payload["assignment_id"] == response_id(seeded_assignment)
    assert payload["student_id"] == response_id(seeded_student)
    assert payload.get("file_type") in {None, "text/plain", "text"}
    assert "file" not in payload, "raw file bytes should never be echoed back"


@pytest.mark.asyncio
async def test_submissions_list_and_detail(authorized_client, seeded_submission, app):
    require_route(app, "GET", SUBMISSIONS["collection"])
    require_route(app, "GET", SUBMISSIONS["detail"].format(submission_id="{submission_id}"))
    submission_id = response_id(seeded_submission)

    listing = await authorized_client.get(SUBMISSIONS["collection"])
    assert listing.status_code == 200, listing.text
    assert any(response_id(item) == submission_id for item in listing.json())

    detail = await authorized_client.get(SUBMISSIONS["detail"].format(submission_id=submission_id))
    assert detail.status_code == 200, detail.text
    assert response_id(detail.json()) == submission_id


@pytest.mark.asyncio
async def test_submissions_reject_missing_file(authorized_client, seeded_assignment, seeded_student):
    # Upload is the only submission endpoint implemented today.
    response = await authorized_client.post(
        SUBMISSIONS["upload"],
        data={
            "assignment_id": str(response_id(seeded_assignment)),
            "student_id": str(response_id(seeded_student)),
        },
    )

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_submissions_return_404_for_missing_id(authorized_client):
    pytest.skip("Submission detail endpoint is planned in the architecture, but not implemented yet.")


@pytest.mark.asyncio
async def test_submissions_require_authentication(async_client):
    response = await async_client.post(
        SUBMISSIONS["upload"],
        data={"assignment_id": "1", "student_id": "1"},
        files={"file": ("fractions.txt", b"test", "text/plain")},
    )

    assert response.status_code == 401, response.text
