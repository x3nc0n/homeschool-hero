from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.models import AuditEvent, Family, FamilyMembership, FamilyRole, ScimGroup, User
from backend.rate_limit import RateLimitRule
from backend.database import AsyncSessionLocal

SCIM_BASE = '/scim/v2'


def _enable_scim(monkeypatch, *, token: str = 'test-scim-token') -> dict[str, str]:
    monkeypatch.setattr('backend.config.settings.scim_enabled', True, raising=False)
    monkeypatch.setattr('backend.config.settings.scim_bearer_token', token, raising=False)
    monkeypatch.setattr('backend.config.settings.auth_default_family_name', 'Entra Provisioned Family', raising=False)
    return {'Authorization': f'Bearer {token}'}


@pytest.mark.asyncio
async def test_scim_requires_feature_flag_and_bearer_token(async_client, monkeypatch):
    response = await async_client.get(f'{SCIM_BASE}/ServiceProviderConfig')
    assert response.status_code == 404, response.text
    assert response.json()['schemas'] == ['urn:ietf:params:scim:api:messages:2.0:Error']

    headers = _enable_scim(monkeypatch)
    missing_token = await async_client.get(f'{SCIM_BASE}/ServiceProviderConfig')
    assert missing_token.status_code == 401, missing_token.text
    assert missing_token.headers['www-authenticate'] == 'Bearer realm="scim"'

    ok = await async_client.get(f'{SCIM_BASE}/ServiceProviderConfig', headers=headers)
    assert ok.status_code == 200, ok.text
    assert ok.headers['content-type'].startswith('application/scim+json')
    assert ok.json()['patch']['supported'] is True


