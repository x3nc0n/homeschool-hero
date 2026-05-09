from __future__ import annotations

import pytest

from tests.contracts import (
    CALENDAR,
    CURRICULUM,
    LESSON_PLANS,
    SCHEDULE,
    STUDENTS,
    SUBJECTS,
    curriculum_lesson_payload,
    curriculum_package_payload,
    curriculum_unit_payload,
    schedule_block_payload,
    schedule_payload,
    school_year_payload,
    student_payload,
    subject_payload,
)
from tests.helpers import response_id


async def _seed_package_with_schedule(client):
    school_year_response = await client.post(
        CALENDAR['school_years'],
        json=school_year_payload(
            name='2026-2027',
            start_date='2026-08-17',
            end_date='2027-05-28',
            is_active=False,
        ),
    )
    assert school_year_response.status_code == 201, school_year_response.text
    school_year_id = response_id(school_year_response.json())

    student_response = await client.post(STUDENTS['collection'], json=student_payload('Alan Turing'))
    assert student_response.status_code == 201, student_response.text
    student_id = response_id(student_response.json())

    subject_response = await client.post(SUBJECTS['collection'], json=subject_payload(name='Math', color='#2563eb'))
    assert subject_response.status_code == 201, subject_response.text
    subject_id = response_id(subject_response.json())

    package_response = await client.post(
        CURRICULUM['packages'],
        json=curriculum_package_payload(school_year_id, subject_id, name='Math 6'),
    )
    assert package_response.status_code == 201, package_response.text
    package_id = response_id(package_response.json())

    unit_one = await client.post(
        CURRICULUM['units'],
        json=curriculum_unit_payload(package_id, name='Unit 1: Fractions', sequence_order=1),
    )
    assert unit_one.status_code == 201, unit_one.text
    unit_one_id = response_id(unit_one.json())

    unit_two = await client.post(
        CURRICULUM['units'],
        json=curriculum_unit_payload(package_id, name='Unit 2: Decimals', sequence_order=2),
    )
    assert unit_two.status_code == 201, unit_two.text
    unit_two_id = response_id(unit_two.json())

    lesson_ids: list[int] = []
    for unit_id, names in (
        (unit_one_id, ('Lesson 1', 'Lesson 2')),
        (unit_two_id, ('Lesson 3', 'Lesson 4')),
    ):
        for index, name in enumerate(names, start=1):
            lesson_response = await client.post(
                CURRICULUM['lessons'],
                json=curriculum_lesson_payload(
                    unit_id,
                    name=name,
                    sequence_order=index,
                    estimated_duration_minutes=45,
                ),
            )
            assert lesson_response.status_code == 201, lesson_response.text
            lesson_ids.append(response_id(lesson_response.json()))

    schedule_response = await client.post(
        SCHEDULE['collection'],
        json=schedule_payload(student_id, school_year_id, name='Core Schedule'),
    )
    assert schedule_response.status_code == 201, schedule_response.text
    schedule_id = response_id(schedule_response.json())

    monday_block = await client.post(
        SCHEDULE['blocks'].format(schedule_id=schedule_id),
        json=schedule_block_payload(subject_id, day_of_week=0, start_time='09:00', end_time='10:00'),
    )
    assert monday_block.status_code == 201, monday_block.text

    wednesday_block = await client.post(
        SCHEDULE['blocks'].format(schedule_id=schedule_id),
        json=schedule_block_payload(subject_id, day_of_week=2, start_time='09:00', end_time='10:00'),
    )
    assert wednesday_block.status_code == 201, wednesday_block.text

    return {
        'school_year_id': school_year_id,
        'student_id': student_id,
        'subject_id': subject_id,
        'package_id': package_id,
        'unit_ids': [unit_one_id, unit_two_id],
        'lesson_ids': lesson_ids,
    }


