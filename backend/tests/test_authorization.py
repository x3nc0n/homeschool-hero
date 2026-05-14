from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.config import settings
from backend.security import AuthSession, resolve_external_app_roles
from backend.services.authorization import Capability, has_capability
from tests.contracts import ASSIGNMENTS, AUTH, BACKUPS, GRADES, INVITATIONS, STUDENTS, assignment_payload, student_payload
from tests.helpers import response_id, sync_csrf_header


@pytest.mark.asyncio
async def test_rbac_enforces_role_permissions(authorized_client, secondary_client, create_family_user, seeded_subject, seeded_student, seeded_assignment, seeded_submission, seeded_grade):
    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']
    student_id = response_id(seeded_student)

    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='coparent@example.com',
        password='strongpass234',
        display_name='Co Parent',
        role='co-parent',
    )
    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='tutor@example.com',
        password='strongpass345',
        display_name='Tutor User',
        role='tutor',
    )
    await create_family_user(
        family_name='Test Family',
        family_id=family_id,
        email='viewer@example.com',
        password='strongpass456',
        display_name='Viewer User',
        role='student_viewer',
        student_id=student_id,
    )
    await authorized_client.post(STUDENTS['collection'], json=student_payload('Grace Hopper'))

    login = await secondary_client.post(AUTH['login'], json={'email': 'tutor@example.com', 'password': 'strongpass345', 'family_id': family_id})
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    tutor_assignment = await secondary_client.post(ASSIGNMENTS['collection'], json=assignment_payload(response_id(seeded_subject)))
    assert tutor_assignment.status_code == 201, tutor_assignment.text

    tutor_student = await secondary_client.post(STUDENTS['collection'], json=student_payload('Tutor Cannot Add'))
    assert tutor_student.status_code == 403, tutor_student.text
    assert 'manage students' in tutor_student.json()['detail']

    tutor_invite = await secondary_client.post(INVITATIONS['collection'], json={'email': 'blocked@example.com', 'role': 'tutor', 'expires_in_days': 7})
    assert tutor_invite.status_code == 403, tutor_invite.text
    assert 'create invitations' in tutor_invite.json()['detail']

    await secondary_client.post(AUTH['logout'])
    viewer_login = await secondary_client.post(AUTH['login'], json={'email': 'viewer@example.com', 'password': 'strongpass456', 'family_id': family_id})
    assert viewer_login.status_code == 200, viewer_login.text
    sync_csrf_header(secondary_client)
    assert viewer_login.json()['membership']['student_id'] == student_id

    viewer_students = await secondary_client.get(STUDENTS['collection'])
    assert viewer_students.status_code == 200, viewer_students.text
    assert [item['id'] for item in viewer_students.json()] == [student_id]

    other_student = await authorized_client.get(STUDENTS['collection'])
    other_student_id = [item['id'] for item in other_student.json() if item['id'] != student_id][0]
    forbidden_student = await secondary_client.get(STUDENTS['detail'].format(student_id=other_student_id))
    assert forbidden_student.status_code == 403, forbidden_student.text

    forbidden_upload = await secondary_client.post(
        '/api/submissions',
        data={'assignment_id': str(response_id(seeded_assignment)), 'student_id': str(student_id)},
        files={
            'file': (
                'fractions.png',
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0'
                b'\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82',
                'image/png',
            )
        },
    )
    assert forbidden_upload.status_code == 403, forbidden_upload.text

    viewer_grade = await secondary_client.get(GRADES['detail'].format(grade_id=response_id(seeded_grade)))
    assert viewer_grade.status_code == 200, viewer_grade.text

    forbidden_grade_history = await secondary_client.get(f"{GRADES['history']}?student_id={other_student_id}")
    assert forbidden_grade_history.status_code == 403, forbidden_grade_history.text