@pytest.mark.asyncio
async def test_scim_user_crud_filtering_pagination_and_audit(async_client, monkeypatch):
    headers = _enable_scim(monkeypatch)

    created = await async_client.post(
        f'{SCIM_BASE}/Users',
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
            'userName': 'learner@example.com',
            'displayName': 'Learner One',
            'active': True,
            'externalId': 'entra-user-1',
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()
    assert user['userName'] == 'learner@example.com'
    assert user['externalId'] == 'entra-user-1'
    assert user['active'] is True
    assert created.headers['content-type'].startswith('application/scim+json')

    conflict = await async_client.post(
        f'{SCIM_BASE}/Users',
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
            'userName': 'learner@example.com',
            'displayName': 'Duplicate User',
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()['scimType'] == 'uniqueness'

    created_two = await async_client.post(
        f'{SCIM_BASE}/Users',
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
            'userName': 'teacher@example.com',
            'displayName': 'Teacher Two',
            'active': False,
            'externalId': 'entra-user-2',
        },
    )
    assert created_two.status_code == 201, created_two.text

    filtered = await async_client.get(
        f'{SCIM_BASE}/Users',
        headers=headers,
        params={'filter': 'userName eq "learner@example.com"'},
    )
    assert filtered.status_code == 200, filtered.text
    payload = filtered.json()
    assert payload['totalResults'] == 1
    assert payload['Resources'][0]['id'] == user['id']

    paged = await async_client.get(
        f'{SCIM_BASE}/Users',
        headers=headers,
        params={'startIndex': 2, 'count': 1},
    )
    assert paged.status_code == 200, paged.text
    assert paged.json()['totalResults'] == 2
    assert paged.json()['itemsPerPage'] == 1

    patched = await async_client.patch(
        f"{SCIM_BASE}/Users/{user['id']}",
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [
                {'op': 'Replace', 'path': 'displayName', 'value': 'Learner Prime'},
                {'op': 'Replace', 'path': 'active', 'value': False},
            ],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()['displayName'] == 'Learner Prime'
    assert patched.json()['active'] is False

    invalid_filter = await async_client.get(
        f'{SCIM_BASE}/Users',
        headers=headers,
        params={'filter': 'userName co "learner"'},
    )
    assert invalid_filter.status_code == 400, invalid_filter.text
    assert invalid_filter.json()['scimType'] == 'invalidFilter'

    deleted = await async_client.delete(f"{SCIM_BASE}/Users/{user['id']}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    async with AsyncSessionLocal() as session:
        stored_user = await session.get(User, int(user['id']))
        assert stored_user is not None
        assert stored_user.scim_external_id == 'entra-user-1'
        assert stored_user.is_active is False

        membership = (
            await session.execute(
                select(FamilyMembership).where(FamilyMembership.user_id == stored_user.id)
            )
        ).scalar_one()
        assert membership.role is FamilyRole.student_viewer

        audit_events = list(
            (
                await session.execute(
                    select(AuditEvent).where(AuditEvent.target_entity_type == 'scim_user').order_by(AuditEvent.id)
                )
            ).scalars()
        )
        assert len(audit_events) == 4


@pytest.mark.asyncio
async def test_scim_can_link_existing_user_to_default_family(create_family_user, async_client, monkeypatch):
    existing = await create_family_user(
        family_name='Local Family',
        email='existing@example.com',
        password='StrongPassword123!',
        display_name='Existing User',
        role='parent',
    )
    headers = _enable_scim(monkeypatch)

    filtered = await async_client.get(
        f'{SCIM_BASE}/Users',
        headers=headers,
        params={'filter': 'userName eq "existing@example.com"'},
    )
    assert filtered.status_code == 200, filtered.text
    resource = filtered.json()['Resources'][0]
    assert resource['id'] == str(existing['user_id'])

    linked = await async_client.patch(
        f"{SCIM_BASE}/Users/{existing['user_id']}",
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [
                {'op': 'Replace', 'path': 'externalId', 'value': 'entra-linked-user'},
            ],
        },
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()['externalId'] == 'entra-linked-user'

    async with AsyncSessionLocal() as session:
        default_family = (
            await session.execute(select(Family).where(Family.name == 'Entra Provisioned Family'))
        ).scalar_one()
        default_membership = (
            await session.execute(
                select(FamilyMembership).where(
                    FamilyMembership.user_id == existing['user_id'],
                    FamilyMembership.family_id == default_family.id,
                )
            )
        ).scalar_one()
        user = await session.get(User, existing['user_id'])
        assert user is not None
        assert user.scim_external_id == 'entra-linked-user'
        assert default_membership.role is FamilyRole.student_viewer


@pytest.mark.asyncio
async def test_scim_group_crud_maps_roles_and_reverts_removed_members(async_client, monkeypatch):
    headers = _enable_scim(monkeypatch)

    user_one = (
        await async_client.post(
            f'{SCIM_BASE}/Users',
            headers=headers,
            json={
                'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
                'userName': 'parent@example.com',
                'displayName': 'Parent User',
                'externalId': 'entra-parent',
            },
        )
    ).json()
    user_two = (
        await async_client.post(
            f'{SCIM_BASE}/Users',
            headers=headers,
            json={
                'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
                'userName': 'tutor@example.com',
                'displayName': 'Tutor User',
                'externalId': 'entra-tutor',
            },
        )
    ).json()

    created_group = await async_client.post(
        f'{SCIM_BASE}/Groups',
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:Group'],
            'displayName': 'Admin',
            'externalId': 'entra-group-1',
            'members': [{'value': user_one['id']}],
        },
    )
    assert created_group.status_code == 201, created_group.text
    group = created_group.json()
    assert group['displayName'] == 'Admin'
    assert group['members'][0]['value'] == user_one['id']

    add_member = await async_client.patch(
        f"{SCIM_BASE}/Groups/{group['id']}",
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [
                {'op': 'Add', 'path': 'members', 'value': [{'value': user_two['id']}]},
            ],
        },
    )
    assert add_member.status_code == 200, add_member.text
    assert {member['value'] for member in add_member.json()['members']} == {user_one['id'], user_two['id']}

    remapped_role = await async_client.patch(
        f"{SCIM_BASE}/Groups/{group['id']}",
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [
                {'op': 'Replace', 'path': 'displayName', 'value': 'Teacher'},
            ],
        },
    )
    assert remapped_role.status_code == 200, remapped_role.text
    assert remapped_role.json()['displayName'] == 'Teacher'

    removed_one = await async_client.patch(
        f"{SCIM_BASE}/Groups/{group['id']}",
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [
                {'op': 'Remove', 'path': f'members[value eq "{user_one["id"]}"]'},
            ],
        },
    )
    assert removed_one.status_code == 200, removed_one.text
    assert [member['value'] for member in removed_one.json()['members']] == [user_two['id']]

    deleted_group = await async_client.delete(f"{SCIM_BASE}/Groups/{group['id']}", headers=headers)
    assert deleted_group.status_code == 204, deleted_group.text

    async with AsyncSessionLocal() as session:
        memberships = {
            membership.user_id: membership.role
            for membership in (
                await session.execute(
                    select(FamilyMembership).where(FamilyMembership.user_id.in_([int(user_one['id']), int(user_two['id'])]))
                )
            ).scalars()
        }
        assert memberships[int(user_one['id'])] is FamilyRole.student_viewer
        assert memberships[int(user_two['id'])] is FamilyRole.student_viewer
        assert (
            await session.execute(select(ScimGroup).where(ScimGroup.external_id == 'entra-group-1'))
        ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_scim_rejects_owner_role_mutation(create_family_user, async_client, monkeypatch):
    owner = await create_family_user(
        family_name='Entra Provisioned Family',
        email='owner-managed@example.com',
        password='StrongPassword123!',
        display_name='Owner Managed',
        role='parent',
        is_owner=True,
    )
    headers = _enable_scim(monkeypatch)

    group = await async_client.post(
        f'{SCIM_BASE}/Groups',
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:schemas:core:2.0:Group'],
            'displayName': 'Teacher',
            'externalId': 'entra-owner-group',
        },
    )
    assert group.status_code == 201, group.text

    blocked = await async_client.patch(
        f"{SCIM_BASE}/Groups/{group.json()['id']}",
        headers=headers,
        json={
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:PatchOp'],
            'Operations': [
                {'op': 'Add', 'path': 'members', 'value': [{'value': str(owner['user_id'])}]},
            ],
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()['scimType'] == 'mutability'


@pytest.mark.asyncio
async def test_scim_rate_limit_returns_429(async_client, monkeypatch):
    headers = _enable_scim(monkeypatch)
    monkeypatch.setattr('backend.routers.scim.SCIM_RATE_LIMIT', RateLimitRule('scim', 2, 60))

    for attempt in range(1, 4):
        response = await async_client.get(f'{SCIM_BASE}/ServiceProviderConfig', headers=headers)
        if attempt <= 2:
            assert response.status_code == 200, response.text
        else:
            assert response.status_code == 429, response.text
            assert response.json()['schemas'] == ['urn:ietf:params:scim:api:messages:2.0:Error']
            assert int(response.headers['retry-after']) >= 1
