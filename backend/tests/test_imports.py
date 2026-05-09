from __future__ import annotations

import asyncio
import json

import pytest
from httpx import AsyncClient

from tests.contracts import CALENDAR, GRADES, STUDENTS, SUBJECTS
from tests.helpers import sync_csrf_header

IMPORTS = {
    'collection': '/api/imports',
    'upload': '/api/imports/upload',
    'detail': '/api/imports/{job_id}/status',
    'validate': '/api/imports/{job_id}/validate',
    'execute': '/api/imports/{job_id}/execute',
}


async def _upload_import_job(
    client: AsyncClient,
    *,
    entity_type: str,
    filename: str,
    content: str,
    content_type: str = 'text/csv',
) -> dict:
    response = await client.post(
        IMPORTS['upload'],
        params={'entity_type': entity_type},
        files={'file': (filename, content.encode('utf-8'), content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _wait_for_job(client: AsyncClient, job_id: int, *, timeout: float = 5.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(IMPORTS['detail'].format(job_id=job_id))
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload['status'] in {'complete', 'failed'}:
            return payload
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail(f'Import job {job_id} did not finish in time: {payload}')
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_import_dry_run_reports_row_errors_without_committing(authorized_client: AsyncClient):
    csv_content = 'name\nAda Lovelace\n \nAda Lovelace\n'
    job = await _upload_import_job(
        authorized_client,
        entity_type='students',
        filename='students.csv',
        content=csv_content,
    )

    validate_response = await authorized_client.post(IMPORTS['validate'].format(job_id=job['id']))
    assert validate_response.status_code == 200, validate_response.text
    payload = validate_response.json()

    assert payload['status'] == 'failed'
    assert payload['error_count'] == 2
    assert {error['row'] for error in payload['errors']} == {3, 4}
    assert any(error['field'] == 'name' and 'required' in error['message'].lower() for error in payload['errors'])

    students_response = await authorized_client.get(STUDENTS['collection'])
    assert students_response.status_code == 200, students_response.text
    assert students_response.json() == []


@pytest.mark.asyncio
async def test_import_execute_tracks_progress(monkeypatch, authorized_client: AsyncClient):
    from backend.services import import_service

    original_apply_students = import_service._apply_students

    async def slow_apply_students(db, job, rows):
        await asyncio.sleep(0.2)
        await original_apply_students(db, job, rows)

    monkeypatch.setattr(import_service, '_apply_students', slow_apply_students)
    csv_content = 'name\n' + '\n'.join(f'Student {index}' for index in range(1, 31))
    job = await _upload_import_job(
        authorized_client,
        entity_type='students',
        filename='students.csv',
        content=csv_content,
    )

    execute_response = await authorized_client.post(IMPORTS['execute'].format(job_id=job['id']))
    assert execute_response.status_code == 202, execute_response.text

    observed_importing = False
    observed_progress = False
    for _ in range(30):
        status_response = await authorized_client.get(IMPORTS['detail'].format(job_id=job['id']))
        payload = status_response.json()
        if payload['status'] == 'importing':
            observed_importing = True
            if payload['total_rows'] == 30:
                observed_progress = True
                break
        if payload['status'] in {'complete', 'failed'}:
            break
        await asyncio.sleep(0.05)

    final_job = await _wait_for_job(authorized_client, job['id'])
    assert observed_importing
    assert observed_progress
    assert final_job['status'] == 'complete'
    assert final_job['processed_rows'] == 30
    assert final_job['total_rows'] == 30

    audit_response = await authorized_client.get('/api/audit?entity_type=import_job')
    assert audit_response.status_code == 200, audit_response.text
    assert any(item['target_entity_id'] == str(job['id']) for item in audit_response.json()['items'])


@pytest.mark.asyncio
async def test_assignment_grade_and_attendance_imports_succeed(authorized_client: AsyncClient):
    subject_response = await authorized_client.post(SUBJECTS['collection'], json={'name': 'Mathematics', 'color': '#2563eb'})
    assert subject_response.status_code == 201, subject_response.text
    student_response = await authorized_client.post(STUDENTS['collection'], json={'name': 'Ada Lovelace'})
    assert student_response.status_code == 201, student_response.text
    student_id = student_response.json()['id']

    assignment_job = await _upload_import_job(
        authorized_client,
        entity_type='assignments',
        filename='assignments.csv',
        content=(
            'title,subject_name,description,due_date,status,category,grading_period_name,weight,max_score,recurrence,recurrence_end_date,'
            'rubric_description,target_student_names\n'
            'Fractions Worksheet,Mathematics,Complete problems 1-10.,2026-05-15,pending,homework,,1,100,none,,Show your work.,Ada Lovelace\n'
        ),
    )
    execute_assignment = await authorized_client.post(IMPORTS['execute'].format(job_id=assignment_job['id']))
    assert execute_assignment.status_code == 202, execute_assignment.text
    assignment_result = await _wait_for_job(authorized_client, assignment_job['id'])
    assert assignment_result['status'] == 'complete'

    grade_job = await _upload_import_job(
        authorized_client,
        entity_type='grades',
        filename='grades.csv',
        content=(
            'student_name,assignment_title,subject_name,score,max_score,letter_grade,notes,graded_by,ai_confidence\n'
            'Ada Lovelace,Fractions Worksheet,Mathematics,94,100,A,Imported from SIS,human,\n'
        ),
    )
    execute_grade = await authorized_client.post(IMPORTS['execute'].format(job_id=grade_job['id']))
    assert execute_grade.status_code == 202, execute_grade.text
    grade_result = await _wait_for_job(authorized_client, grade_job['id'])
    assert grade_result['status'] == 'complete'

    grades_response = await authorized_client.get(GRADES['collection'])
    assert grades_response.status_code == 200, grades_response.text
    grades = grades_response.json()
    assert grades['total'] == 1
    assert grades['items'][0]['score'] == 94
    assert grades['items'][0]['letter_grade'] == 'A'

    attendance_job = await _upload_import_job(
        authorized_client,
        entity_type='attendance',
        filename='attendance.csv',
        content=(
            'student_name,date,status,check_in_time,check_out_time,instructional_hours,notes\n'
            'Ada Lovelace,2026-05-14,present,09:00,13:00,4.00,Science lab day\n'
        ),
    )
    execute_attendance = await authorized_client.post(IMPORTS['execute'].format(job_id=attendance_job['id']))
    assert execute_attendance.status_code == 202, execute_attendance.text
    attendance_result = await _wait_for_job(authorized_client, attendance_job['id'])
    assert attendance_result['status'] == 'complete'

    attendance_response = await authorized_client.get(f'/api/attendance?student_id={student_id}&date=2026-05-14')
    assert attendance_response.status_code == 200, attendance_response.text
    records = attendance_response.json()
    assert len(records) == 1
    assert records[0]['instructional_hours'] == '4.00'


@pytest.mark.asyncio
async def test_curriculum_package_json_import_succeeds(authorized_client: AsyncClient):
    school_year_response = await authorized_client.post(
        CALENDAR['school_years'],
        json={'name': '2026-2027', 'start_date': '2026-08-15', 'end_date': '2027-05-30', 'is_active': True},
    )
    assert school_year_response.status_code == 201, school_year_response.text
    subject_response = await authorized_client.post(SUBJECTS['collection'], json={'name': 'Science', 'color': '#16a34a'})
    assert subject_response.status_code == 201, subject_response.text

    curriculum_job = await _upload_import_job(
        authorized_client,
        entity_type='curriculum_packages',
        filename='curriculum.json',
        content=json.dumps(
            {
                'packages': [
                    {
                        'name': 'Biology Foundations',
                        'school_year_name': '2026-2027',
                        'subject_name': 'Science',
                        'description': 'Core biology sequence.',
                        'units': [
                            {
                                'name': 'Cells',
                                'sequence_order': 1,
                                'lessons': [
                                    {
                                        'name': 'Cell theory',
                                        'sequence_order': 1,
                                        'resources': [
                                            {'name': 'Notebook page', 'resource_type': 'note', 'description': 'Guided notes'},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        content_type='application/json',
    )
    execute_response = await authorized_client.post(IMPORTS['execute'].format(job_id=curriculum_job['id']))
    assert execute_response.status_code == 202, execute_response.text
    result = await _wait_for_job(authorized_client, curriculum_job['id'])
    assert result['status'] == 'complete'

    packages_response = await authorized_client.get('/api/curriculum/packages')
    assert packages_response.status_code == 200, packages_response.text
    packages = packages_response.json()
    assert len(packages) == 1
    assert packages[0]['name'] == 'Biology Foundations'
    assert packages[0]['units'][0]['lessons'][0]['resources'][0]['name'] == 'Notebook page'


@pytest.mark.asyncio
async def test_import_jobs_are_family_scoped(
    authorized_client: AsyncClient,
    secondary_client: AsyncClient,
    create_family_user,
):
    secondary_user = await create_family_user(
        family_name='Other Family',
        email='other@example.com',
        password='strongpass123',
        display_name='Other Parent',
    )
    login_response = await secondary_client.post(
        '/api/auth/login',
        json={'email': secondary_user['email'], 'password': secondary_user['password']},
    )
    assert login_response.status_code == 200, login_response.text
    sync_csrf_header(secondary_client)

    job = await _upload_import_job(
        authorized_client,
        entity_type='students',
        filename='students.csv',
        content='name\nAda Lovelace\n',
    )

    list_response = await secondary_client.get(IMPORTS['collection'])
    assert list_response.status_code == 200, list_response.text
    assert list_response.json() == []

    status_response = await secondary_client.get(IMPORTS['detail'].format(job_id=job['id']))
    assert status_response.status_code == 404, status_response.text
