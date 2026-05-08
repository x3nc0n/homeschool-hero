from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.contracts import GRADING, SERVICE_CANDIDATES
from tests.helpers import maybe_await, require_route, resolve_attr


def _load_service_module(*names: str):
    import importlib

    for name in names:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError as exc:
            missing = exc.name or ""
            root_name = name.split(".")[0]
            if missing in {name, root_name}:
                continue
            raise
    pytest.skip("Grading service modules are not implemented yet.")


@pytest.mark.asyncio
@pytest.mark.xfail(reason="OCR implementation is still a stub in the current backend branch.", strict=False)
async def test_ocr_service_uses_mocked_tesseract(monkeypatch):
    ocr_module = _load_service_module("services.ocr", "backend.services.ocr")
    extractor = resolve_attr(ocr_module, SERVICE_CANDIDATES["ocr"], label="OCR service")

    monkeypatch.setattr("PIL.Image.open", lambda *_args, **_kwargs: SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        "pytesseract.image_to_string",
        lambda *_args, **_kwargs: "problem 1: 3/4\nproblem 2: 1/2",
        raising=False,
    )

    result = await maybe_await(extractor("worksheet.png"))

    assert isinstance(result, str)
    assert "3/4" in result


@pytest.mark.asyncio
@pytest.mark.xfail(reason="AI grader implementation is still a stub in the current backend branch.", strict=False)
async def test_ai_grader_returns_mocked_score_and_confidence(monkeypatch):
    grader_module = _load_service_module("services.ai_grader", "backend.services.ai_grader")
    grader = resolve_attr(grader_module, SERVICE_CANDIDATES["ai_grade"], label="AI grader")

    fake_payload = {
        "score": 92,
        "max_score": 100,
        "confidence": 0.93,
        "feedback": "Accurate work with clear reasoning.",
    }
    monkeypatch.setattr(
        grader_module,
        "_call_model",
        lambda *_args, **_kwargs: fake_payload,
        raising=False,
    )

    result = await maybe_await(
        grader(
            assignment_description="Fractions worksheet",
            answer_key="1) 3/4\n2) 1/2",
            submission_text="1) 3/4\n2) 1/2",
        )
    )

    assert result["score"] == 92
    assert result["confidence"] >= 0.8


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Grading worker processing flow is not implemented yet.", strict=False)
async def test_grading_worker_auto_completes_high_confidence_job(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text_from_image", lambda *_args, **_kwargs: "correct work", raising=False)
    monkeypatch.setattr(
        worker_module,
        "grade_submission_text",
        lambda *_args, **_kwargs: {"score": 97, "max_score": 100, "confidence": 0.95, "feedback": "Excellent"},
        raising=False,
    )
    job = {"id": 10, "status": "queued", "submission_id": 3}

    result = await maybe_await(processor(job))

    assert result["status"] in {"complete", "completed"}
    assert result["ai_confidence"] >= 0.8


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Grading worker processing flow is not implemented yet.", strict=False)
async def test_grading_worker_routes_low_confidence_job_to_review(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text_from_image", lambda *_args, **_kwargs: "unclear work", raising=False)
    monkeypatch.setattr(
        worker_module,
        "grade_submission_text",
        lambda *_args, **_kwargs: {"score": 74, "max_score": 100, "confidence": 0.42, "feedback": "Needs review"},
        raising=False,
    )
    job = {"id": 11, "status": "queued", "submission_id": 4}

    result = await maybe_await(processor(job))

    assert result["status"] == "needs_review"
    assert result["ai_confidence"] < 0.8


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Grading worker processing flow is not implemented yet.", strict=False)
async def test_grading_worker_ai_failure_falls_back_to_review(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text_from_image", lambda *_args, **_kwargs: "some work", raising=False)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(worker_module, "grade_submission_text", _raise, raising=False)
    job = {"id": 12, "status": "queued", "submission_id": 5}

    result = await maybe_await(processor(job))

    assert result["status"] == "needs_review"
    assert "error" in result or result.get("error_message")


@pytest.mark.asyncio
async def test_review_queue_requires_authentication(async_client, app):
    require_route(app, "GET", GRADING["review_queue"])
    response = await async_client.get(GRADING["review_queue"])

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_review_queue_lists_pending_jobs(authorized_client, app):
    require_route(app, "GET", GRADING["review_queue"])
    response = await authorized_client.get(GRADING["review_queue"])

    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, (list, dict))


@pytest.mark.asyncio
async def test_review_queue_approve_and_reject_flows(authorized_client, app):
    require_route(app, "POST", GRADING["approve"].format(job_id="{job_id}"))
    require_route(app, "POST", GRADING["reject"].format(job_id="{job_id}"))
    list_response = await authorized_client.get(GRADING["review_queue"])
    assert list_response.status_code == 200, list_response.text
    payload = list_response.json()
    items = payload if isinstance(payload, list) else payload.get("items", [])
    if not items:
        pytest.skip("No review jobs are seeded yet; enable this assertion when backend seeds review jobs.")

    job_id = items[0]["id"]

    approve = await authorized_client.post(
        GRADING["approve"].format(job_id=job_id),
        json={"score": 89, "feedback": "Approved after review", "graded_by": "ai+human"},
    )
    assert approve.status_code in {200, 204}, approve.text

    reject = await authorized_client.post(
        GRADING["reject"].format(job_id=job_id),
        json={"reason": "OCR mismatch", "graded_by": "human"},
    )
    assert reject.status_code in {200, 204}, reject.text
