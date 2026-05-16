from __future__ import annotations

import pytest

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import FamilyRole
from backend.services import rbac as rbac_service
from backend.services.auth_provisioning import ExternalIdentity, provision_external_identity
from backend.services.rbac import AppRole

_ROLE_DERIVATION_AVAILABLE = hasattr(rbac_service, 'derive_family_role_from_app_roles')
_PENDING_ROLE_DERIVATION_REASON = 'Issue #112 role derivation helper is not implemented yet.'


def _set_auto_provision_settings(monkeypatch, *, family_name: str) -> None:
    monkeypatch.setattr(settings, 'auth_auto_provision_mode', 'default_family', raising=False)
    monkeypatch.setattr(settings, 'auth_default_family_name', family_name, raising=False)


async def _provision_identity(*, email: str, external_id: str, display_name: str, roles: tuple[str, ...] = ()):
    async with AsyncSessionLocal() as db:
        return await provision_external_identity(
            db,
            ExternalIdentity(
                provider='oidc',
                external_id=external_id,
                email=email,
                display_name=display_name,
                roles=roles,
            ),
        )


def test_admin_role_maps_to_parent() -> None:
    assert rbac_service.derive_family_role_from_app_roles([AppRole.admin]) is FamilyRole.parent


def test_teacher_role_maps_to_tutor() -> None:
    assert rbac_service.derive_family_role_from_app_roles([AppRole.teacher]) is FamilyRole.tutor


def test_student_role_maps_to_student_viewer() -> None:
    assert rbac_service.derive_family_role_from_app_roles([AppRole.student]) is FamilyRole.student_viewer


def test_empty_roles_fallback_to_student_viewer() -> None:
    assert rbac_service.derive_family_role_from_app_roles([]) is FamilyRole.student_viewer


def test_multiple_roles_highest_wins() -> None:
    assert rbac_service.derive_family_role_from_app_roles([AppRole.admin, AppRole.teacher]) is FamilyRole.parent


def test_multiple_roles_teacher_student() -> None:
    assert rbac_service.derive_family_role_from_app_roles([AppRole.teacher, AppRole.student]) is FamilyRole.tutor


