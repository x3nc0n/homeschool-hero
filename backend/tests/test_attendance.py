from __future__ import annotations

from io import BytesIO

import pytest

from tests.contracts import (
    ATTENDANCE,
    AUTH,
    CALENDAR,
    attendance_daily_payload,
    attendance_hours_payload,
    attendance_record_payload,
    school_year_payload,
    student_payload,
    term_payload,
)
from tests.helpers import response_id, sync_csrf_header


@pytest.mark.asyncio
async def test_attendance_crud_and_summaries(authorized_client):
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())

    term = await authorized_client.post(
        CALENDAR['terms'],
        json=term_payload(school_year_id, name='Fall Semester', start_date='2025-08-18', end_date='2025-12-19'),
    )
    assert term.status_code == 201, term.text

    student = await authorized_client.post('/api/students', json=student_payload('Ada Lovelace'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    daily = await authorized_client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload(
            '2025-09-08',
            [
                attendance_record_payload(
                    student_id,
                    status='tardy',
                    instructional_hours='5.50',
                    check_in_time='09:20:00',
                    check_out_time='15:00:00',
                    notes='Late after dentist appointment',
                )
            ],
        ),
    )
    assert daily.status_code == 201, daily.text
    record = daily.json()[0]
    assert record['status'] == 'tardy'
    assert record['instructional_hours'] == '5.50'

    hours = await authorized_client.post(
        ATTENDANCE['hours'],
        json=attendance_hours_payload(student_id, attendance_date='2025-09-09', instructional_hours='4.25'),
    )
    assert hours.status_code == 200, hours.text
    assert hours.json()['status'] == 'present'

    listing = await authorized_client.get(f"{ATTENDANCE['collection']}?date_from=2025-09-01&date_to=2025-09-30")
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 2

    day_summary = await authorized_client.get(f"{ATTENDANCE['summary']}?student_id={student_id}&period=day")
    assert day_summary.status_code == 200, day_summary.text
    assert day_summary.json()['total_records'] == 2
    assert len(day_summary.json()['buckets']) == 2

    week_summary = await authorized_client.get(f"{ATTENDANCE['summary']}?student_id={student_id}&period=week")
    assert week_summary.status_code == 200, week_summary.text
    assert week_summary.json()['attendance_rate'] == 100.0

    term_summary = await authorized_client.get(
        f"{ATTENDANCE['summary']}?student_id={student_id}&period=term&school_year_id={school_year_id}"
    )
    assert term_summary.status_code == 200, term_summary.text
    assert term_summary.json()['buckets'][0]['label'] == 'Fall Semester'

    year_summary = await authorized_client.get(
        f"{ATTENDANCE['summary']}?student_id={student_id}&period=year&school_year_id={school_year_id}"
    )
    assert year_summary.status_code == 200, year_summary.text
    assert year_summary.json()['total_hours'] == '9.75'

    hours_total = await authorized_client.get(f"{ATTENDANCE['hours']}?student_id={student_id}&school_year_id={school_year_id}")
    assert hours_total.status_code == 200, hours_total.text
    assert hours_total.json()['total_hours'] == '9.75'
    assert hours_total.json()['recorded_days'] == 2


@pytest.mark.asyncio
async def test_attendance_excuse_workflow_and_audit_trail(authorized_client):
    student = await authorized_client.post('/api/students', json=student_payload('Grace Hopper'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    attendance = await authorized_client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload(
            '2025-09-15',
            [attendance_record_payload(student_id, status='absent', instructional_hours='0.00', notes='Fever')],
        ),
    )
    assert attendance.status_code == 201, attendance.text
    record_id = attendance.json()[0]['id']

    files = {'document': ('doctor-note.pdf', BytesIO(b'%PDF-1.4 fake note').read(), 'application/pdf')}
    data = {'attendance_record_id': str(record_id), 'reason': 'Doctor note on file'}
    excuse = await authorized_client.post(ATTENDANCE['excuses'], files=files, data=data)
    assert excuse.status_code == 201, excuse.text
    excuse_payload = excuse.json()
    assert excuse_payload['document_path']

    approved = await authorized_client.post(ATTENDANCE['excuse_approve'].format(excuse_id=excuse_payload['id']))
    assert approved.status_code == 200, approved.text
    assert approved.json()['approved_by_user_id'] is not None

    refreshed = await authorized_client.get(f"{ATTENDANCE['collection']}?date=2025-09-15&student_id={student_id}")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()[0]['status'] == 'excused'
    assert refreshed.json()[0]['excuse']['reason'] == 'Doctor note on file'

    audit = await authorized_client.get('/api/audit?action=attendance_edit')
    assert audit.status_code == 200, audit.text
    items = audit.json()['items']
    assert len(items) >= 3
    assert any(item['target_entity_type'] == 'attendance_record' for item in items)
    assert any(item['target_entity_type'] == 'attendance_excuse' for item in items)
    assert any(item['after_snapshot'] and 'document_path' in str(item['after_snapshot']) for item in items)


@pytest.mark.asyncio
async def test_attendance_family_isolation_and_student_scope(
    authorized_client,
    secondary_client,
    tertiary_client,
    create_family_user,
):
    school_year = await authorized_client.post(CALENDAR['school_years'], json=school_year_payload())
    assert school_year.status_code == 201, school_year.text
    school_year_id = response_id(school_year.json())

    primary_student = await authorized_client.post('/api/students', json=student_payload('Primary Student'))
    assert primary_student.status_code == 201, primary_student.text
    primary_student_id = response_id(primary_student.json())

    family_id = (await authorized_client.get(AUTH['me'])).json()['family']['id']
    viewer = await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='attendance-viewer@example.com',
        password='strongpass777',
        display_name='Attendance Viewer',
        role='student_viewer',
        student_id=primary_student_id,
    )
    other_family = await create_family_user(
        family_name='Other Family',
        email='attendance-other@example.com',
        password='strongpass776',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
        student_name='Other Student',
    )

    daily = await authorized_client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload('2025-10-01', [attendance_record_payload(primary_student_id, status='present')]),
    )
    assert daily.status_code == 201, daily.text

    viewer_login = await secondary_client.post(
        AUTH['login'],
        json={'email': viewer['email'], 'password': viewer['password'], 'family_id': family_id},
    )
    assert viewer_login.status_code == 200, viewer_login.text
    sync_csrf_header(secondary_client)

    viewer_records = await secondary_client.get(ATTENDANCE['collection'])
    assert viewer_records.status_code == 200, viewer_records.text
    assert {item['student_id'] for item in viewer_records.json()} == {primary_student_id}

    viewer_hours = await secondary_client.get(
        f"{ATTENDANCE['hours']}?student_id={primary_student_id}&school_year_id={school_year_id}"
    )
    assert viewer_hours.status_code == 200, viewer_hours.text

    other_login = await tertiary_client.post(
        AUTH['login'],
        json={
            'email': other_family['email'],
            'password': other_family['password'],
            'family_id': other_family['family_id'],
        },
    )
    assert other_login.status_code == 200, other_login.text
    sync_csrf_header(tertiary_client)

    other_records = await tertiary_client.get(f"{ATTENDANCE['collection']}?student_id={primary_student_id}")
    assert other_records.status_code == 404, other_records.text

    other_summary = await tertiary_client.get(
        f"{ATTENDANCE['summary']}?student_id={primary_student_id}&period=year&school_year_id={school_year_id}"
    )
    assert other_summary.status_code == 404, other_summary.text
