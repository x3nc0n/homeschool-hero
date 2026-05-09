from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models import AuditEvent, GradingJob, GradingJobStatus

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


def _artifact_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".pytest-state" / "grading-pipeline"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.mark.asyncio
async def test_ocr_service_uses_mocked_tesseract(monkeypatch):
    ocr_module = _load_service_module("services.ocr", "backend.services.ocr")
    extractor = resolve_attr(ocr_module, SERVICE_CANDIDATES["ocr"], label="OCR service")
    image_path = _artifact_dir() / "worksheet.png"
    Image.new("RGB", (8, 8), "white").save(image_path)

    monkeypatch.setattr(ocr_module, "preprocess_image", lambda image: image)
    monkeypatch.setattr(
        "pytesseract.image_to_string",
        lambda *_args, **_kwargs: "problem 1: 3/4\nproblem 2: 1/2",
        raising=False,
    )

    result = await maybe_await(extractor(str(image_path)))

    assert isinstance(result, str)
    assert "3/4" in result


@pytest.mark.asyncio
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
async def test_grading_worker_auto_completes_high_confidence_job(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text", lambda *_args, **_kwargs: "correct work", raising=False)
    monkeypatch.setattr(
        worker_module.get_capability_registry(),
        "check_all_sync",
        lambda: {
            "ai_grading": {"name": "ai_grading", "enabled": True, "reason": "ok"},
            "email": {"name": "email", "enabled": False, "reason": "disabled"},
            "backup": {"name": "backup", "enabled": False, "reason": "disabled"},
            "ocr": {"name": "ocr", "enabled": True, "reason": "ok"},
        },
        raising=False,
    )
    monkeypatch.setattr(
        worker_module,
        "grade_submission_text",
        lambda *_args, **_kwargs: {"score": 97, "max_score": 100, "confidence": 0.95, "feedback": "Excellent"},
        raising=False,
    )
    job = {"id": 10, "status": "queued", "submission_id": 3}

    result = await maybe_await(processor(job))

    assert result["status"] == "final"
    assert result["ai_confidence"] >= 0.8
    assert result["status_history"]
    assert result["status_history"][-1]["status"] == "final"


@pytest.mark.asyncio
async def test_grading_worker_routes_low_confidence_job_to_review(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text", lambda *_args, **_kwargs: "unclear work", raising=False)
    monkeypatch.setattr(
        worker_module.get_capability_registry(),
        "check_all_sync",
        lambda: {
            "ai_grading": {"name": "ai_grading", "enabled": True, "reason": "ok"},
            "email": {"name": "email", "enabled": False, "reason": "disabled"},
            "backup": {"name": "backup", "enabled": False, "reason": "disabled"},
            "ocr": {"name": "ocr", "enabled": True, "reason": "ok"},
        },
        raising=False,
    )
    monkeypatch.setattr(
        worker_module,
        "grade_submission_text",
        lambda *_args, **_kwargs: {"score": 74, "max_score": 100, "confidence": 0.42, "feedback": "Needs review"},
        raising=False,
    )
    job = {"id": 11, "status": "queued", "submission_id": 4}

    result = await maybe_await(processor(job))

    assert result["status"] == "review_needed"
    assert result["ai_confidence"] < 0.8


@pytest.mark.asyncio
async def test_grading_worker_ai_failure_falls_back_to_review(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text", lambda *_args, **_kwargs: "some work", raising=False)
    monkeypatch.setattr(
        worker_module.get_capability_registry(),
        "check_all_sync",
        lambda: {
            "ai_grading": {"name": "ai_grading", "enabled": True, "reason": "ok"},
            "email": {"name": "email", "enabled": False, "reason": "disabled"},
            "backup": {"name": "backup", "enabled": False, "reason": "disabled"},
            "ocr": {"name": "ocr", "enabled": True, "reason": "ok"},
        },
        raising=False,
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(worker_module, "grade_submission_text", _raise, raising=False)
    job = {"id": 12, "status": "queued", "submission_id": 5}

    result = await maybe_await(processor(job))

    assert result["status"] == "review_needed"
    assert "error" in result or result.get("error_message")


@pytest.mark.asyncio
async def test_grading_worker_routes_directly_to_review_when_ai_capability_is_disabled(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text", lambda *_args, **_kwargs: "some work", raising=False)
    monkeypatch.setattr(
        worker_module.get_capability_registry(),
        "check_all_sync",
        lambda: {
            "ai_grading": {"name": "ai_grading", "enabled": False, "reason": "AI provider is down"},
            "email": {"name": "email", "enabled": False, "reason": "disabled"},
            "backup": {"name": "backup", "enabled": False, "reason": "disabled"},
            "ocr": {"name": "ocr", "enabled": True, "reason": "ok"},
        },
        raising=False,
    )

    monkeypatch.setattr(
        worker_module,
        "grade_submission_text",
        lambda *_args, **_kwargs: pytest.fail("AI grader should not run when capability is disabled"),
        raising=False,
    )
    job = {"id": 13, "status": "queued", "submission_id": 6}

    result = await maybe_await(processor(job))

    assert result["status"] == "review_needed"
    assert "AI grading unavailable" in result["error_message"]


@pytest.mark.asyncio
async def test_grading_worker_scores_with_answer_key(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text", lambda *_args, **_kwargs: "1) 3/4\n2) 1/2", raising=False)
    monkeypatch.setattr(
        worker_module.get_capability_registry(),
        "check_all_sync",
        lambda: {
            "ai_grading": {"name": "ai_grading", "enabled": True, "reason": "ok"},
            "email": {"name": "email", "enabled": False, "reason": "disabled"},
            "backup": {"name": "backup", "enabled": False, "reason": "disabled"},
            "ocr": {"name": "ocr", "enabled": True, "reason": "ok"},
        },
        raising=False,
    )
    monkeypatch.setattr(
        worker_module,
        "grade_submission_text",
        lambda *_args, **_kwargs: {"score": 100, "max_score": 100, "confidence": 0.9, "feedback": "Looks good"},
        raising=False,
    )

    result = await maybe_await(
        processor(
            {
                "id": 22,
                "status": "queued",
                "submission_id": 1,
                "answer_key_questions": [
                    {"question_number": "1", "correct_answer": "3/4", "points": 2},
                    {"question_number": "2", "correct_answer": "1/2", "points": 3},
                ],
            }
        )
    )

    assert result["status"] == "final"
    assert result["answer_key_result"]["score"] == 5
    assert result["answer_key_result"]["max_score"] == 5
    assert result["ai_confidence"] >= 0.8


@pytest.mark.asyncio
async def test_grading_worker_opens_circuit_breaker(monkeypatch):
    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text", lambda *_args, **_kwargs: "some work", raising=False)
    monkeypatch.setattr(worker_module.settings, "grading_retry_attempts", 1, raising=False)
    monkeypatch.setattr(worker_module.settings, "ai_circuit_breaker_threshold", 1, raising=False)
    worker_module.ai_circuit_breaker.record_success()
    monkeypatch.setattr(
        worker_module.get_capability_registry(),
        "check_all_sync",
        lambda: {
            "ai_grading": {"name": "ai_grading", "enabled": True, "reason": "ok"},
            "email": {"name": "email", "enabled": False, "reason": "disabled"},
            "backup": {"name": "backup", "enabled": False, "reason": "disabled"},
            "ocr": {"name": "ocr", "enabled": True, "reason": "ok"},
        },
        raising=False,
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(worker_module, "grade_submission_text", _raise, raising=False)
    first = await maybe_await(processor({"id": 31, "status": "queued", "submission_id": 1}))
    second = await maybe_await(processor({"id": 32, "status": "queued", "submission_id": 2}))

    assert first["status"] == "review_needed"
    assert second["manual_review_reason"] == "AI circuit breaker is open; manual review required."
    worker_module.ai_circuit_breaker.record_success()


@pytest.mark.asyncio
async def test_grading_worker_handles_timeouts(monkeypatch):
    import time

    worker_module = _load_service_module("services.grading_worker", "backend.services.grading_worker")
    processor = resolve_attr(worker_module, SERVICE_CANDIDATES["worker"], label="Grading worker")

    monkeypatch.setattr(worker_module, "extract_text", lambda *_args, **_kwargs: "some work", raising=False)
    monkeypatch.setattr(worker_module.settings, "grading_retry_attempts", 1, raising=False)
    monkeypatch.setattr(worker_module.settings, "grading_request_timeout_seconds", 0.01, raising=False)
    monkeypatch.setattr(
        worker_module.get_capability_registry(),
        "check_all_sync",
        lambda: {
            "ai_grading": {"name": "ai_grading", "enabled": True, "reason": "ok"},
            "email": {"name": "email", "enabled": False, "reason": "disabled"},
            "backup": {"name": "backup", "enabled": False, "reason": "disabled"},
            "ocr": {"name": "ocr", "enabled": True, "reason": "ok"},
        },
        raising=False,
    )

    def _sleep(*_args, **_kwargs):
        time.sleep(0.05)
        return {"score": 90, "max_score": 100, "confidence": 0.9, "feedback": "Late"}

    monkeypatch.setattr(worker_module, "grade_submission_text", _sleep, raising=False)
    result = await maybe_await(processor({"id": 41, "status": "queued", "submission_id": 1}))

    assert result["status"] == "review_needed"
    assert "timed out" in result["error_message"]


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


@pytest.mark.asyncio
async def test_answer_key_and_grading_job_audit_flow(authorized_client, seeded_assignment, seeded_submission):
    answer_key_response = await authorized_client.put(
        f"/api/assignments/{seeded_assignment['id']}/answer-key",
        json={
            "questions": [
                {"question_number": "1", "correct_answer": "3/4", "points": 2},
                {"question_number": "2", "correct_answer": "1/2", "points": 3, "partial_credit_rules": "50%"},
            ]
        },
    )
    assert answer_key_response.status_code == 200, answer_key_response.text
    assert len(answer_key_response.json()["questions"]) == 2

    async with AsyncSessionLocal() as session:
        job = (
            await session.execute(select(GradingJob).where(GradingJob.submission_id == seeded_submission["id"]))
        ).scalar_one()
        job.status = GradingJobStatus.review_needed
        job.ai_grade = 88
        job.ai_feedback = "Needs a quick human pass"
        job.ai_confidence = 0.52
        job.status_history = [
            {"timestamp": "2026-05-10T00:00:00Z", "status": "pending", "detail": "Job created", "payload": {}},
            {"timestamp": "2026-05-10T00:00:01Z", "status": "review_needed", "detail": "Manual review required", "payload": {}},
        ]
        await session.commit()

    list_response = await authorized_client.get("/api/grading/jobs?status=review_needed")
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()

    review_response = await authorized_client.post(
        f"/api/grading/review/{list_response.json()[0]['id']}",
        json={
            "action": "modify",
            "score": 91,
            "feedback": "Adjusted after review",
            "notes": "OCR dropped a symbol",
            "override_reason": "Parent confirmed the answer",
        },
    )
    assert review_response.status_code == 200, review_response.text
    payload = review_response.json()
    assert payload["status"] == "final"
    assert payload["human_override_details"]["final_score"] == 91

    async with AsyncSessionLocal() as session:
        audit_events = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.target_entity_type.in_(["answer_key", "grading_job"])).order_by(AuditEvent.id)
            )
        ).scalars().all()
    assert any(event.target_entity_type == "answer_key" for event in audit_events)
    assert any(event.target_entity_type == "grading_job" for event in audit_events)