@pytest.mark.skipif(not _ROLE_DERIVATION_AVAILABLE, reason=_PENDING_ROLE_DERIVATION_REASON)
class TestProvisionExternalIdentityRoleDerivation:
    @pytest.mark.asyncio
    async def test_provision_admin_gets_parent_non_owner(self, monkeypatch):
        _set_auto_provision_settings(monkeypatch, family_name='OIDC Admin Family')

        provisioned = await _provision_identity(
            email='oidc-admin@example.com',
            external_id='oidc-admin-1',
            display_name='OIDC Admin',
            roles=('admin',),
        )

        assert provisioned.created_default_family_membership is True
        assert provisioned.membership.role is FamilyRole.parent
        assert provisioned.membership.is_owner is False

    @pytest.mark.asyncio
    async def test_provision_teacher_gets_tutor(self, monkeypatch, create_family_user):
        family_name = 'OIDC Teacher Family'
        _set_auto_provision_settings(monkeypatch, family_name=family_name)
        await create_family_user(
            family_name=family_name,
            email='family-owner@example.com',
            password='strongpass-owner',
            display_name='Family Owner',
            role=FamilyRole.parent.value,
            is_owner=True,
        )

        provisioned = await _provision_identity(
            email='oidc-teacher@example.com',
            external_id='oidc-teacher-1',
            display_name='OIDC Teacher',
            roles=('teacher',),
        )

        assert provisioned.created_default_family_membership is True
        assert provisioned.membership.role is FamilyRole.tutor
        assert provisioned.membership.is_owner is False

    @pytest.mark.asyncio
    async def test_provision_student_gets_student_viewer(self, monkeypatch, create_family_user):
        family_name = 'OIDC Student Family'
        _set_auto_provision_settings(monkeypatch, family_name=family_name)
        await create_family_user(
            family_name=family_name,
            email='family-owner@example.com',
            password='strongpass-owner',
            display_name='Family Owner',
            role=FamilyRole.parent.value,
            is_owner=True,
        )

        provisioned = await _provision_identity(
            email='oidc-student@example.com',
            external_id='oidc-student-1',
            display_name='OIDC Student',
            roles=('student',),
        )

        assert provisioned.created_default_family_membership is True
        assert provisioned.membership.role is FamilyRole.student_viewer
        assert provisioned.membership.student_id is None
        assert provisioned.membership.is_owner is False

    @pytest.mark.asyncio
    async def test_provision_no_roles_gets_student_viewer_fallback(self, monkeypatch, create_family_user):
        family_name = 'OIDC No Roles Family'
        _set_auto_provision_settings(monkeypatch, family_name=family_name)
        await create_family_user(
            family_name=family_name,
            email='family-owner@example.com',
            password='strongpass-owner',
            display_name='Family Owner',
            role=FamilyRole.parent.value,
            is_owner=True,
        )

        provisioned = await _provision_identity(
            email='oidc-no-roles@example.com',
            external_id='oidc-no-roles-1',
            display_name='OIDC No Roles',
        )

        assert provisioned.created_default_family_membership is True
        assert provisioned.membership.role is FamilyRole.student_viewer
        assert provisioned.membership.student_id is None
        assert provisioned.membership.is_owner is False

    @pytest.mark.asyncio
    async def test_auto_provisioned_never_owner(self, monkeypatch, create_family_user):
        family_name = 'OIDC Existing Owner Family'
        _set_auto_provision_settings(monkeypatch, family_name=family_name)
        await create_family_user(
            family_name=family_name,
            email='existing-owner@example.com',
            password='strongpass-owner',
            display_name='Existing Owner',
            role=FamilyRole.parent.value,
            is_owner=True,
        )

        provisioned = await _provision_identity(
            email='oidc-admin-second@example.com',
            external_id='oidc-admin-2',
            display_name='OIDC Admin Two',
            roles=('admin',),
        )

        assert provisioned.created_default_family_membership is True
        assert provisioned.membership.role is FamilyRole.parent
        assert provisioned.membership.is_owner is False

    @pytest.mark.asyncio
    async def test_provision_existing_membership_unchanged(self, monkeypatch, create_family_user):
        _set_auto_provision_settings(monkeypatch, family_name='OIDC Existing Membership Family')
        existing_user = await create_family_user(
            family_name='Existing Membership Family',
            email='existing-membership@example.com',
            password='strongpass-existing',
            display_name='Existing Membership',
            role=FamilyRole.co_parent.value,
            is_owner=False,
        )

        provisioned = await _provision_identity(
            email='existing-membership@example.com',
            external_id='oidc-existing-membership-1',
            display_name='Existing Membership',
            roles=('admin',),
        )

        assert provisioned.created_default_family_membership is False
        assert provisioned.user.id == existing_user['user_id']
        assert provisioned.membership.role is FamilyRole.co_parent
        assert provisioned.membership.is_owner is False

    @pytest.mark.asyncio
    async def test_unmapped_roles_get_least_privilege(self, monkeypatch, create_family_user):
        family_name = 'OIDC Unmapped Roles Family'
        _set_auto_provision_settings(monkeypatch, family_name=family_name)
        await create_family_user(
            family_name=family_name,
            email='family-owner@example.com',
            password='strongpass-owner',
            display_name='Family Owner',
            role=FamilyRole.parent.value,
            is_owner=True,
        )

        provisioned = await _provision_identity(
            email='oidc-unmapped@example.com',
            external_id='oidc-unmapped-1',
            display_name='OIDC Unmapped',
            roles=('district-admin',),
        )

        assert provisioned.created_default_family_membership is True
        assert provisioned.membership.role is FamilyRole.student_viewer
        assert provisioned.membership.student_id is None
        assert provisioned.membership.is_owner is False
