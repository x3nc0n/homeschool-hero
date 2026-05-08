from __future__ import annotations

import pytest

from tests.contracts import STUDENTS, student_payload
from tests.helpers import assert_validation_error, response_id, update_resource


@pytest.mark.asyncio
async def test_students_crud_happy_path(authorized_client):
    create = await authorized_client.post(STUDENTS["collection"], json=student_payload())
    assert create.status_code in {200, 201}, create.text
    created = create.json()
    student_id = response_id(created)

    listing = await authorized_client.get(STUDENTS["collection"])
    assert listing.status_code == 200, listing.text
    assert any(response_id(item) == student_id for item in listing.json())

    detail = await authorized_client.get(STUDENTS["detail"].format(student_id=student_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "Ada Lovelace"

    update = await update_resource(
        authorized_client,
        STUDENTS["detail"].format(student_id=student_id),
        student_payload(name="Grace Hopper"),
    )
    assert update.status_code == 200, update.text
    assert update.json()["name"] == "Grace Hopper"

    delete = await authorized_client.delete(STUDENTS["detail"].format(student_id=student_id))
    assert delete.status_code == 204, delete.text


@pytest.mark.asyncio
async def test_students_reject_invalid_payload(authorized_client):
    response = await authorized_client.post(STUDENTS["collection"], json={})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_students_return_404_for_missing_id(authorized_client):
    response = await authorized_client.get(STUDENTS["detail"].format(student_id=999999))

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_students_require_authentication(async_client):
    response = await async_client.get(STUDENTS["collection"])

    assert response.status_code == 401, response.text
