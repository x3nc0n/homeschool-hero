from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from backend.models import FamilyRole


class Capability(str, Enum):
    manage_family = 'manage_family'
    manage_household = 'manage_household'
    manage_platform = 'manage_platform'
    manage_curriculum = 'manage_curriculum'
    manage_submissions = 'manage_submissions'
    manage_grading = 'manage_grading'
    manage_invitations = 'manage_invitations'
    manage_security = 'manage_security'
    read_students = 'read_students'
    read_curriculum = 'read_curriculum'
    read_submissions = 'read_submissions'
    read_grades = 'read_grades'


class AppRole(str, Enum):
    admin = 'admin'
    teacher = 'teacher'
    student = 'student'


_APP_ROLE_ORDER = (AppRole.admin, AppRole.teacher, AppRole.student)

_READ_CAPABILITIES = {
    Capability.read_students,
    Capability.read_curriculum,
    Capability.read_submissions,
    Capability.read_grades,
}

_TEACHER_CAPABILITIES = {
    Capability.manage_household,
    Capability.manage_curriculum,
    Capability.manage_submissions,
    Capability.manage_grading,
    Capability.manage_invitations,
    *_READ_CAPABILITIES,
}

_ROLE_CAPABILITIES: dict[FamilyRole, set[Capability]] = {
    FamilyRole.parent: {
        Capability.manage_family,
        Capability.manage_household,
        Capability.manage_platform,
        Capability.manage_curriculum,
        Capability.manage_submissions,
        Capability.manage_grading,
        Capability.manage_invitations,
        Capability.manage_security,
        *_READ_CAPABILITIES,
    },
    FamilyRole.co_parent: {
        Capability.manage_family,
        Capability.manage_household,
        Capability.manage_platform,
        Capability.manage_curriculum,
        Capability.manage_submissions,
        Capability.manage_grading,
        Capability.manage_invitations,
        *_READ_CAPABILITIES,
    },
    FamilyRole.tutor: {
        Capability.manage_curriculum,
        Capability.manage_submissions,
        Capability.manage_grading,
        *_READ_CAPABILITIES,
    },
    FamilyRole.student_viewer: set(_READ_CAPABILITIES),
}

_FAMILY_ROLE_CAPABILITIES: dict[FamilyRole, set[Capability]] = {
    FamilyRole.parent: {
        Capability.manage_household,
        Capability.manage_curriculum,
        Capability.manage_submissions,
        Capability.manage_grading,
        Capability.manage_invitations,
        *_READ_CAPABILITIES,
    },
    FamilyRole.co_parent: {
        Capability.manage_household,
        Capability.manage_curriculum,
        Capability.manage_submissions,
        Capability.manage_grading,
        Capability.manage_invitations,
        *_READ_CAPABILITIES,
    },
    FamilyRole.tutor: {
        Capability.manage_curriculum,
        Capability.manage_submissions,
        Capability.manage_grading,
        *_READ_CAPABILITIES,
    },
    FamilyRole.student_viewer: set(_READ_CAPABILITIES),
}

_APP_ROLE_CAPABILITIES: dict[AppRole, set[Capability]] = {
    AppRole.admin: {Capability.manage_platform},
    AppRole.teacher: set(_TEACHER_CAPABILITIES),
    AppRole.student: set(_READ_CAPABILITIES),
}

_FAMILY_SCOPED_CAPABILITIES = {
    Capability.manage_household,
    Capability.manage_curriculum,
    Capability.manage_submissions,
    Capability.manage_grading,
    Capability.manage_invitations,
    *_READ_CAPABILITIES,
}

_APP_AXIS_ONLY_CAPABILITIES = {Capability.manage_platform}
_FAMILY_AXIS_ONLY_CAPABILITIES = {Capability.manage_security}
_COMPATIBILITY_ALIASES: dict[Capability, set[Capability]] = {
    Capability.manage_family: {
        Capability.manage_family,
        Capability.manage_household,
        Capability.manage_platform,
    }
}


def parse_mapping_csv(raw_value: str | None) -> set[str]:
    return {item.strip().casefold() for item in (raw_value or '').split(',') if item.strip()}


def synthesize_app_roles(family_role: FamilyRole) -> list[AppRole]:
    if family_role in {FamilyRole.parent, FamilyRole.co_parent}:
        return [AppRole.admin, AppRole.teacher]
    if family_role is FamilyRole.tutor:
        return [AppRole.teacher]
    return [AppRole.student]


def normalize_app_role_names(app_roles: Iterable[str | AppRole]) -> list[AppRole]:
    normalized: list[AppRole] = []
    seen: set[AppRole] = set()
    for app_role in app_roles:
        candidate = app_role if isinstance(app_role, AppRole) else AppRole(str(app_role).strip().lower())
        if candidate not in seen:
            normalized.append(candidate)
            seen.add(candidate)
    normalized.sort(key=_APP_ROLE_ORDER.index)
    return normalized


def normalize_external_app_roles(
    external_roles: Iterable[str],
    *,
    external_role_mappings: dict[str, str],
) -> list[AppRole]:
    resolved: list[AppRole] = []
    seen: set[AppRole] = set()
    for external_role in external_roles:
        candidate = external_role.strip().casefold()
        if not candidate:
            continue
        app_role_name = external_role_mappings.get(candidate)
        if app_role_name is None:
            continue
        app_role = AppRole(app_role_name)
        if app_role not in seen:
            resolved.append(app_role)
            seen.add(app_role)
    resolved.sort(key=_APP_ROLE_ORDER.index)
    return resolved


def capability_names(capabilities: Iterable[Capability]) -> set[str]:
    return {capability.value for capability in capabilities}


def expand_capability_aliases(capability: Capability) -> set[Capability]:
    return _COMPATIBILITY_ALIASES.get(capability, {capability})


def derive_effective_capabilities(
    *,
    family_role: FamilyRole,
    app_roles: Iterable[AppRole],
    is_owner: bool,
) -> set[Capability]:
    normalized_app_roles = normalize_app_role_names(app_roles)
    family_capabilities = set(_FAMILY_ROLE_CAPABILITIES[family_role])
    if is_owner and family_role is FamilyRole.parent:
        family_capabilities.add(Capability.manage_security)

    app_capabilities: set[Capability] = set()
    for app_role in normalized_app_roles:
        app_capabilities.update(_APP_ROLE_CAPABILITIES[app_role])

    effective = (family_capabilities & app_capabilities & _FAMILY_SCOPED_CAPABILITIES)
    effective.update(app_capabilities & _APP_AXIS_ONLY_CAPABILITIES)
    effective.update(family_capabilities & _FAMILY_AXIS_ONLY_CAPABILITIES)
    return effective


def validate_app_role_assignment(*, family_role: FamilyRole, app_roles: Iterable[AppRole]) -> None:
    normalized_app_roles = normalize_app_role_names(app_roles)
    if (
        AppRole.student in normalized_app_roles
        and family_role is not FamilyRole.student_viewer
        and AppRole.teacher not in normalized_app_roles
        and AppRole.admin not in normalized_app_roles
    ):
        raise ValueError(
            f"App role '{AppRole.student.value}' is not compatible with family role '{family_role.value}'."
        )
