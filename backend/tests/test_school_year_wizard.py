from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import jwt
import pytest

from backend.config import settings
from tests.contracts import AUTH, WIZARD, school_year_wizard_payload
from tests.helpers import assert_validation_error, sync_csrf_header


def _wizard_payload(**overrides):
    payload = school_year_wizard_payload()
    payload.update(overrides)
    return payload


async def _family_id_for(client) -> int:
    me = await client.get(AUTH['me'])
    assert me.status_code == 200, me.text
    return me.json()['family']['id']


async def _login_family_user(
    client,
    create_family_user,
    *,
    family_id: int,
    email: str,
    password: str,
    role: str,
    display_name: str,
    student_id: int | None = None,
):
    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email=email,
        password=password,
        display_name=display_name,
        role=role,
        student_id=student_id,
    )
    login = await client.post(AUTH['login'], json={'email': email, 'password': password, 'family_id': family_id})
    assert login.status_code == 200, login.text
    sync_csrf_header(client)
    return login.json()


async def _admin_headers(authorized_client, create_family_user, monkeypatch) -> dict[str, str]:
    monkeypatch.setattr(settings, 'jwt_enabled', True, raising=False)
    monkeypatch.setattr(settings, 'jwt_secret', 'wizard-jwt-secret-with-32-char-minimum', raising=False)
    monkeypatch.setattr(settings, 'jwt_jwks_url', '', raising=False)
    monkeypatch.setattr(settings, 'jwt_algorithm', 'HS256', raising=False)
    monkeypatch.setattr(settings, 'jwt_issuer', 'https://issuer.example.test', raising=False)
    monkeypatch.setattr(settings, 'jwt_audience', 'homeschool-hero-tests', raising=False)

    family_id = await _family_id_for(authorized_client)
    admin_user = await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='wizard-admin@example.com',
        password='strongpass890',
        display_name='Wizard Admin',
        role='tutor',
    )

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            'iss': settings.jwt_issuer,
            'aud': settings.jwt_audience,
            'sub': str(admin_user['user_id']),
            'user_id': admin_user['user_id'],
            'family_id': family_id,
            'family_role': 'tutor',
            'email': admin_user['email'],
            'name': 'Wizard Admin',
            'roles': ['Admin'],
            'iat': int(now.timestamp()),
            'nbf': int((now - timedelta(seconds=30)).timestamp()),
            'exp': int((now + timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {'Authorization': f'Bearer {token}'}


def _assert_evenly_split_terms(terms: list[dict[str, object]], *, start_date: str, end_date: str, expected_count: int, term_type: str) -> None:
    assert len(terms) == expected_count
    assert terms[0]['start_date'] == start_date
    assert terms[-1]['end_date'] == end_date
    assert {term['term_type'] for term in terms} == {term_type}

    expected_start = date.fromisoformat(start_date)
    lengths: list[int] = []
    for term in terms:
        actual_start = date.fromisoformat(str(term['start_date']))
        actual_end = date.fromisoformat(str(term['end_date']))
        assert actual_start == expected_start
        assert actual_start <= actual_end
        lengths.append((actual_end - actual_start).days + 1)
        expected_start = actual_end + timedelta(days=1)

    assert expected_start == date.fromisoformat(end_date) + timedelta(days=1)
    assert max(lengths) - min(lengths) <= 1


@pytest.mark.asyncio
async def test_school_year_wizard_templates_allow_parent_and_teacher_but_block_student(
    authorized_client,
    secondary_client,
    tertiary_client,
    create_family_user,
):
    parent_response = await authorized_client.get(WIZARD['templates'])
    assert parent_response.status_code == 200, parent_response.text

    templates = parent_response.json()
    assert len(templates) >= 4
    assert {
        'key',
        'name',
        'description',
        'suggested_start_date',
        'suggested_end_date',
        'default_term_structure',
    } <= set(templates[0])
    assert {item['key'] for item in templates} >= {
        'traditional_aug_may',
        'traditional_sep_jun',
        'year_round_balanced',
        'trimester_focus',
    }
    august_template = next(item for item in templates if item['key'] == 'traditional_aug_may')
    assert august_template['name'] == 'Traditional August to May'
    assert august_template['description']
    assert august_template['suggested_start_date'].startswith('08-')
    assert august_template['suggested_end_date'].startswith('05-')

    family_id = await _family_id_for(authorized_client)
    await _login_family_user(
        secondary_client,
        create_family_user,
        family_id=family_id,
        email='wizard-teacher@example.com',
        password='strongpass777',
        role='tutor',
        display_name='Wizard Teacher',
    )
    teacher_response = await secondary_client.get(WIZARD['templates'])
    assert teacher_response.status_code == 200, teacher_response.text
    assert [item['key'] for item in teacher_response.json()] == [item['key'] for item in templates]

    await _login_family_user(
        tertiary_client,
        create_family_user,
        family_id=family_id,
        email='wizard-student@example.com',
        password='strongpass778',
        role='student_viewer',
        display_name='Wizard Student',
    )
    denied = await tertiary_client.get(WIZARD['templates'])
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
async def test_school_year_wizard_holidays_return_dates_that_change_by_year(authorized_client):
    response_2026 = await authorized_client.get(WIZARD['holidays'], params={'year': 2026})
    response_2027 = await authorized_client.get(WIZARD['holidays'], params={'year': 2027})

    assert response_2026.status_code == 200, response_2026.text
    assert response_2027.status_code == 200, response_2027.text

    holidays_2026 = {item['key']: item for item in response_2026.json()}
    holidays_2027 = {item['key']: item for item in response_2027.json()}
    assert set(holidays_2026) == {'us_federal', 'christmas_break', 'easter_break', 'spring_break', 'fall_break'}

    for holiday in holidays_2026.values():
        assert {'key', 'name', 'type', 'events'} <= set(holiday)
        assert holiday['type'] in {'federal', 'religious', 'school_break'}
        assert holiday['events']
        assert any(holiday.get(field) is not None for field in ('date', 'date_range')) or holiday['events']

    assert ('2026-09-07', 'Labor Day') in {(event['date'], event['name']) for event in holidays_2026['us_federal']['events']}
    assert holidays_2026['christmas_break']['date_range'] == {'start_date': '2026-12-20', 'end_date': '2027-01-02'}

    easter_2026 = [event['date'] for event in holidays_2026['easter_break']['events']]
    easter_2027 = [event['date'] for event in holidays_2027['easter_break']['events']]
    assert easter_2026 != easter_2027
    assert easter_2026[0] == '2027-03-22'
    assert easter_2027[0] == '2028-04-10'


@pytest.mark.asyncio
async def test_school_year_wizard_holidays_missing_year_returns_validation_error(authorized_client):
    response = await authorized_client.get(WIZARD['holidays'])
    assert_validation_error(response)


@pytest.mark.asyncio
async def test_school_year_wizard_parent_creation_returns_full_school_year_with_semesters_and_events(authorized_client):
    response = await authorized_client.post(
        WIZARD['create'],
        json=_wizard_payload(
            name='2026-2027 Parent Wizard Year',
            holidays=['us_federal', 'christmas_break', 'easter_break', 'spring_break'],
            custom_breaks=[
                {
                    'name': 'Family Travel',
                    'start_date': '2026-10-15',
                    'end_date': '2026-10-16',
                }
            ],
        ),
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    assert payload['name'] == '2026-2027 Parent Wizard Year'
    assert payload['start_date'] == '2026-08-15'
    assert payload['end_date'] == '2027-05-30'
    assert payload['is_active'] is True
    assert payload['id'] > 0
    assert payload['family_id'] > 0
    _assert_evenly_split_terms(
        payload['terms'],
        start_date='2026-08-15',
        end_date='2027-05-30',
        expected_count=2,
        term_type='semester',
    )
    assert [term['name'] for term in payload['terms']] == ['Fall Semester', 'Spring Semester']

    events = {(item['date'], item['name'], item['event_type']) for item in payload['calendar_events']}
    assert ('2026-09-07', 'Labor Day', 'holiday') in events
    assert ('2026-12-20', 'Christmas Break', 'holiday') in events
    assert ('2027-01-02', 'Christmas Break', 'holiday') in events
    assert ('2027-03-15', 'Spring Break', 'closure') in events
    assert ('2027-03-22', 'Easter Break', 'holiday') in events
    assert ('2027-03-29', 'Easter Break', 'holiday') in events
    assert ('2026-10-15', 'Family Travel', 'closure') in events
    assert ('2026-10-16', 'Family Travel', 'closure') in events


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('term_structure', 'expected_count', 'term_type', 'expected_names'),
    [
        ('quarters', 4, 'quarter', ['Q1', 'Q2', 'Q3', 'Q4']),
        ('trimesters', 3, 'trimester', ['Trimester 1', 'Trimester 2', 'Trimester 3']),
    ],
)
async def test_school_year_wizard_teacher_can_create_evenly_split_terms(
    authorized_client,
    secondary_client,
    create_family_user,
    term_structure,
    expected_count,
    term_type,
    expected_names,
):
    family_id = await _family_id_for(authorized_client)
    await _login_family_user(
        secondary_client,
        create_family_user,
        family_id=family_id,
        email=f'wizard-{term_structure}@example.com',
        password='strongpass779',
        role='tutor',
        display_name='Wizard Tutor',
    )

    response = await secondary_client.post(
        WIZARD['create'],
        json=_wizard_payload(
            name=f'2026-2027 {term_structure.title()} Wizard Year',
            term_structure=term_structure,
            holidays=['fall_break'],
            custom_breaks=[],
        ),
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    _assert_evenly_split_terms(
        payload['terms'],
        start_date='2026-08-15',
        end_date='2027-05-30',
        expected_count=expected_count,
        term_type=term_type,
    )
    assert [term['name'] for term in payload['terms']] == expected_names
    assert ('2026-10-08', 'Fall Break', 'closure') in {
        (item['date'], item['name'], item['event_type']) for item in payload['calendar_events']
    }


@pytest.mark.asyncio
async def test_school_year_wizard_student_cannot_create_but_admin_app_role_can(
    authorized_client,
    secondary_client,
    tertiary_client,
    create_family_user,
    monkeypatch,
):
    family_id = await _family_id_for(authorized_client)
    await _login_family_user(
        secondary_client,
        create_family_user,
        family_id=family_id,
        email='wizard-student-create@example.com',
        password='strongpass880',
        role='student_viewer',
        display_name='Wizard Student Creator',
    )

    denied = await secondary_client.post(
        WIZARD['create'],
        json=_wizard_payload(name='Denied Student Wizard Year', holidays=[], custom_breaks=[]),
    )
    assert denied.status_code == 403, denied.text

    admin_response = await tertiary_client.post(
        WIZARD['create'],
        json=_wizard_payload(
            name='Admin Wizard Year',
            term_structure='semesters',
            holidays=['christmas_break'],
            custom_breaks=[],
        ),
        headers=await _admin_headers(authorized_client, create_family_user, monkeypatch),
    )
    assert admin_response.status_code == 201, admin_response.text
    assert [term['name'] for term in admin_response.json()['terms']] == ['Fall Semester', 'Spring Semester']


@pytest.mark.asyncio
async def test_school_year_wizard_validates_date_order_and_required_fields(authorized_client):
    invalid_range = await authorized_client.post(
        WIZARD['create'],
        json=_wizard_payload(
            name='Invalid Range Year',
            start_date='2027-05-30',
            end_date='2026-08-15',
            holidays=[],
            custom_breaks=[],
        ),
    )
    assert_validation_error(invalid_range)

    missing_name = await authorized_client.post(
        WIZARD['create'],
        json={
            'start_date': '2026-08-15',
            'end_date': '2027-05-30',
            'term_structure': 'semesters',
            'holidays': [],
            'custom_breaks': [],
        },
    )
    assert_validation_error(missing_name)


@pytest.mark.asyncio
async def test_school_year_wizard_allows_overlapping_custom_breaks_with_preset_holidays(authorized_client):
    response = await authorized_client.post(
        WIZARD['create'],
        json=_wizard_payload(
            name='Overlap Wizard Year',
            holidays=['christmas_break'],
            custom_breaks=[
                {
                    'name': 'Family Vacation',
                    'start_date': '2026-12-24',
                    'end_date': '2026-12-26',
                }
            ],
        ),
    )
    assert response.status_code == 201, response.text

    events = {(item['date'], item['name']) for item in response.json()['calendar_events']}
    assert ('2026-12-24', 'Christmas Break') in events
    assert ('2026-12-24', 'Family Vacation') in events
    assert ('2026-12-26', 'Christmas Break') in events
    assert ('2026-12-26', 'Family Vacation') in events


@pytest.mark.asyncio
async def test_school_year_wizard_handles_very_short_school_year(authorized_client):
    response = await authorized_client.post(
        WIZARD['create'],
        json=_wizard_payload(
            name='Short Wizard Year',
            start_date='2026-01-01',
            end_date='2026-01-31',
            term_structure='quarters',
            holidays=[],
            custom_breaks=[],
        ),
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    _assert_evenly_split_terms(
        payload['terms'],
        start_date='2026-01-01',
        end_date='2026-01-31',
        expected_count=4,
        term_type='quarter',
    )
    assert payload['calendar_events'] == []


@pytest.mark.asyncio
async def test_school_year_wizard_handles_year_round_school_year_crossing_calendar_boundary(authorized_client):
    response = await authorized_client.post(
        WIZARD['create'],
        json=_wizard_payload(
            name='Year Round Wizard Year',
            start_date='2026-07-15',
            end_date='2027-06-30',
            term_structure='quarters',
            holidays=['us_federal', 'christmas_break'],
            custom_breaks=[],
        ),
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    _assert_evenly_split_terms(
        payload['terms'],
        start_date='2026-07-15',
        end_date='2027-06-30',
        expected_count=4,
        term_type='quarter',
    )
    events = {(item['date'], item['name']) for item in payload['calendar_events']}
    assert ('2026-09-07', 'Labor Day') in events
    assert ('2026-12-25', 'Christmas Day') in events
    assert ('2027-01-01', "New Year's Day") in events
    assert ('2027-01-02', 'Christmas Break') in events