@pytest.mark.asyncio
async def test_generate_lesson_plans_from_curriculum_builds_sequence_and_pacing_targets(authorized_client):
    seeded = await _seed_package_with_schedule(authorized_client)

    generate = await authorized_client.post(
        LESSON_PLANS['generate'],
        json={'package_id': seeded['package_id'], 'student_id': seeded['student_id']},
    )
    assert generate.status_code == 201, generate.text
    lesson_plans = generate.json()
    assert [item['target_date'] for item in lesson_plans] == ['2026-08-17', '2026-08-19', '2026-08-24', '2026-08-26']
    assert all(item['student_id'] == seeded['student_id'] for item in lesson_plans)

    pacing_targets = await authorized_client.get(
        LESSON_PLANS['pacing_targets'],
        params={'student_id': seeded['student_id'], 'subject_id': seeded['subject_id']},
    )
    assert pacing_targets.status_code == 200, pacing_targets.text
    pacing_payload = pacing_targets.json()
    assert len(pacing_payload) == 2
    assert pacing_payload[0]['target_start_date'] == '2026-08-17'
    assert pacing_payload[0]['target_end_date'] == '2026-08-19'
    assert pacing_payload[1]['target_start_date'] == '2026-08-24'
    assert pacing_payload[1]['target_end_date'] == '2026-08-26'


@pytest.mark.asyncio
async def test_pacing_status_turns_ahead_when_lessons_complete(authorized_client):
    seeded = await _seed_package_with_schedule(authorized_client)
    generate = await authorized_client.post(
        LESSON_PLANS['generate'],
        json={'package_id': seeded['package_id'], 'student_id': seeded['student_id']},
    )
    assert generate.status_code == 201, generate.text
    lesson_plans = generate.json()

    first_unit_plans = [item for item in lesson_plans if item['curriculum_lesson']['unit']['id'] == seeded['unit_ids'][0]]
    complete = await authorized_client.post(
        LESSON_PLANS['bulk_status'],
        json={'lesson_plan_ids': [item['id'] for item in first_unit_plans], 'status': 'completed'},
    )
    assert complete.status_code == 200, complete.text
    assert all(item['completed_at'] for item in complete.json())

    pacing = await authorized_client.get(
        LESSON_PLANS['pacing'].format(student_id=seeded['student_id']),
        params={'subject_id': seeded['subject_id']},
    )
    assert pacing.status_code == 200, pacing.text
    pacing_items = pacing.json()['items']
    first_unit_status = next(item for item in pacing_items if item['curriculum_unit_id'] == seeded['unit_ids'][0])
    assert first_unit_status['status'] == 'ahead'
    assert first_unit_status['actual_completion_date'] is not None


@pytest.mark.asyncio
async def test_reschedule_bulk_update_changes_target_date_and_status(authorized_client):
    seeded = await _seed_package_with_schedule(authorized_client)
    generate = await authorized_client.post(
        LESSON_PLANS['generate'],
        json={'package_id': seeded['package_id'], 'student_id': seeded['student_id']},
    )
    assert generate.status_code == 201, generate.text
    lesson_plan = generate.json()[0]

    reschedule = await authorized_client.post(
        LESSON_PLANS['bulk_status'],
        json={
            'lesson_plan_ids': [lesson_plan['id']],
            'status': 'rescheduled',
            'target_date': '2026-08-21',
            'notes': 'Co-op moved this lesson to Friday.',
        },
    )
    assert reschedule.status_code == 200, reschedule.text
    updated = reschedule.json()[0]
    assert updated['status'] == 'rescheduled'
    assert updated['target_date'] == '2026-08-21'
    assert updated['notes'] == 'Co-op moved this lesson to Friday.'

    detail = await authorized_client.get(LESSON_PLANS['detail'].format(lesson_plan_id=lesson_plan['id']))
    assert detail.status_code == 200, detail.text
    assert detail.json()['target_date'] == '2026-08-21'


@pytest.mark.asyncio
async def test_assignment_generation_links_assignments_to_lesson_plans(authorized_client):
    seeded = await _seed_package_with_schedule(authorized_client)
    generate = await authorized_client.post(
        LESSON_PLANS['generate'],
        json={'package_id': seeded['package_id'], 'student_id': seeded['student_id']},
    )
    assert generate.status_code == 201, generate.text
    lesson_plan = generate.json()[0]

    assignments = await authorized_client.post(
        LESSON_PLANS['generate_assignments'],
        json={'lesson_plan_ids': [lesson_plan['id']]},
    )
    assert assignments.status_code == 201, assignments.text
    assignment = assignments.json()[0]
    assert assignment['lesson_plan_id'] == lesson_plan['id']
    assert assignment['targets'][0]['student_id'] == seeded['student_id']

    detail = await authorized_client.get(LESSON_PLANS['detail'].format(lesson_plan_id=lesson_plan['id']))
    assert detail.status_code == 200, detail.text
    assert detail.json()['assignment_ids'] == [assignment['id']]
