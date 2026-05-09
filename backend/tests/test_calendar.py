from __future__ import annotations

import pytest

from tests.contracts import (
    AUTH,
    CALENDAR,
    calendar_event_payload,
    grading_period_payload,
    school_year_payload,
    term_payload,
)
from tests.helpers import response_id, sync_csrf_header, update_resource


@pytest.mark.asyncio
async def test_calendar_crud_happy_path(authorized_client):
    school_year_create = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year_create.status_code == 201, school_year_create.text
    school_year = school_year_create.json()
    school_year_id = response_id(school_year)
    assert school_year['is_active'] is True

    term_create = await authorized_client.post(CALENDAR['terms'], json=term_payload(school_year_id))
    assert term_create.status_code == 201, term_create.text
    term = term_create.json()
    term_id = response_id(term)

    grading_period_create = await authorized_client.post(
        CALENDAR['grading_periods'],
        json=grading_period_payload(term_id),
    )
    assert grading_period_create.status_code == 201, grading_period_create.text
    grading_period_id = response_id(grading_period_create.json())

    event_create = await authorized_client.post(
        CALENDAR['events'],
        json=calendar_event_payload(school_year_id, notes='Family travel'),
    )
    assert event_create.status_code == 201, event_create.text
    event_id = response_id(event_create.json())

    active = await authorized_client.get(CALENDAR['active'])
    assert active.status_code == 200, active.text
    active_payload = active.json()
    assert active_payload['id'] == school_year_id
    assert len(active_payload['terms']) == 1
    assert active_payload['terms'][0]['grading_periods'][0]['id'] == grading_period_id
    assert len(active_payload['calendar_events']) == 1

    detail = await authorized_client.get(CALENDAR['school_year_detail'].format(school_year_id=school_year_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()['terms'][0]['id'] == term_id

    updated_school_year = await update_resource(
        authorized_client,
        CALENDAR['school_year_detail'].format(school_year_id=school_year_id),
        school_year_payload(name='2025-2026 Updated', is_active=True),
    )
    assert updated_school_year.status_code == 200, updated_school_year.text
    assert updated_school_year.json()['name'] == '2025-2026 Updated'

    updated_term = await update_resource(
        authorized_client,
        CALENDAR['term_detail'].format(term_id=term_id),
        {
            'name': 'Autumn Semester',
            'start_date': '2025-08-18',
            'end_date': '2025-12-19',
            'term_type': 'semester',
        },
    )
    assert updated_term.status_code == 200, updated_term.text
    assert updated_term.json()['name'] == 'Autumn Semester'

    updated_grading_period = await update_resource(
        authorized_client,
        CALENDAR['grading_period_detail'].format(grading_period_id=grading_period_id),
        {
            'name': 'Quarter 1',
            'start_date': '2025-08-18',
            'end_date': '2025-10-17',
        },
    )
    assert updated_grading_period.status_code == 200, updated_grading_period.text
    assert updated_grading_period.json()['name'] == 'Quarter 1'

    updated_event = await update_resource(
        authorized_client,
        CALENDAR['event_detail'].format(event_id=event_id),
        {
            'date': '2025-11-28',
            'event_type': 'closure',
            'name': 'Weather closure',
            'is_instructional_day': False,
            'notes': 'Snow day',
        },
    )
    assert updated_event.status_code == 200, updated_event.text
    assert updated_event.json()['event_type'] == 'closure'

    listing = await authorized_client.get(CALENDAR['school_years'])
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 1

    events_listing = await authorized_client.get(f"{CALENDAR['events']}?school_year_id={school_year_id}")
    assert events_listing.status_code == 200, events_listing.text
    assert len(events_listing.json()) == 1

    delete_event = await authorized_client.delete(CALENDAR['event_detail'].format(event_id=event_id))
    assert delete_event.status_code == 204, delete_event.text

    delete_grading_period = await authorized_client.delete(
        CALENDAR['grading_period_detail'].format(grading_period_id=grading_period_id)
    )
    assert delete_grading_period.status_code == 204, delete_grading_period.text

    delete_term = await authorized_client.delete(CALENDAR['term_detail'].format(term_id=term_id))
    assert delete_term.status_code == 204, delete_term.text

    delete_school_year = await authorized_client.delete(CALENDAR['school_year_detail'].format(school_year_id=school_year_id))
    assert delete_school_year.status_code == 204, delete_school_year.text


@pytest.mark.asyncio
async def test_calendar_family_isolation_and_student_viewer_read_only(
    authorized_client,
    secondary_client,
    tertiary_client,
    create_family_user,
):
    school_year_create = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']

    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='viewer-calendar@example.com',
        password='strongpass999',
        display_name='Calendar Viewer',
        role='student_viewer',
    )
    other_family = await create_family_user(
        family_name='Other Family',
        email='calendar-other@example.com',
        password='strongpass998',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
    )

    viewer_login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'viewer-calendar@example.com', 'password': 'strongpass999', 'family_id': family_id},
    )
    assert viewer_login.status_code == 200, viewer_login.text
    sync_csrf_header(secondary_client)

    viewer_list = await secondary_client.get(CALENDAR['school_years'])
    assert viewer_list.status_code == 200, viewer_list.text
    assert [item['id'] for item in viewer_list.json()] == [school_year_id]

    viewer_create = await secondary_client.post(
        CALENDAR['school_years'],
        json=school_year_payload(name='2026-2027', start_date='2026-08-17', end_date='2027-05-28'),
    )
    assert viewer_create.status_code == 403, viewer_create.text

    other_login = await tertiary_client.post(
        AUTH['login'],
        json={'email': 'calendar-other@example.com', 'password': 'strongpass998', 'family_id': other_family['family_id']},
    )
    assert other_login.status_code == 200, other_login.text
    sync_csrf_header(tertiary_client)

    other_detail = await tertiary_client.get(CALENDAR['school_year_detail'].format(school_year_id=school_year_id))
    assert other_detail.status_code == 404, other_detail.text


