from __future__ import annotations

import pytest

from tests.contracts import ASSIGNMENTS, assignment_payload
from tests.helpers import assert_validation_error, response_id, update_resource


@pytest.mark.asyncio
async def test_assignments_crud_happy_path(authorized_client, seeded_subject):
    create = await authorized_client.post(
        ASSIGNMENTS["collection"],
        json=assignment_payload(response_id(seeded_subject)),
    )
    assert create.status_code in {200, 201}, create.text
    created = create.json()
    assignment_id = response_id(created)

    listing = await authorized_client.get(ASSIGNMENTS["collection"])
    assert listing.status_code == 200, listing.text
    assert any(response_id(item) == assignment_id for item in listing.json())

    detail = await authorized_client.get(ASSIGNMENTS["detail"].format(assignment_id=assignment_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()["title"] == "Fractions Worksheet"

    update = await update_resource(
        authorized_client,
        ASSIGNMENTS["detail"].format(assignment_id=assignment_id),
        {
            **assignment_payload(response_id(seeded_subject)),
            "status": "graded",
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["status"] == "graded"

    status_update = await authorized_client.patch(
        ASSIGNMENTS["status"].format(assignment_id=assignment_id),
        json={"status": "complete"},
    )
    assert status_update.status_code in {200, 400}, status_update.text
    if status_update.status_code == 200:
        assert status_update.json()["status"] == "complete"
    else:
        assert "Invalid status transition" in status_update.text

    delete = await authorized_client.delete(ASSIGNMENTS["detail"].format(assignment_id=assignment_id))
    assert delete.status_code == 204, delete.text


@pytest.mark.asyncio
async def test_assignments_reject_invalid_payload(authorized_client):
    response = await authorized_client.post(ASSIGNMENTS["collection"], json={"status": "pending"})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_assignments_return_404_for_missing_id(authorized_client):
    response = await authorized_client.get(ASSIGNMENTS["detail"].format(assignment_id=999999))

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_assignments_require_authentication(async_client):
    response = await async_client.get(ASSIGNMENTS["collection"])

    assert response.status_code == 401, response.text
