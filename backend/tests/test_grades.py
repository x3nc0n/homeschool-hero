from __future__ import annotations

import pytest

from tests.contracts import GRADES, grade_payload
from tests.helpers import assert_validation_error, response_id, update_resource


@pytest.mark.asyncio
async def test_grades_crud_happy_path(authorized_client, seeded_submission, seeded_student):
    create = await authorized_client.post(
        GRADES["collection"],
        json=grade_payload(response_id(seeded_submission), response_id(seeded_student)),
    )
    assert create.status_code in {200, 201}, create.text
    created = create.json()
    grade_id = response_id(created)

    listing = await authorized_client.get(GRADES["collection"])
    assert listing.status_code == 200, listing.text
    assert any(response_id(item) == grade_id for item in listing.json()["items"])

    detail = await authorized_client.get(GRADES["detail"].format(grade_id=grade_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()["score"] == 88

    update = await update_resource(
        authorized_client,
        GRADES["detail"].format(grade_id=grade_id),
        {
            **grade_payload(response_id(seeded_submission), response_id(seeded_student)),
            "score": 95,
            "letter_grade": "A",
            "graded_by": "ai+human",
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["score"] == 95
    assert update.json()["graded_by"] == "ai+human"

    delete = await authorized_client.delete(GRADES["detail"].format(grade_id=grade_id))
    assert delete.status_code == 204, delete.text


@pytest.mark.asyncio
async def test_grade_queries_return_history_and_averages(authorized_client, seeded_grade, seeded_student, seeded_subject):
    history = await authorized_client.get(GRADES["history"])
    assert history.status_code == 200, history.text
    history_payload = history.json()["items"]
    assert history_payload, "expected at least one grade history row"
    assert history_payload[0]["student_id"] == response_id(seeded_student)

    student_averages = await authorized_client.get(
        GRADES["student_averages"].format(student_id=response_id(seeded_student))
    )
    assert student_averages.status_code == 200, student_averages.text
    assert student_averages.json()

    subject_averages = await authorized_client.get(
        GRADES["subject_averages"].format(subject_id=response_id(seeded_subject))
    )
    assert subject_averages.status_code == 200, subject_averages.text
    assert subject_averages.json()


@pytest.mark.asyncio
async def test_grades_reject_invalid_payload(authorized_client):
    response = await authorized_client.post(GRADES["collection"], json={"score": 100})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_grades_return_404_for_missing_id(authorized_client):
    response = await authorized_client.get(GRADES["detail"].format(grade_id=999999))

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_grades_require_authentication(async_client):
    response = await async_client.get(GRADES["collection"])

    assert response.status_code == 401, response.text