@pytest.mark.asyncio
async def test_tenant_isolation_blocks_cross_family_reads_for_same_role(authorized_client, secondary_client, tertiary_client, create_family_user, seeded_subject):
    assignment = await authorized_client.post(ASSIGNMENTS['collection'], json=assignment_payload(response_id(seeded_subject)))
    assert assignment.status_code == 201, assignment.text
    assignment_id = response_id(assignment.json())

    parent_login = await authorized_client.get(AUTH['me'])
    family_a_id = parent_login.json()['family']['id']
    await create_family_user(
        family_name='Family A',
        family_id=family_a_id,
        email='tutor-a@example.com',
        password='strongpass567',
        display_name='Tutor A',
        role='tutor',
    )

    other_family = await create_family_user(
        family_name='Other Family',
        email='owner-other@example.com',
        password='strongpass678',
        display_name='Owner Other',
        role='parent',
        is_owner=True,
    )
    await create_family_user(
        family_name='Other Family',
        family_id=other_family['family_id'],
        email='tutor-b@example.com',
        password='strongpass789',
        display_name='Tutor B',
        role='tutor',
    )

    login = await tertiary_client.post(AUTH['login'], json={'email': 'tutor-b@example.com', 'password': 'strongpass789', 'family_id': other_family['family_id']})
    assert login.status_code == 200, login.text
    sync_csrf_header(tertiary_client)

    detail = await tertiary_client.get(ASSIGNMENTS['detail'].format(assignment_id=assignment_id))
    assert detail.status_code == 404, detail.text


def test_local_auth_session_synthesizes_app_roles_and_effective_capabilities() -> None:
    auth = AuthSession(
        user_id=1,
        family_id=1,
        email='owner@example.com',
        display_name='Owner',
        auth_provider='local',
        role='parent',
        is_owner=True,
        family_name='Test Family',
    )

    assert auth.family_role == 'parent'
    assert auth.app_roles == ['admin', 'teacher']
    assert has_capability(auth, Capability.manage_family)
    assert Capability.manage_platform.value in auth.effective_capabilities
    assert Capability.manage_household.value in auth.effective_capabilities


def test_external_role_mapping_supports_aliases_and_fails_closed(monkeypatch) -> None:
    original_teacher = settings.role_mapping_teacher_raw
    original_admin = settings.role_mapping_admin_raw
    original_student = settings.role_mapping_student_raw
    monkeypatch.setattr(settings, 'role_mapping_teacher_raw', 'Teacher,Instructor,Educator')
    monkeypatch.setattr(settings, 'role_mapping_admin_raw', original_admin)
    monkeypatch.setattr(settings, 'role_mapping_student_raw', original_student)

    assert resolve_external_app_roles(['Instructor']) == ['teacher']
    assert resolve_external_app_roles(['Unknown Role']) == []

    monkeypatch.setattr(settings, 'role_mapping_teacher_raw', original_teacher)


def test_external_teacher_role_is_narrower_than_parent_membership_without_admin() -> None:
    auth = AuthSession(
        user_id=1,
        family_id=1,
        email='external@example.com',
        display_name='External Parent',
        auth_provider='oidc',
        family_role='parent',
        app_roles=['teacher'],
        is_owner=True,
        family_name='Test Family',
    )

    assert has_capability(auth, Capability.manage_household)
    assert not has_capability(auth, Capability.manage_platform)


@pytest.mark.asyncio
async def test_bearer_token_takes_precedence_over_cookie_session(authorized_client, secondary_client, seeded_student, monkeypatch):
    monkeypatch.setattr(settings, 'jwt_enabled', True, raising=False)
    monkeypatch.setattr(settings, 'jwt_secret', 'authz-jwt-secret-with-32-char-minimum', raising=False)
    monkeypatch.setattr(settings, 'jwt_jwks_url', '', raising=False)
    monkeypatch.setattr(settings, 'jwt_algorithm', 'HS256', raising=False)
    monkeypatch.setattr(settings, 'jwt_issuer', 'https://issuer.example.test', raising=False)
    monkeypatch.setattr(settings, 'jwt_audience', 'homeschool-hero-tests', raising=False)

    me = await authorized_client.get(AUTH['me'])
    family_id = me.json()['family']['id']
    student_id = response_id(seeded_student)
    secondary_client.cookies.update(authorized_client.cookies)
    sync_csrf_header(secondary_client)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            'iss': settings.jwt_issuer,
            'aud': settings.jwt_audience,
            'sub': '7777',
            'user_id': 7777,
            'family_id': family_id,
            'family_role': 'student_viewer',
            'student_id': student_id,
            'email': 'student-bearer@example.com',
            'name': 'Student Bearer',
            'roles': ['Student'],
            'iat': int(now.timestamp()),
            'nbf': int((now - timedelta(seconds=30)).timestamp()),
            'exp': int((now + timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await secondary_client.get(BACKUPS['config'], headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 403, response.text
