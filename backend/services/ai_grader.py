from __future__ import annotations

import json
import re
from typing import Any

import httpx

from backend.config import settings

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


class AIServiceUnavailable(RuntimeError):
    """Raised when the configured AI provider is unavailable."""


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_prompt(assignment_description: str, answer_key: str | None, submission_text: str) -> str:
    return (
        "You are grading a student submission.\n"
        "Return ONLY JSON with keys: score, confidence, feedback.\n"
        "score must be 0-100. confidence must be 0.0-1.0.\n\n"
        f"Assignment Description:\n{assignment_description or 'N/A'}\n\n"
        f"Answer Key:\n{answer_key or 'N/A'}\n\n"
        f"Student Submission OCR Text:\n{submission_text or 'N/A'}\n"
    )


def _extract_json_block(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    try:
        payload = json.loads(stripped)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced_match:
        try:
            payload = json.loads(fenced_match.group(1))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            pass

    object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if object_match:
        try:
            payload = json.loads(object_match.group(0))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _parse_freeform_response(text: str) -> dict[str, Any]:
    score_match = re.search(r"score\s*[:=-]\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    confidence_match = re.search(r"confidence\s*[:=-]\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    feedback_match = re.search(r"feedback\s*[:=-]\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)

    score = _to_float(score_match.group(1), 0.0) if score_match else 0.0
    confidence = _to_float(confidence_match.group(1), 0.0) if confidence_match else 0.0
    if confidence > 1.0:
        confidence = confidence / 100.0
    feedback = feedback_match.group(1).strip() if feedback_match else text.strip()

    return {"score": score, "confidence": confidence, "feedback": feedback}


def _normalize_result(payload: dict[str, Any], fallback_feedback: str = "") -> dict[str, Any]:
    score = _clamp(_to_float(payload.get("score"), 0.0), 0.0, 100.0)
    confidence = _to_float(payload.get("confidence"), 0.0)
    if confidence > 1.0:
        confidence = confidence / 100.0
    confidence = _clamp(confidence, 0.0, 1.0)
    feedback = str(payload.get("feedback") or fallback_feedback or "").strip()
    return {"score": score, "max_score": 100, "confidence": confidence, "feedback": feedback}


def _parse_model_response_text(text: str) -> dict[str, Any]:
    parsed_json = _extract_json_block(text)
    if parsed_json:
        return _normalize_result(parsed_json, fallback_feedback=text)
    return _normalize_result(_parse_freeform_response(text), fallback_feedback=text)


def _call_ollama(prompt: str) -> dict[str, Any]:
    url = f"{settings.ollama_host.rstrip('/')}/api/generate"
    payload = {"model": settings.ollama_model, "prompt": prompt, "stream": False}
    try:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
        body = response.json()
        text = str(body.get("response", "")).strip()
        if not text:
            raise AIServiceUnavailable("Ollama returned an empty response")
        return _parse_model_response_text(text)
    except (httpx.HTTPError, ValueError) as exc:
        raise AIServiceUnavailable(f"Ollama unavailable: {exc}") from exc


def _call_openai(prompt: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise AIServiceUnavailable("OPENAI_API_KEY is not configured")
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You are a strict grading assistant. Return only JSON."},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    try:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(OPENAI_CHAT_URL, headers=headers, json=payload)
            response.raise_for_status()
        body = response.json()
        text = str(body["choices"][0]["message"]["content"]).strip()
        if not text:
            raise AIServiceUnavailable("OpenAI returned an empty response")
        return _parse_model_response_text(text)
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        raise AIServiceUnavailable(f"OpenAI unavailable: {exc}") from exc


def _call_model(*_: Any, **kwargs: Any) -> dict[str, Any]:
    prompt = _build_prompt(
        assignment_description=str(kwargs.get("assignment_description", "")),
        answer_key=kwargs.get("answer_key"),
        submission_text=str(kwargs.get("submission_text", "")),
    )
    provider = settings.ai_provider.lower().strip()
    if provider == "openai":
        return _call_openai(prompt)
    return _call_ollama(prompt)


def grade_submission_text(assignment_description: str, answer_key: str | None, submission_text: str) -> dict[str, Any]:
    try:
        payload = _call_model(
            assignment_description=assignment_description,
            answer_key=answer_key,
            submission_text=submission_text,
        )
        normalized = _normalize_result(payload)
        normalized["unavailable"] = False
        return normalized
    except AIServiceUnavailable:
        return {
            "score": 0.0,
            "max_score": 100,
            "confidence": 0.0,
            "feedback": "AI grading unavailable; manual review required.",
            "unavailable": True,
        }


def grade_submission(assignment_description: str, answer_key: str | None = None, submission_text: str = "") -> dict[str, Any]:
    return grade_submission_text(assignment_description, answer_key, submission_text)
