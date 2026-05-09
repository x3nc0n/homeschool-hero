from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from fastapi import Depends, HTTPException, status

from backend.models import FamilyRole
from backend.security import AuthSession, get_auth_session


class Capability(str, Enum):
    manage_family = 'manage_family'
    manage_curriculum = 'manage_curriculum'
    manage_submissions = 'manage_submissions'
    manage_grading = 'manage_grading'
    manage_invitations = 'manage_invitations'
    manage_security = 'manage_security'
    read_students = 'read_students'
    read_curriculum = 'read_curriculum'
    read_submissions = 'read_submissions'
    read_grades = 'read_grades'


_ROLE_CAPABILITIES: dict[FamilyRole, set[Capability]] = {
    FamilyRole.parent: set(Capability),
    FamilyRole.co_parent: {
        Capability.manage_family,
        Capability.manage_curriculum,
        Capability.manage_submissions,
        Capability.manage_grading,
        Capability.manage_invitations,
        Capability.read_students,
        Capability.read_curriculum,
        Capability.read_submissions,
        Capability.read_grades,
    },
    FamilyRole.tutor: {
        Capability.manage_curriculum,
        Capability.manage_submissions,
        Capability.manage_grading,
        Capability.read_students,
        Capability.read_curriculum,
        Capability.read_submissions,
        Capability.read_grades,
    },
    FamilyRole.student_viewer: {
        Capability.read_students,
        Capability.read_curriculum,
        Capability.read_submissions,
        Capability.read_grades,
    },
}


def role_from_auth(auth: AuthSession) -> FamilyRole:
    return FamilyRole(auth.role)


def has_capability(auth: AuthSession, capability: Capability) -> bool:
    return capability in _ROLE_CAPABILITIES[role_from_auth(auth)]


def require_capabilities(*capabilities: Capability, action: str) -> Callable[[AuthSession], AuthSession]:
    async def dependency(auth: AuthSession = Depends(get_auth_session)) -> AuthSession:
        missing = [capability for capability in capabilities if not has_capability(auth, capability)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' is not allowed to {action}.",
            )
        return auth

    return dependency


def ensure_student_scope(auth: AuthSession, student_id: int, *, action: str) -> None:
    if auth.role != FamilyRole.student_viewer.value:
        return
    if auth.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Student viewer access is not linked to a student record.',
        )
    if auth.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{auth.role}' is not allowed to {action} for another student.",
        )


def get_student_scope_id(auth: AuthSession) -> int:
    if auth.role != FamilyRole.student_viewer.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Student scope is not required for this role')
    if auth.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Student viewer access is not linked to a student record.',
        )
    return auth.student_id
