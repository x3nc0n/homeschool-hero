from __future__ import annotations

import pytest

from tests.contracts import QUIZZES, quiz_payload
from tests.helpers import assert_validation_error, response_id, update_resource


@pytest.mark.asyncio
async def test_quizzes_crud_happy_path(authorized_client, seeded_subject):
    create = await authorized_client.post(
        QUIZZES["collection"],
        json=quiz_payload(response_id(seeded_subject)),
    )
    assert create.status_code in {200, 201}, create.text
    created = create.json()
    quiz_id = response_id(created)

    listing = await authorized_client.get(QUIZZES["collection"])
    assert listing.status_code == 200, listing.text
    assert any(response_id(item) == quiz_id for item in listing.json())

    detail = await authorized_client.get(QUIZZES["detail"].format(quiz_id=quiz_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()["title"] == "Fractions Check-In"

    update = await update_resource(
        authorized_client,
        QUIZZES["detail"].format(quiz_id=quiz_id),
        {
            **quiz_payload(response_id(seeded_subject)),
            "title": "Updated Fractions Check-In",
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["title"] == "Updated Fractions Check-In"

    delete = await authorized_client.delete(QUIZZES["detail"].format(quiz_id=quiz_id))
    assert delete.status_code == 204, delete.text


@pytest.mark.asyncio
async def test_quiz_attempt_is_auto_scored(authorized_client, seeded_quiz, quiz_attempt_body):
    response = await authorized_client.post(
        QUIZZES["attempts"].format(quiz_id=response_id(seeded_quiz)),
        json=quiz_attempt_body,
    )

    assert response.status_code in {200, 201}, response.text
    payload = response.json()
    assert payload["score"] == payload["max_score"]

    list_attempts = await authorized_client.get(QUIZZES["attempts_list"].format(quiz_id=response_id(seeded_quiz)))
    assert list_attempts.status_code == 200, list_attempts.text
    assert list_attempts.json(), "expected recorded quiz attempts"


@pytest.mark.asyncio
async def test_quizzes_reject_invalid_payload(authorized_client):
    response = await authorized_client.post(QUIZZES["collection"], json={"title": "Incomplete"})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_quizzes_return_404_for_missing_id(authorized_client):
    response = await authorized_client.get(QUIZZES["detail"].format(quiz_id=999999))

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_quizzes_require_authentication(async_client):
    response = await async_client.get(QUIZZES["collection"])

    assert response.status_code == 401, response.text
