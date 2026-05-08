from __future__ import annotations

import pytest

from tests.contracts import SUBJECTS, subject_payload
from tests.helpers import assert_validation_error, response_id, update_resource


@pytest.mark.asyncio
async def test_subjects_crud_happy_path(authorized_client):
    create = await authorized_client.post(SUBJECTS["collection"], json=subject_payload())
    assert create.status_code in {200, 201}, create.text
    created = create.json()
    subject_id = response_id(created)

    listing = await authorized_client.get(SUBJECTS["collection"])
    assert listing.status_code == 200, listing.text
    assert any(response_id(item) == subject_id for item in listing.json())

    detail = await authorized_client.get(SUBJECTS["detail"].format(subject_id=subject_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "Math"

    update = await update_resource(
        authorized_client,
        SUBJECTS["detail"].format(subject_id=subject_id),
        subject_payload(name="Science", color="#16a34a"),
    )
    assert update.status_code == 200, update.text
    assert update.json()["name"] == "Science"

    delete = await authorized_client.delete(SUBJECTS["detail"].format(subject_id=subject_id))
    assert delete.status_code == 204, delete.text


@pytest.mark.asyncio
async def test_subjects_reject_invalid_payload(authorized_client):
    response = await authorized_client.post(SUBJECTS["collection"], json={"color": "#fff"})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_subjects_return_404_for_missing_id(authorized_client):
    response = await authorized_client.get(SUBJECTS["detail"].format(subject_id=999999))

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_subjects_require_authentication(async_client):
    response = await async_client.get(SUBJECTS["collection"])

    assert response.status_code == 401, response.text
