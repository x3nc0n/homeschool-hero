from __future__ import annotations

import pytest

from tests.contracts import (
    AUTH,
    CALENDAR,
    SCHEDULE,
    STUDENTS,
    SUBJECTS,
    schedule_block_payload,
    schedule_override_payload,
    schedule_payload,
    school_year_payload,
    student_payload,
    subject_payload,
)
from tests.helpers import response_id, sync_csrf_header, update_resource


@pytest.mark.asyncio
async def test_schedule_crud_and_block_crud(authorized_client):
    school_year_create = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    student_create = await authorized_client.post(STUDENTS['collection'], json=student_payload())
    assert student_create.status_code == 201, student_create.text
    student_id = response_id(student_create.json())

    subject_create = await authorized_client.post(SUBJECTS['collection'], json=subject_payload())
    assert subject_create.status_code == 201, subject_create.text
    subject_id = response_id(subject_create.json())

    schedule_create = await authorized_client.post(
        SCHEDULE['collection'],
        json=schedule_payload(student_id, school_year_id),
    )
    assert schedule_create.status_code == 201, schedule_create.text
    schedule = schedule_create.json()
    schedule_id = response_id(schedule)
    assert schedule['name'] == 'Default Schedule'

    block_create = await authorized_client.post(
        SCHEDULE['blocks'].format(schedule_id=schedule_id),
        json=schedule_block_payload(subject_id),
    )
    assert block_create.status_code == 201, block_create.text
    block = block_create.json()
    block_id = response_id(block)
    assert block['subject']['name'] == 'Math'

    listing = await authorized_client.get(f"{SCHEDULE['collection']}?student_id={student_id}")
    assert listing.status_code == 200, listing.text
    listing_ids = [item['id'] for item in listing.json()]
    assert schedule_id in listing_ids

    detail = await authorized_client.get(SCHEDULE['detail'].format(schedule_id=schedule_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()['blocks'][0]['id'] == block_id

    updated_schedule = await update_resource(
        authorized_client,
        SCHEDULE['detail'].format(schedule_id=schedule_id),
        schedule_payload(student_id, school_year_id, name='Updated Schedule'),
    )
    assert updated_schedule.status_code == 200, updated_schedule.text
    assert updated_schedule.json()['name'] == 'Updated Schedule'

    updated_block = await update_resource(
        authorized_client,
        SCHEDULE['block_detail'].format(block_id=block_id),
        schedule_block_payload(subject_id, start_time='09:30', end_time='10:30', location='Library', notes='Project work'),
    )
    assert updated_block.status_code == 200, updated_block.text
    assert updated_block.json()['location'] == 'Library'

    delete_block = await authorized_client.delete(SCHEDULE['block_detail'].format(block_id=block_id))
    assert delete_block.status_code == 204, delete_block.text

    delete_schedule = await authorized_client.delete(SCHEDULE['detail'].format(schedule_id=schedule_id))
    assert delete_schedule.status_code == 204, delete_schedule.text


@pytest.mark.asyncio
async def test_agenda_generation_applies_schedule_overrides(authorized_client):
    school_year_create = await authorized_client.post(
        CALENDAR['school_years'],
        json=school_year_payload(start_date='2025-09-01', end_date='2026-05-29'),
    )
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    student_create = await authorized_client.post(STUDENTS['collection'], json=student_payload())
    assert student_create.status_code == 201, student_create.text
    student_id = response_id(student_create.json())

    math_create = await authorized_client.post(SUBJECTS['collection'], json=subject_payload())
    assert math_create.status_code == 201, math_create.text
    math_id = response_id(math_create.json())

    science_create = await authorized_client.post(SUBJECTS['collection'], json=subject_payload(name='Science', color='#16a34a'))
    assert science_create.status_code == 201, science_create.text
    science_id = response_id(science_create.json())

    schedule_create = await authorized_client.post(SCHEDULE['collection'], json=schedule_payload(student_id, school_year_id))
    assert schedule_create.status_code == 201, schedule_create.text
    schedule_id = response_id(schedule_create.json())

    recurring_math = await authorized_client.post(
        SCHEDULE['blocks'].format(schedule_id=schedule_id),
        json=schedule_block_payload(math_id, day_of_week=0, start_time='09:00', end_time='10:00', notes='Core lesson'),
    )
    assert recurring_math.status_code == 201, recurring_math.text
    recurring_math_id = response_id(recurring_math.json())

    recurring_science = await authorized_client.post(
        SCHEDULE['blocks'].format(schedule_id=schedule_id),
        json=schedule_block_payload(science_id, day_of_week=0, start_time='10:15', end_time='11:00', notes='Lab notes'),
    )
    assert recurring_science.status_code == 201, recurring_science.text
    recurring_science_id = response_id(recurring_science.json())

    cancel_math = await authorized_client.post(
        SCHEDULE['override_create'],
        json=schedule_override_payload(
            schedule_id,
            date='2025-09-15',
            override_type='cancel',
            original_block_id=recurring_math_id,
            start_time=None,
            end_time=None,
            reason='Co-op day',
        ),
    )
    assert cancel_math.status_code == 201, cancel_math.text

    reschedule_science = await authorized_client.post(
        SCHEDULE['override_create'],
        json=schedule_override_payload(
            schedule_id,
            date='2025-09-15',
            override_type='reschedule',
            original_block_id=recurring_science_id,
            subject_id=science_id,
            start_time='13:00',
            end_time='14:00',
            reason='Afternoon lab',
        ),
    )
    assert reschedule_science.status_code == 201, reschedule_science.text

    add_science = await authorized_client.post(
        SCHEDULE['override_create'],
        json=schedule_override_payload(
            schedule_id,
            date='2025-09-15',
            override_type='add',
            subject_id=science_id,
            start_time='14:15',
            end_time='15:00',
            reason='Museum prep',
        ),
    )
    assert add_science.status_code == 201, add_science.text

    agenda = await authorized_client.get(SCHEDULE['agenda'].format(student_id=student_id) + '?date=2025-09-15')
    assert agenda.status_code == 200, agenda.text
    agenda_payload = agenda.json()
    assert [item['subject_name'] for item in agenda_payload['items']] == ['Science', 'Science']
    assert agenda_payload['items'][0]['override_type'] == 'reschedule'
    assert agenda_payload['items'][0]['start_time'].startswith('13:00')
    assert agenda_payload['items'][1]['override_type'] == 'add'

    week = await authorized_client.get(SCHEDULE['week'].format(student_id=student_id) + '?date=2025-09-15')
    assert week.status_code == 200, week.text
    monday = next(day for day in week.json()['days'] if day['date'] == '2025-09-15')
    assert len(monday['items']) == 2


@pytest.mark.asyncio
async def test_schedule_conflicts_are_rejected_before_save(authorized_client):
    school_year_create = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    student_create = await authorized_client.post(STUDENTS['collection'], json=student_payload())
    assert student_create.status_code == 201, student_create.text
    student_id = response_id(student_create.json())

    subject_create = await authorized_client.post(SUBJECTS['collection'], json=subject_payload())
    assert subject_create.status_code == 201, subject_create.text
    subject_id = response_id(subject_create.json())

    first_schedule = await authorized_client.post(
        SCHEDULE['collection'],
        json=schedule_payload(student_id, school_year_id, name='Morning Schedule'),
    )
    assert first_schedule.status_code == 201, first_schedule.text
    first_schedule_id = response_id(first_schedule.json())

    second_schedule = await authorized_client.post(
        SCHEDULE['collection'],
        json=schedule_payload(student_id, school_year_id, name='Support Schedule'),
    )
    assert second_schedule.status_code == 201, second_schedule.text
    second_schedule_id = response_id(second_schedule.json())

    first_block = await authorized_client.post(
        SCHEDULE['blocks'].format(schedule_id=first_schedule_id),
        json=schedule_block_payload(subject_id, day_of_week=1, start_time='09:00', end_time='10:00'),
    )
    assert first_block.status_code == 201, first_block.text

    overlapping_block = await authorized_client.post(
        SCHEDULE['blocks'].format(schedule_id=second_schedule_id),
        json=schedule_block_payload(subject_id, day_of_week=1, start_time='09:30', end_time='10:30'),
    )
    assert overlapping_block.status_code == 409, overlapping_block.text
    assert 'overlap' in overlapping_block.json()['detail'].lower()

    original_block_id = response_id(first_block.json())
    conflicting_override = await authorized_client.post(
        SCHEDULE['override_create'],
        json=schedule_override_payload(
            first_schedule_id,
            date='2025-09-16',
            override_type='reschedule',
            original_block_id=original_block_id,
            subject_id=subject_id,
            start_time='09:30',
            end_time='10:30',
            reason='Moved later',
        ),
    )
    assert conflicting_override.status_code == 201, conflicting_override.text

    add_overlap = await authorized_client.post(
        SCHEDULE['override_create'],
        json=schedule_override_payload(
            first_schedule_id,
            date='2025-09-16',
            override_type='add',
            subject_id=subject_id,
            start_time='10:00',
            end_time='10:30',
            reason='Extra drill',
        ),
    )
    assert add_overlap.status_code == 409, add_overlap.text
    assert 'overlap' in add_overlap.json()['detail'].lower()


@pytest.mark.asyncio
async def test_schedule_family_isolation_and_student_viewer_scope(
    authorized_client,
    secondary_client,
    tertiary_client,
    create_family_user,
):
    school_year_create = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    student_create = await authorized_client.post(STUDENTS['collection'], json=student_payload())
    assert student_create.status_code == 201, student_create.text
    student_id = response_id(student_create.json())

    subject_create = await authorized_client.post(SUBJECTS['collection'], json=subject_payload())
    assert subject_create.status_code == 201, subject_create.text
    subject_id = response_id(subject_create.json())

    schedule_create = await authorized_client.post(SCHEDULE['collection'], json=schedule_payload(student_id, school_year_id))
    assert schedule_create.status_code == 201, schedule_create.text
    schedule_id = response_id(schedule_create.json())

    block_create = await authorized_client.post(
        SCHEDULE['blocks'].format(schedule_id=schedule_id),
        json=schedule_block_payload(subject_id, day_of_week=2, start_time='11:00', end_time='12:00'),
    )
    assert block_create.status_code == 201, block_create.text
    block_id = response_id(block_create.json())

    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']

    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='planner-viewer@example.com',
        password='strongpass777',
        display_name='Planner Viewer',
        role='student_viewer',
        student_id=student_id,
    )
    other_family = await create_family_user(
        family_name='Other Family',
        email='planner-other@example.com',
        password='strongpass776',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
    )

    viewer_login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'planner-viewer@example.com', 'password': 'strongpass777', 'family_id': family_id},
    )
    assert viewer_login.status_code == 200, viewer_login.text
    sync_csrf_header(secondary_client)

    viewer_agenda = await secondary_client.get(SCHEDULE['agenda'].format(student_id=student_id) + '?date=2025-09-17')
    assert viewer_agenda.status_code == 200, viewer_agenda.text

    viewer_create = await secondary_client.post(
        SCHEDULE['collection'],
        json=schedule_payload(student_id, school_year_id, name='Viewer Schedule'),
    )
    assert viewer_create.status_code == 403, viewer_create.text

    other_login = await tertiary_client.post(
        AUTH['login'],
        json={'email': 'planner-other@example.com', 'password': 'strongpass776', 'family_id': other_family['family_id']},
    )
    assert other_login.status_code == 200, other_login.text
    sync_csrf_header(tertiary_client)

    other_detail = await tertiary_client.get(SCHEDULE['detail'].format(schedule_id=schedule_id))
    assert other_detail.status_code == 404, other_detail.text

    other_block_delete = await tertiary_client.delete(SCHEDULE['block_detail'].format(block_id=block_id))
    assert other_block_delete.status_code == 404, other_block_delete.text
