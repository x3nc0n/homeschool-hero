from __future__ import annotations

from io import BytesIO

import pytest
from httpx import AsyncClient

from tests.contracts import ATTENDANCE, AUTH, PORTFOLIO, RESOURCES
from tests.contracts import attendance_daily_payload, attendance_record_payload, student_payload
from tests.helpers import response_id, sync_csrf_header


@pytest.mark.asyncio
async def test_submission_files_require_authentication_and_family_scope(
    authorized_client: AsyncClient,
    secondary_client: AsyncClient,
    tertiary_client: AsyncClient,
    create_family_user,
    seeded_submission: dict,
):
    file_url = seeded_submission['file_url']
    assert file_url.startswith('/api/files/')

    unauthenticated = await secondary_client.get(file_url)
    assert unauthenticated.status_code == 401, unauthenticated.text

    own_file = await authorized_client.get(file_url)
    assert own_file.status_code == 200, own_file.text
    assert own_file.content

    other_student = await authorized_client.post('/api/students', json=student_payload('Other Student'))
    assert other_student.status_code == 201, other_student.text
    other_student_id = response_id(other_student.json())

    family_id = (await authorized_client.get(AUTH['me'])).json()['family']['id']
    viewer = await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='file-viewer@example.com',
        password='strongpass-file-viewer',
        display_name='Scoped Viewer',
        role='student_viewer',
        student_id=other_student_id,
    )
    viewer_login = await secondary_client.post(
        AUTH['login'],
        json={'email': viewer['email'], 'password': viewer['password'], 'family_id': family_id},
    )
    assert viewer_login.status_code == 200, viewer_login.text
    sync_csrf_header(secondary_client)

    scoped_block = await secondary_client.get(file_url)
    assert scoped_block.status_code == 403, scoped_block.text

    outsider = await create_family_user(
        family_name='Other Family',
        email='file-outsider@example.com',
        password='strongpass-outsider',
        display_name='Other Parent',
        role='parent',
        is_owner=True,
        student_name='Outside Student',
    )
    outsider_login = await tertiary_client.post(
        AUTH['login'],
        json={'email': outsider['email'], 'password': outsider['password'], 'family_id': outsider['family_id']},
    )
    assert outsider_login.status_code == 200, outsider_login.text
    sync_csrf_header(tertiary_client)

    cross_family = await tertiary_client.get(file_url)
    assert cross_family.status_code == 404, cross_family.text

    traversal = await authorized_client.get('/api/files/../secrets.txt')
    assert traversal.status_code == 404, traversal.text


@pytest.mark.asyncio
async def test_other_uploaded_file_urls_use_authenticated_endpoint(
    authorized_client: AsyncClient,
):
    student = await authorized_client.post('/api/students', json=student_payload('Portfolio Student'))
    assert student.status_code == 201, student.text
    student_id = response_id(student.json())

    entry_create = await authorized_client.post(
        PORTFOLIO['entry_collection'],
        json={
            'student_id': student_id,
            'entry_type': 'photo',
            'title': 'Microscope snapshot',
            'description': 'Lab sample',
            'date': '2025-09-20',
            'tags': ['science'],
        },
    )
    assert entry_create.status_code == 201, entry_create.text
    entry = entry_create.json()

    attach_response = await authorized_client.post(
        PORTFOLIO['entry_attach'].format(entry_id=entry['id']),
        files=[('files', ('sample.png', b'\x89PNG\r\n\x1a\n', 'image/png'))],
    )
    assert attach_response.status_code == 200, attach_response.text
    attachment_url = attach_response.json()['attachment_urls'][0]
    assert attachment_url.startswith('/api/files/portfolio/')
    attachment_download = await authorized_client.get(attachment_url)
    assert attachment_download.status_code == 200, attachment_download.text

    resource_response = await authorized_client.post(
        RESOURCES['collection'],
        data={
            'name': 'Printable practice',
            'description': 'PDF worksheet',
            'resource_type': 'file',
            'tags': '["worksheet"]',
            'metadata': '{"format":"pdf"}',
        },
        files={'file': ('practice.pdf', b'%PDF-1.4 curriculum practice', 'application/pdf')},
    )
    assert resource_response.status_code == 201, resource_response.text
    resource_url = resource_response.json()['file_url']
    assert resource_url.startswith('/api/files/resources/')
    resource_download = await authorized_client.get(resource_url)
    assert resource_download.status_code == 200, resource_download.text

    attendance_student = await authorized_client.post('/api/students', json=student_payload('Attendance Student'))
    assert attendance_student.status_code == 201, attendance_student.text
    attendance_student_id = response_id(attendance_student.json())
    attendance = await authorized_client.post(
        ATTENDANCE['daily'],
        json=attendance_daily_payload(
            '2025-09-15',
            [attendance_record_payload(attendance_student_id, status='absent', instructional_hours='0.00', notes='Fever')],
        ),
    )
    assert attendance.status_code == 201, attendance.text
    record_id = attendance.json()[0]['id']
    excuse = await authorized_client.post(
        ATTENDANCE['excuses'],
        files={'document': ('doctor-note.pdf', BytesIO(b'%PDF-1.4 fake note').read(), 'application/pdf')},
        data={'attendance_record_id': str(record_id), 'reason': 'Doctor note on file'},
    )
    assert excuse.status_code == 201, excuse.text
    document_url = excuse.json()['document_url']
    assert document_url and document_url.startswith('/api/files/')
    document_download = await authorized_client.get(document_url)
    assert document_download.status_code == 200, document_download.text
