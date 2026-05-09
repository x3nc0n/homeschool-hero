from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from types import SimpleNamespace
from typing import Any, Callable

from backend.config import settings
from backend.models import GradingJob, GradingJobStatus

_ALLOWED_TRANSITIONS: dict[GradingJobStatus, set[GradingJobStatus]] = {
    GradingJobStatus.pending: {GradingJobStatus.ocr_processing, GradingJobStatus.review_needed, GradingJobStatus.final},
    GradingJobStatus.ocr_processing: {GradingJobStatus.ocr_complete, GradingJobStatus.review_needed, GradingJobStatus.final},
    GradingJobStatus.ocr_complete: {GradingJobStatus.ai_grading, GradingJobStatus.review_needed, GradingJobStatus.final},
    GradingJobStatus.ai_grading: {GradingJobStatus.ai_complete, GradingJobStatus.review_needed},
    GradingJobStatus.ai_complete: {GradingJobStatus.review_needed, GradingJobStatus.final},
    GradingJobStatus.review_needed: {GradingJobStatus.pending, GradingJobStatus.reviewed},
    GradingJobStatus.reviewed: {GradingJobStatus.final},
    GradingJobStatus.final: {GradingJobStatus.pending},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_transition(current: GradingJobStatus, nxt: GradingJobStatus) -> None:
    if nxt not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f'Invalid grading status transition from {current.value} to {nxt.value}')


