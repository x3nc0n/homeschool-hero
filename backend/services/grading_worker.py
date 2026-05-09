from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import Assignment, Grade, GradedBy, GradingJob, GradingJobStatus, Submission
from backend.services.ai_grader import grade_submission_text
from backend.services.capabilities import get_capability_registry
from backend.services.logging_config import log_action
from backend.services.ocr import extract_text

logger = logging.getLogger(__name__)


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


def process_grading_job(job: dict[str, Any]) -> dict[str, Any]:
    output = {**job}
    start_time = time.perf_counter()
    try:
        capabilities = get_capability_registry().check_all_sync()
        ocr_capability = capabilities['ocr']
        if not ocr_capability['enabled']:
            message = f"OCR unavailable; text extraction skipped. {ocr_capability['reason']}"
            log_action(
                logger,
                logging.WARNING,
                'Submission routed to manual review because OCR is unavailable',
                action='grading_job_failed',
                family_id=job.get('family_id'),
                details={
                    'job_id': job.get('id'),
                    'submission_id': job.get('submission_id'),
                    'reason': message,
                    'duration_ms': round((time.perf_counter() - start_time) * 1000, 2),
                },
            )
            output.update(
                {
                    'ocr_result': '',
                    'status': 'needs_review',
                    'feedback': 'OCR unavailable; manual review required.',
                    'error_message': message,
                    'ai_confidence': 0.0,
                }
            )
            return output

        extracted = extract_text(str(job.get('file_path', '')))
        output['ocr_result'] = extracted

        ai_capability = capabilities['ai_grading']
        if not ai_capability['enabled']:
            message = f"AI grading unavailable; routed to manual review. {ai_capability['reason']}"
            log_action(
                logger,
                logging.WARNING,
                'Submission routed to manual review because AI grading is unavailable',
                action='grading_job_failed',
                family_id=job.get('family_id'),
                details={
                    'job_id': job.get('id'),
                    'submission_id': job.get('submission_id'),
                    'reason': message,
                    'duration_ms': round((time.perf_counter() - start_time) * 1000, 2),
                },
            )
            output.update(
                {
                    'status': 'needs_review',
                    'feedback': 'AI grading unavailable; manual review required.',
                    'error_message': message,
                    'ai_confidence': 0.0,
                    'unavailable': True,
                }
            )
            return output

        ai = grade_submission_text(
            assignment_description=str(job.get('assignment_description', '')),
            answer_key=job.get('answer_key'),
            submission_text=extracted,
        )
    except Exception as exc:
        log_action(
            logger,
            logging.WARNING,
            'Submission routed to manual review after grading error',
            action='grading_job_failed',
            family_id=job.get('family_id'),
            details={
                'job_id': job.get('id'),
                'submission_id': job.get('submission_id'),
                'reason': str(exc),
                'duration_ms': round((time.perf_counter() - start_time) * 1000, 2),
            },
        )
        output.update({'status': 'needs_review', 'error_message': str(exc), 'ai_confidence': 0.0})
        return output

    confidence = float(ai.get('confidence', 0.0))
    output['ai_confidence'] = confidence
    output['score'] = float(ai.get('score', 0.0))
    output['max_score'] = float(ai.get('max_score', 100.0))
    output['feedback'] = str(ai.get('feedback', ''))
    output['unavailable'] = bool(ai.get('unavailable', False))
    if output['unavailable']:
        log_action(
            logger,
            logging.WARNING,
            'Submission routed to manual review because AI grading became unavailable',
            action='grading_job_failed',
            family_id=job.get('family_id'),
            details={
                'job_id': job.get('id'),
                'submission_id': job.get('submission_id'),
                'reason': ai.get('error_message') or output['feedback'],
                'duration_ms': round((time.perf_counter() - start_time) * 1000, 2),
            },
        )
        output['error_message'] = str(ai.get('error_message') or output.get('error_message') or output['feedback'])
        output['status'] = 'needs_review'
        return output
    output['status'] = 'complete' if confidence >= settings.confidence_threshold else 'needs_review'
    if output['status'] == 'needs_review':
        log_action(
            logger,
            logging.INFO,
            'Submission routed to manual review because confidence is below threshold',
            action='grading_job_completed',
            family_id=job.get('family_id'),
            details={
                'job_id': job.get('id'),
                'submission_id': job.get('submission_id'),
                'confidence': confidence,
                'threshold': settings.confidence_threshold,
                'duration_ms': round((time.perf_counter() - start_time) * 1000, 2),
            },
        )
    else:
        log_action(
            logger,
            logging.INFO,
            'Grading job completed automatically',
            action='grading_job_completed',
            family_id=job.get('family_id'),
            details={
                'job_id': job.get('id'),
                'submission_id': job.get('submission_id'),
                'score': output['score'],
                'confidence': confidence,
                'duration_ms': round((time.perf_counter() - start_time) * 1000, 2),
            },
        )
    return output


