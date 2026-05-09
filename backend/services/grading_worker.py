from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import (
    AnswerKey,
    Assignment,
    AssignmentTarget,
    AssignmentTargetStatus,
    AuditAction,
    Grade,
    GradedBy,
    GradingJob,
    GradingJobStatus,
    Student,
    Submission,
)
from backend.services.ai_grader import grade_submission_text
from backend.services.audit import log_event
from backend.services.capabilities import get_capability_registry
from backend.services.grading_pipeline import (
    ai_circuit_breaker,
    compare_answer_key,
    ensure_initial_history,
    retry_with_backoff,
    serialize_prompt_answer_key,
    system_actor,
    transition_job,
)
from backend.services.logging_config import log_action
from backend.services.notifications import create_grading_complete_notifications, run_notification_maintenance
from backend.services.ocr import extract_text

logger = logging.getLogger(__name__)
NOTIFICATION_MAINTENANCE_INTERVAL = max(settings.grading_poll_interval, 900.0)


def _to_letter_grade(score: float) -> str:
    if score >= 90:
        return 'A'
    if score >= 80:
        return 'B'
    if score >= 70:
        return 'C'
    if score >= 60:
        return 'D'
    return 'F'


def _job_snapshot(job: GradingJob) -> dict[str, Any]:
    return {
        'id': job.id,
        'submission_id': job.submission_id,
        'status': job.status.value,
        'ocr_result': job.ocr_result,
        'ai_grade': job.ai_grade,
        'ai_feedback': job.ai_feedback,
        'ai_confidence': job.ai_confidence,
        'manual_review_reason': job.manual_review_reason,
        'human_override_details': job.human_override_details,
        'answer_key_result': job.answer_key_result,
        'status_history': job.status_history,
        'ocr_retry_count': job.ocr_retry_count,
        'ai_retry_count': job.ai_retry_count,
    }


async def _audit_new_history(
    db,
    *,
    job: GradingJob,
    previous_history: list[dict[str, Any]],
) -> None:
    prior_steps = len(previous_history)
    if len(job.status_history) <= prior_steps:
        return
    for index, step in enumerate(job.status_history[prior_steps:], start=prior_steps):
        before = previous_history[index - 1] if index > 0 and index - 1 < len(previous_history) else None
        await log_event(
            db,
            action=AuditAction.grade_update,
            actor=system_actor(job.created_by_user_id),
            family_id=job.family_id,
            target_type='grading_job',
            target_id=job.id,
            before=before,
            after={
                'step': step,
                'ocr_result': job.ocr_result,
                'ai_response': job.ai_response,
                'answer_key_result': job.answer_key_result,
                'ai_confidence': job.ai_confidence,
                'manual_review_reason': job.manual_review_reason,
            },
            request=None,
        )


def _combine_feedback(ai_feedback: str, answer_key_result: dict[str, Any] | None) -> str:
    if not answer_key_result:
        return ai_feedback
    answered = answer_key_result.get('answered_questions', 0)
    total = answer_key_result.get('total_questions', 0)
    summary = f'Answer key matched {answered}/{total} question(s).'
    return f'{summary}\n\n{ai_feedback}'.strip()


def _manual_review(
    output: dict[str, Any],
    *,
    reason: str,
    detail: str,
) -> dict[str, Any]:
    transition_job(output, GradingJobStatus.review_needed, detail=detail, payload={'reason': reason})
    output['manual_review_reason'] = reason
    output['error_message'] = reason
    output['completed_at'] = datetime.now(timezone.utc).isoformat()
    return output


