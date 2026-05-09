from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models import AuditEvent, Grade, GradingJob, GradingJobStatus, Notification, NotificationType, ReviewItem
from backend.services.grading_worker import process_queued_job_once
from backend.services.reviews import sync_review_item_for_job
from tests.contracts import AUTH
from tests.helpers import sync_csrf_header


async def _login(client, *, email: str, password: str) -> None:
    response = await client.post(AUTH['login'], json={'email': email, 'password': password})
    assert response.status_code == 200, response.text
    sync_csrf_header(client)


async def _seed_review_item(submission_id: int, *, confidence: float = 0.42) -> int:
    async with AsyncSessionLocal() as session:
        job = (await session.execute(select(GradingJob).where(GradingJob.submission_id == submission_id))).scalar_one()
        job.status = GradingJobStatus.review_needed
        job.ai_grade = 84
        job.ai_feedback = 'Needs a manual pass'
        job.ai_confidence = confidence
        job.manual_review_reason = 'Confidence below threshold; human review required.'
        job.status_history = [
            {'timestamp': '2026-05-10T00:00:00Z', 'status': 'pending', 'detail': 'Job created', 'payload': {}},
            {'timestamp': '2026-05-10T00:00:01Z', 'status': 'review_needed', 'detail': 'Low-confidence grading result', 'payload': {}},
        ]
        item = await sync_review_item_for_job(session, job)
        assert item is not None
        await session.commit()
        return item.id


def _mock_capabilities():
    return {
        'ai_grading': {'name': 'ai_grading', 'enabled': True, 'reason': 'ok'},
        'email': {'name': 'email', 'enabled': False, 'reason': 'disabled'},
        'backup': {'name': 'backup', 'enabled': False, 'reason': 'disabled'},
        'ocr': {'name': 'ocr', 'enabled': True, 'reason': 'ok'},
    }


@pytest.mark.asyncio
async def test_low_confidence_grading_creates_review_item_and_notifications(authorized_client, seeded_submission, monkeypatch):
    import backend.services.grading_worker as grading_worker

    monkeypatch.setattr(grading_worker, 'extract_text', lambda *_args, **_kwargs: 'unclear work', raising=False)
    monkeypatch.setattr(
        grading_worker,
        'grade_submission_text',
        lambda *_args, **_kwargs: {'score': 74, 'max_score': 100, 'confidence': 0.31, 'feedback': 'Review this'},
        raising=False,
    )
    monkeypatch.setattr(grading_worker.get_capability_registry(), 'check_all_sync', _mock_capabilities, raising=False)

    processed = await process_queued_job_once()
    assert processed is True

    response = await authorized_client.get('/api/reviews?status=pending_review')
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]['submission_id'] == seeded_submission['id']
    assert payload[0]['status'] == 'pending_review'
    assert payload[0]['ai_confidence'] < 0.8

    async with AsyncSessionLocal() as session:
        notifications = (
            await session.execute(
                select(Notification).where(Notification.type == NotificationType.grading_complete).order_by(Notification.id.desc())
            )
        ).scalars().all()
    assert notifications
    assert notifications[0].link == '/review'


@pytest.mark.asyncio
async def test_review_lifecycle_comment_assign_approve_triggers_audit_and_notification(
    authorized_client,
    secondary_client,
    create_family_user,
    seeded_submission,
):
    review_id = await _seed_review_item(seeded_submission['id'])
    reviewer = await create_family_user(
        family_name='Unused',
        email='coparent@example.com',
        password='review-pass-123',
        display_name='Co Parent',
        role='co-parent',
        family_id=1,
    )
    await _login(secondary_client, email=reviewer['email'], password=reviewer['password'])

    comment_response = await authorized_client.post(f'/api/reviews/{review_id}/comments', json={'body': 'Second set of eyes requested.'})
    assert comment_response.status_code == 201, comment_response.text

    assign_response = await authorized_client.post(
        f'/api/reviews/{review_id}/assign',
        json={'assigned_to_user_id': reviewer['user_id']},
    )
    assert assign_response.status_code == 200, assign_response.text
    assert assign_response.json()['assigned_to_user_id'] == reviewer['user_id']

    approve_response = await secondary_client.post(
        f'/api/reviews/{review_id}/approve',
        json={
            'score': 91,
            'feedback': 'Confirmed after co-parent review.',
            'notes': 'OCR dropped a symbol.',
            'override_reason': 'Second parent verified the final answer.',
        },
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()['status'] == 'approved'
    assert approve_response.json()['comments']

    async with AsyncSessionLocal() as session:
        grade = (await session.execute(select(Grade))).scalar_one()
        assert grade.score == 91
        audit_events = (
            await session.execute(select(AuditEvent).where(AuditEvent.target_entity_type == 'review_item').order_by(AuditEvent.id))
        ).scalars().all()
        notifications = (
            await session.execute(select(Notification).where(Notification.link == f'/review/{review_id}').order_by(Notification.id))
        ).scalars().all()

    assert audit_events
    assert notifications


@pytest.mark.asyncio
async def test_reviews_bulk_operations_and_family_isolation(
    authorized_client,
    secondary_client,
    create_family_user,
    seeded_submission,
    seeded_assignment,
    seeded_student,
):
    from tests.contracts import SUBMISSIONS

    first_review_id = await _seed_review_item(seeded_submission['id'], confidence=0.49)
    second_submission_response = await authorized_client.post(
        SUBMISSIONS['collection'],
        data={'assignment_id': str(seeded_assignment['id']), 'student_id': str(seeded_student['id'])},
        files={'file': ('review-2.png', b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82', 'image/png')},
    )
    assert second_submission_response.status_code in {200, 201, 202}, second_submission_response.text
    second_review_id = await _seed_review_item(second_submission_response.json()['id'], confidence=0.58)

    reviewer = await create_family_user(
        family_name='Unused',
        email='tutor@example.com',
        password='tutor-pass-123',
        display_name='Tutor Review',
        role='tutor',
        family_id=1,
    )

    bulk_assign = await authorized_client.post(
        '/api/reviews/bulk/assign',
        json={'review_ids': [first_review_id, second_review_id], 'assigned_to_user_id': reviewer['user_id']},
    )
    assert bulk_assign.status_code == 200, bulk_assign.text
    assert bulk_assign.json()['updated'] == 2

    bulk_approve = await authorized_client.post('/api/reviews/bulk/approve', json={'review_ids': [first_review_id, second_review_id]})
    assert bulk_approve.status_code == 200, bulk_approve.text
    assert bulk_approve.json()['updated'] == 2

    other_family = await create_family_user(
        family_name='Other Family',
        email='other-parent@example.com',
        password='other-pass-123',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
    )
    await _login(secondary_client, email=other_family['email'], password=other_family['password'])

    other_family_queue = await secondary_client.get('/api/reviews')
    assert other_family_queue.status_code == 200, other_family_queue.text
    assert other_family_queue.json() == []

    blocked = await secondary_client.get(f'/api/reviews/{first_review_id}')
    assert blocked.status_code == 404, blocked.text


@pytest.mark.asyncio
async def test_student_viewer_cannot_access_reviews(authorized_client, secondary_client, create_family_user):
    viewer = await create_family_user(
        family_name='Unused',
        email='viewer@example.com',
        password='viewer-pass-123',
        display_name='Student Viewer',
        role='student_viewer',
        family_id=1,
        student_name='Scoped Student',
    )
    await _login(secondary_client, email=viewer['email'], password=viewer['password'])

    response = await secondary_client.get('/api/reviews')
    assert response.status_code == 403, response.text