def process_job(job: dict[str, Any]) -> dict[str, Any]:
    return process_grading_job(job)


def handle_job(job: dict[str, Any]) -> dict[str, Any]:
    return process_grading_job(job)


async def _claim_next_job() -> int | None:
    async with AsyncSessionLocal() as db:
        job = (
            await db.execute(
                select(GradingJob).where(GradingJob.status == GradingJobStatus.queued).order_by(GradingJob.created_at).limit(1)
            )
        ).scalar_one_or_none()
        if not job:
            return None
        job.status = GradingJobStatus.processing
        job.error_message = None
        await db.commit()
        log_action(
            logger,
            logging.INFO,
            'Claimed grading job for processing',
            action='grading_job_processing',
            family_id=job.family_id,
            details={'job_id': job.id, 'submission_id': job.submission_id},
        )
        return job.id


async def _finalize_failed(job_id: int, error_message: str) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(GradingJob, job_id)
        if not job:
            return
        job.status = GradingJobStatus.failed
        job.error_message = error_message[:2000]
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        duration_ms = None
        if job.completed_at and job.created_at:
            duration_ms = round((job.completed_at - job.created_at).total_seconds() * 1000, 2)
        log_action(
            logger,
            logging.ERROR,
            'Grading job failed',
            action='grading_job_failed',
            family_id=job.family_id,
            details={
                'job_id': job.id,
                'submission_id': job.submission_id,
                'reason': job.error_message,
                'duration_ms': duration_ms,
            },
        )


async def process_queued_job_once() -> bool:
    job_id = await _claim_next_job()
    if job_id is None:
        return False

    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(GradingJob, job_id)
            if not job:
                return False
            submission = await db.get(Submission, job.submission_id)
            if not submission:
                job.status = GradingJobStatus.failed
                job.error_message = 'Submission not found'
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return True
            assignment = await db.get(Assignment, submission.assignment_id)
            job_result = process_grading_job(
                {
                    'id': job.id,
                    'family_id': job.family_id,
                    'submission_id': submission.id,
                    'file_path': submission.file_path,
                    'assignment_description': assignment.description if assignment else '',
                    'answer_key': None,
                    'status': job.status.value,
                }
            )

            ocr_result = job_result.get('ocr_result', '')
            submission.ocr_text = ocr_result if isinstance(ocr_result, str) else ''
            job.ocr_result = submission.ocr_text
            job.ai_grade = float(job_result.get('score', 0.0))
            job.ai_feedback = str(job_result.get('feedback', ''))
            job.ai_confidence = float(job_result.get('ai_confidence', 0.0))
            job.error_message = job_result.get('error_message')
            job.completed_at = datetime.now(timezone.utc)

            if job_result.get('status') == 'complete':
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
                job.status = GradingJobStatus.complete
            elif job_result.get('status') == 'needs_review':
                job.status = GradingJobStatus.needs_review
            else:
                job.status = GradingJobStatus.failed
                job.error_message = 'Unexpected grading status'

            await db.commit()
            return True
    except Exception as exc:
        logger.exception('Failed processing grading job %s', job_id)
        await _finalize_failed(job_id, str(exc))
        return True


async def _worker_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        processed = await process_queued_job_once()
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