def append_status_history(
    job: GradingJob | dict[str, Any],
    status: GradingJobStatus,
    *,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    history = getattr(job, 'status_history', None)
    if history is None:
        history = []
        if isinstance(job, dict):
            job['status_history'] = history
        else:
            job.status_history = history
    history.append({'timestamp': now_iso(), 'status': status.value, 'detail': detail, 'payload': payload or {}})


def transition_job(
    job: GradingJob | dict[str, Any],
    nxt: GradingJobStatus,
    *,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    current = job['status'] if isinstance(job, dict) else job.status
    if isinstance(current, str):
        current = GradingJobStatus(current)
    validate_transition(current, nxt)
    if isinstance(job, dict):
        job['status'] = nxt.value
    else:
        job.status = nxt
    append_status_history(job, nxt, detail=detail, payload=payload)


def ensure_initial_history(job: GradingJob | dict[str, Any]) -> None:
    status = job['status'] if isinstance(job, dict) else job.status
    if isinstance(status, str):
        status = GradingJobStatus(status)
    history = getattr(job, 'status_history', None) if not isinstance(job, dict) else job.get('status_history')
    if not history:
        append_status_history(job, status, detail='Job created')


def serialize_prompt_answer_key(questions: list[dict[str, Any]] | None) -> str | None:
    if not questions:
        return None
    lines = []
    for question in questions:
        lines.append(
            f"{question.get('question_number')}) answer={question.get('correct_answer')} "
            f"points={question.get('points', 0)} partial={question.get('partial_credit_rules') or 'none'}"
        )
    return '\n'.join(lines)


def _normalize_answer(value: str | None) -> str:
    if not value:
        return ''
    return ''.join(char.lower() for char in value.strip() if char.isalnum())


def _extract_answer_lines(submission_text: str) -> dict[str, str]:
    answers: dict[str, str] = {}
    for raw_line in submission_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ')' in line:
            prefix, remainder = line.split(')', 1)
        elif ':' in line:
            prefix, remainder = line.split(':', 1)
        elif '.' in line:
            prefix, remainder = line.split('.', 1)
        else:
            continue
        key = prefix.strip().lstrip('#').lower()
        if key:
            answers[key] = remainder.strip()
    return answers


def _partial_credit(points: float, actual: str, expected: str, rules: str | None) -> float:
    similarity = SequenceMatcher(None, _normalize_answer(actual), _normalize_answer(expected)).ratio()
    if rules:
        digits = ''.join(ch for ch in rules if ch.isdigit() or ch == '.')
        if digits:
            try:
                parsed = float(digits)
                if '%' in rules:
                    return round(points * max(0.0, min(parsed / 100.0, 1.0)), 2)
                if parsed <= 1:
                    return round(points * parsed, 2)
                return round(min(parsed, points), 2)
            except ValueError:
                pass
    if similarity >= 0.85:
        return round(points * 0.75, 2)
    if similarity >= 0.65:
        return round(points * 0.5, 2)
    return 0.0


def compare_answer_key(questions: list[dict[str, Any]] | None, submission_text: str) -> dict[str, Any] | None:
    if not questions:
        return None
    answers = _extract_answer_lines(submission_text)
    comparisons: list[dict[str, Any]] = []
    total_points = 0.0
    awarded_points = 0.0
    exact_matches = 0
    answered_questions = 0
    for raw_question in questions:
        question_number = str(raw_question.get('question_number', '')).strip()
        expected = str(raw_question.get('correct_answer', '')).strip()
        points = float(raw_question.get('points') or 0.0)
        rules = raw_question.get('partial_credit_rules')
        total_points += points
        actual = answers.get(question_number.lower(), '')
        if actual:
            answered_questions += 1
        normalized_actual = _normalize_answer(actual)
        normalized_expected = _normalize_answer(expected)
        is_correct = bool(normalized_actual and normalized_actual == normalized_expected)
        if is_correct:
            awarded = points
            exact_matches += 1
        else:
            awarded = _partial_credit(points, actual, expected, str(rules) if rules else None) if actual else 0.0
        similarity = SequenceMatcher(None, normalized_actual, normalized_expected).ratio() if actual else 0.0
        awarded_points += awarded
        comparisons.append(
            {
                'question_number': question_number,
                'correct_answer': expected,
                'student_answer': actual or None,
                'points': points,
                'awarded_points': awarded,
                'is_correct': is_correct,
                'partial_credit_rules': rules,
                'similarity': round(similarity, 3),
            }
        )

    coverage = answered_questions / len(questions) if questions else 0.0
    accuracy = exact_matches / len(questions) if questions else 0.0
    confidence = max(0.0, min((coverage * 0.45) + (accuracy * 0.55), 1.0))
    if any(item['student_answer'] is None for item in comparisons):
        confidence = max(0.0, confidence - 0.1)
    return {
        'questions': comparisons,
        'score': round(awarded_points, 2),
        'max_score': round(total_points, 2),
        'confidence': round(confidence, 3),
        'answered_questions': answered_questions,
        'total_questions': len(questions),
    }


class RetryableGradingError(RuntimeError):
    pass


def run_with_timeout(operation: Callable[[], Any], *, timeout_seconds: float) -> Any:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(operation)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError(f'Operation timed out after {timeout_seconds:.0f}s') from exc


def retry_with_backoff(
    operation: Callable[[], Any],
    *,
    attempts: int,
    base_delay_seconds: float,
    timeout_seconds: float,
) -> tuple[Any, int]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return run_with_timeout(operation, timeout_seconds=timeout_seconds), attempt - 1
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= attempts:
                break
            time.sleep(base_delay_seconds * (2 ** (attempt - 1)))
    raise RetryableGradingError(str(last_error) if last_error else 'Operation failed')


@dataclass
class CircuitState:
    consecutive_failures: int = 0
    opened_at: float | None = None


class AICircuitBreaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = CircuitState()

    def is_open(self) -> bool:
        with self._lock:
            if self._state.opened_at is None:
                return False
            if time.monotonic() - self._state.opened_at >= settings.ai_circuit_breaker_reset_seconds:
                self._state = CircuitState()
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._state = CircuitState()

    def record_failure(self) -> None:
        with self._lock:
            self._state.consecutive_failures += 1
            if self._state.consecutive_failures >= settings.ai_circuit_breaker_threshold:
                self._state.opened_at = time.monotonic()


ai_circuit_breaker = AICircuitBreaker()


def system_actor(user_id: int) -> Any:
    return SimpleNamespace(id=user_id)