def process_grading_job(job: dict[str, Any]) -> dict[str, Any]:
    output = {**job}
    ensure_initial_history(output)
    if output.get('status') != GradingJobStatus.pending.value:
        output['status'] = GradingJobStatus.pending.value

    capabilities = get_capability_registry().check_all_sync()
    transition_job(output, GradingJobStatus.ocr_processing, detail='OCR processing started')
    if not capabilities['ocr']['enabled']:
        return _manual_review(
            output,
            reason=f"OCR unavailable; manual review required. {capabilities['ocr']['reason']}",
            detail='OCR unavailable',
        )

    try:
        extracted, ocr_retries = retry_with_backoff(
            lambda: extract_text(str(output.get('file_path', ''))),
            attempts=max(1, settings.grading_retry_attempts),
            base_delay_seconds=max(0.0, settings.grading_retry_backoff_seconds),
            timeout_seconds=settings.ocr_request_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        return _manual_review(output, reason=f'OCR failed after retries: {exc}', detail='OCR failed')

    output['ocr_retry_count'] = ocr_retries
    output['ocr_result'] = extracted if isinstance(extracted, str) else ''
    transition_job(
        output,
        GradingJobStatus.ocr_complete,
        detail='OCR completed',
        payload={'ocr_text_length': len(output['ocr_result'])},
    )

    answer_key_result = compare_answer_key(output.get('answer_key_questions'), output['ocr_result'])
    output['answer_key_result'] = answer_key_result

    transition_job(output, GradingJobStatus.ai_grading, detail='AI grading started')
    if ai_circuit_breaker.is_open():
        return _manual_review(output, reason='AI circuit breaker is open; manual review required.', detail='AI circuit open')
    if not capabilities['ai_grading']['enabled']:
        return _manual_review(
            output,
            reason=f"AI grading unavailable; manual review required. {capabilities['ai_grading']['reason']}",
            detail='AI capability unavailable',
        )

    try:
        ai_result, ai_retries = retry_with_backoff(
            lambda: grade_submission_text(
                assignment_description=str(output.get('assignment_description', '')),
                answer_key=serialize_prompt_answer_key(output.get('answer_key_questions')),
                submission_text=output['ocr_result'],
            ),
            attempts=max(1, settings.grading_retry_attempts),
            base_delay_seconds=max(0.0, settings.grading_retry_backoff_seconds),
            timeout_seconds=settings.grading_request_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        ai_circuit_breaker.record_failure()
        return _manual_review(output, reason=f'AI grading failed after retries: {exc}', detail='AI grading failed')

    output['ai_retry_count'] = ai_retries
    if ai_result.get('unavailable'):
        ai_circuit_breaker.record_failure()
        return _manual_review(
            output,
            reason=str(ai_result.get('error_message') or ai_result.get('feedback') or 'AI grading unavailable'),
            detail='AI provider unavailable',
        )
    ai_circuit_breaker.record_success()

    ai_confidence = float(ai_result.get('confidence', 0.0))
    answer_key_confidence = float(answer_key_result.get('confidence', 0.0)) if answer_key_result else None
    combined_confidence = (
        round((answer_key_confidence * 0.65) + (ai_confidence * 0.35), 3)
        if answer_key_confidence is not None
        else ai_confidence
    )
    output['ai_response'] = str(ai_result.get('raw_response') or '')
    output['ai_confidence'] = combined_confidence
    output['score'] = float(answer_key_result.get('score') if answer_key_result else ai_result.get('score', 0.0))
    output['max_score'] = float(answer_key_result.get('max_score') if answer_key_result else ai_result.get('max_score', 100.0))
    output['feedback'] = _combine_feedback(str(ai_result.get('feedback', '')), answer_key_result)
    output['ai_feedback'] = output['feedback']
    transition_job(
        output,
        GradingJobStatus.ai_complete,
        detail='AI grading completed',
        payload={'confidence': combined_confidence, 'score': output['score'], 'max_score': output['max_score']},
    )

    if combined_confidence >= settings.confidence_threshold:
        transition_job(output, GradingJobStatus.final, detail='Auto-graded successfully')
        output['status'] = GradingJobStatus.final.value
        output['completed_at'] = datetime.now(timezone.utc).isoformat()
        output['manual_review_reason'] = None
        return output

    return _manual_review(
        output,
        reason='Confidence below threshold; human review required.',
        detail='Low-confidence grading result',
    )


def process_job(job: dict[str, Any]) -> dict[str, Any]:
    return process_grading_job(job)


def handle_job(job: dict[str, Any]) -> dict[str, Any]:
    return process_grading_job(job)


async def _claim_next_job() -> int | None:
    async with AsyncSessionLocal() as db:
        job = (
            await db.execute(select(GradingJob).where(GradingJob.status == GradingJobStatus.pending).order_by(GradingJob.created_at).limit(1))
        ).scalar_one_or_none()
        if not job:
            return None
        await db.commit()
        return job.id


async def _finalize_manual_review(job: GradingJob, reason: str) -> None:
    job.manual_review_reason = reason
    job.completed_at = datetime.now(timezone.utc)


async def process_queued_job_once() -> bool:
    job_id = await _claim_next_job()
    if job_id is None:
        return False

    try:
        async with AsyncSessionLocal() as db:
            job = (
                await db.execute(
                    select(GradingJob)
                    .options(selectinload(GradingJob.submission).selectinload(Submission.assignment))
                    .where(GradingJob.id == job_id)
                )
            ).scalar_one_or_none()
            if not job:
                return False
            previous_history = list(job.status_history or [])
            previous_snapshot = _job_snapshot(job)
            submission = job.submission
            if not submission:
                transition_job(job, GradingJobStatus.review_needed, detail='Submission not found')
                await _finalize_manual_review(job, 'Submission not found')
                await _audit_new_history(db, job=job, previous_history=previous_history)
                await db.commit()
                return True
            if not submission.is_current:
                transition_job(job, GradingJobStatus.final, detail='Submission superseded by newer version')
                job.manual_review_reason = 'Submission superseded by a newer version.'
                job.error_message = job.manual_review_reason
                job.completed_at = datetime.now(timezone.utc)
                await _audit_new_history(db, job=job, previous_history=previous_history)
                await db.commit()
                return True

            assignment = submission.assignment or await db.get(Assignment, submission.assignment_id)
            student = await db.get(Student, submission.student_id)
            answer_key = (
                await db.execute(select(AnswerKey).where(AnswerKey.assignment_id == submission.assignment_id).limit(1))
            ).scalar_one_or_none()
            job_result = process_grading_job(
                {
                    'id': job.id,
                    'family_id': job.family_id,
                    'submission_id': submission.id,
                    'file_path': submission.file_path,
                    'assignment_description': assignment.description if assignment else '',
                    'answer_key_questions': answer_key.questions if answer_key else [],
                    'status': job.status.value,
                    'status_history': previous_history,
                }
            )

            submission.ocr_text = str(job_result.get('ocr_result') or '')
            job.status = GradingJobStatus(job_result['status'])
            job.ocr_result = submission.ocr_text
            job.ai_grade = float(job_result.get('score', 0.0))
            job.ai_feedback = str(job_result.get('feedback') or '')
            job.ai_confidence = float(job_result.get('ai_confidence', 0.0))
            job.ai_response = str(job_result.get('ai_response') or '')
            job.answer_key_result = job_result.get('answer_key_result')
            job.status_history = list(job_result.get('status_history') or [])
            job.manual_review_reason = job_result.get('manual_review_reason')
            job.human_override_details = job.human_override_details
            job.ocr_retry_count = int(job_result.get('ocr_retry_count', 0))
            job.ai_retry_count = int(job_result.get('ai_retry_count', 0))
            job.error_message = job_result.get('error_message')
            job.completed_at = datetime.now(timezone.utc)

            if job.status == GradingJobStatus.final:
                grade = (
                    await db.execute(
                        select(Grade).where(Grade.family_id == submission.family_id, Grade.submission_id == submission.id).limit(1)
                    )
                ).scalar_one_or_none()
                score = float(job_result.get('score', 0.0))
                max_score = float(job_result.get('max_score', 100.0))
                feedback = str(job_result.get('feedback', ''))
                confidence = float(job_result.get('ai_confidence', 0.0))
                if grade is None:
                    grade = Grade(
                        family_id=submission.family_id,
                        submission_id=submission.id,
                        student_id=submission.student_id,
                        score=score,
                        max_score=max_score,
                        letter_grade=_to_letter_grade(score),
                        notes=feedback,
                        graded_by=GradedBy.ai,
                        ai_confidence=confidence,
                    )
                    db.add(grade)
                else:
                    grade.score = score
                    grade.max_score = max_score
                    grade.letter_grade = _to_letter_grade(score)
                    grade.notes = feedback
                    grade.graded_by = GradedBy.ai
                    grade.ai_confidence = confidence
                assignment_target = (
                    await db.execute(
                        select(AssignmentTarget).where(
                            AssignmentTarget.assignment_id == submission.assignment_id,
                            AssignmentTarget.student_id == submission.student_id,
                        )
                    )
                ).scalar_one_or_none()
                if assignment_target:
                    assignment_target.status = AssignmentTargetStatus.graded
                await create_grading_complete_notifications(
                    db,
                    family_id=submission.family_id,
                    assignment_title=assignment.title if assignment else 'Assignment',
                    student_name=student.name if student else 'Student',
                    score=score,
                    max_score=max_score,
                )
            elif job.status == GradingJobStatus.review_needed:
                await create_grading_complete_notifications(
                    db,
                    family_id=submission.family_id,
                    assignment_title=assignment.title if assignment else 'Assignment',
                    student_name=student.name if student else 'Student',
                    score=None,
                    max_score=None,
                    needs_review=True,
                )

            await _audit_new_history(db, job=job, previous_history=previous_history)
            if previous_snapshot != _job_snapshot(job):
                await log_event(
                    db,
                    action=AuditAction.grade_update,
                    actor=system_actor(job.created_by_user_id),
                    family_id=job.family_id,
                    target_type='grading_job',
                    target_id=job.id,
                    before=previous_snapshot,
                    after=_job_snapshot(job),
                    request=None,
                )
            await db.commit()
            return True
    except Exception as exc:  # noqa: BLE001
        logger.exception('Failed processing grading job %s', job_id)
        async with AsyncSessionLocal() as db:
            job = await db.get(GradingJob, job_id)
            if job:
                previous_history = list(job.status_history or [])
                try:
                    transition_job(job, GradingJobStatus.review_needed, detail='Worker failure', payload={'error': str(exc)})
                except Exception:  # noqa: BLE001
                    pass
                job.manual_review_reason = str(exc)
                job.error_message = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                await _audit_new_history(db, job=job, previous_history=previous_history)
                await db.commit()
        return True


async def _worker_loop(stop_event: threading.Event) -> None:
    last_maintenance = 0.0
    while not stop_event.is_set():
        processed = await process_queued_job_once()
        now = time.monotonic()
        if now - last_maintenance >= NOTIFICATION_MAINTENANCE_INTERVAL:
            async with AsyncSessionLocal() as db:
                await run_notification_maintenance(db)
                await db.commit()
            last_maintenance = now
        if processed:
            await asyncio.sleep(0)
        else:
            await asyncio.sleep(settings.grading_poll_interval)


class GradingWorkerThread:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name='grading-worker', daemon=True)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                asyncio.run(_worker_loop(self._stop_event))
            except Exception:
                logger.exception('Grading worker loop crashed; retrying shortly.')
                time.sleep(1)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=timeout)


def create_worker() -> GradingWorkerThread:
    return GradingWorkerThread()