@pytest.mark.asyncio
async def test_instructional_day_count_applies_event_overrides(authorized_client):
    school_year_create = await authorized_client.post(
        CALENDAR['school_years'],
        json=school_year_payload(name='Override Year', start_date='2025-09-08', end_date='2025-09-14'),
    )
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    weekday_holiday = await authorized_client.post(
        CALENDAR['events'],
        json=calendar_event_payload(school_year_id, date='2025-09-10', name='Midweek Holiday'),
    )
    assert weekday_holiday.status_code == 201, weekday_holiday.text

    saturday_makeup = await authorized_client.post(
        CALENDAR['events'],
        json=calendar_event_payload(
            school_year_id,
            date='2025-09-13',
            event_type='custom',
            name='Saturday makeup day',
            is_instructional_day=True,
        ),
    )
    assert saturday_makeup.status_code == 201, saturday_makeup.text

    response = await authorized_client.get(CALENDAR['days'].format(school_year_id=school_year_id))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['weekday_days'] == 5
    assert payload['instructional_days'] == 5
    assert payload['non_instructional_overrides'] == 1
    assert payload['instructional_overrides'] == 1


@pytest.mark.asyncio
async def test_terms_reject_overlapping_ranges(authorized_client):
    school_year_create = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year_create.status_code == 201, school_year_create.text
    school_year_id = response_id(school_year_create.json())

    first_term = await authorized_client.post(
        CALENDAR['terms'],
        json=term_payload(school_year_id, name='Q1', start_date='2025-08-18', end_date='2025-10-17', term_type='quarter'),
    )
    assert first_term.status_code == 201, first_term.text

    overlapping_term = await authorized_client.post(
        CALENDAR['terms'],
        json=term_payload(school_year_id, name='Q2', start_date='2025-10-01', end_date='2025-12-19', term_type='quarter'),
    )
    assert overlapping_term.status_code == 409, overlapping_term.text
    assert 'overlap' in overlapping_term.json()['detail'].lower()
