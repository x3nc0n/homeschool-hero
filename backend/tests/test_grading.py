from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models import Grade, GradedBy, GradingJob, GradingJobStatus, Notification, NotificationType


async def _seed_review_job(submission_id: int, *, ai_grade: float = 84, confidence: float = 0.41) -> int:
    async with AsyncSessionLocal() as session:
        job = (await session.execute(select(GradingJob).where(GradingJob.submission_id == submission_id))).scalar_one()
        job.status = GradingJobStatus.review_needed
        job.ai_grade = ai_grade
        job.ai_feedback = 'Needs manual confirmation'
        job.ai_confidence = confidence
        job.status_history = [
            {'timestamp': '2026-05-10T00:00:00Z', 'status': 'pending', 'detail': 'Job created', 'payload': {}},
            {'timestamp': '2026-05-10T00:00:01Z', 'status': 'review_needed', 'detail': 'Routed for manual review', 'payload': {}},
        ]
        await session.commit()
        return job.id


@pytest.mark.asyncio
async def test_grading_jobs_listing_and_review_queue_filter(authorized_client, seeded_submission):
    job_id = await _seed_review_job(seeded_submission['id'])

    jobs = await authorized_client.get('/api/grading/jobs')
    assert jobs.status_code == 200, jobs.text
    assert any(item['id'] == job_id for item in jobs.json())

    filtered = await authorized_client.get('/api/grading/jobs', params={'status': 'review_needed'})
    assert filtered.status_code == 200, filtered.text
    assert [item['id'] for item in filtered.json()] == [job_id]

    queue = await authorized_client.get('/api/grading/review-queue')
    assert queue.status_code == 200, queue.text
    assert [item['id'] for item in queue.json()] == [job_id]


@pytest.mark.asyncio
async def test_grading_review_endpoint_approves_and_creates_grade_notification(
    authorized_client,
    seeded_submission,
):
    job_id = await _seed_review_job(seeded_submission['id'], ai_grade=88, confidence=0.38)

    response = await authorized_client.post(
        f'/api/grading/review/{job_id}',
        json={
            'action': 'modify',
            'score': 91,
            'feedback': 'Teacher confirmed final score.',
            'notes': 'One symbol was missing from OCR.',
            'override_reason': 'Manual grading pass',
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['status'] == 'final'
    assert payload['human_override_details']['action'] == 'modify'

    async with AsyncSessionLocal() as session:
        grade = (await session.execute(select(Grade).where(Grade.submission_id == seeded_submission['id']))).scalar_one()
        notifications = (
            await session.execute(
                select(Notification).where(Notification.type == NotificationType.grading_complete).order_by(Notification.id.desc())
            )
        ).scalars().all()

    assert grade.score == 91
    assert grade.graded_by == GradedBy.human
    assert notifications


@pytest.mark.asyncio
async def test_grading_review_queue_approve_and_reject_shortcuts(authorized_client, seeded_submission):
    approve_job_id = await _seed_review_job(seeded_submission['id'], ai_grade=86, confidence=0.33)
    approve = await authorized_client.post(
        f'/api/grading/review-queue/{approve_job_id}/approve',
        json={'score': 87, 'feedback': 'Approved from queue', 'graded_by': 'ai+human'},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()['status'] == 'final'

    second_submission = await authorized_client.post(
        '/api/submissions',
        data={'assignment_id': str(seeded_submission['assignment_id']), 'student_id': str(seeded_submission['student_id'])},
        files={
            'file': (
                'second-review.png',
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0'
                b'\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82',
                'image/png',
            )
        },
    )
    assert second_submission.status_code in {200, 201, 202}, second_submission.text
    reject_job_id = await _seed_review_job(second_submission.json()['id'])

    reject = await authorized_client.post(
        f'/api/grading/review-queue/{reject_job_id}/reject',
        json={'reason': 'Need a fresh OCR pass'},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()['status'] == 'pending'


@pytest.mark.asyncio
async def test_grading_review_queue_is_family_scoped(authorized_client, tertiary_client, create_family_user, seeded_submission):
    job_id = await _seed_review_job(seeded_submission['id'])
    other_family = await create_family_user(
        family_name='Other Family',
        email='other-grading@example.com',
        password='strongpass999',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
    )
    login = await tertiary_client.post(
        '/api/auth/login',
        json={'email': other_family['email'], 'password': other_family['password'], 'family_id': other_family['family_id']},
    )
    assert login.status_code == 200, login.text

    queue = await tertiary_client.get('/api/grading/review-queue')
    assert queue.status_code == 200, queue.text
    assert queue.json() == []

    detail = await tertiary_client.post(
        f'/api/grading/review/{job_id}',
        json={'action': 'approve', 'score': 90, 'feedback': 'Blocked'},
    )
    assert detail.status_code == 404, detail.text
