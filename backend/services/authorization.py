from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from backend.models import FamilyRole
from backend.security import AuthSession, get_auth_session
from backend.services.rbac import Capability, _ROLE_CAPABILITIES, expand_capability_aliases


def role_from_auth(auth: AuthSession) -> FamilyRole:
    return FamilyRole(auth.family_role)


def has_capability(auth: AuthSession, capability: Capability) -> bool:
    required_capabilities = expand_capability_aliases(capability)
    return any(required.value in auth.effective_capabilities for required in required_capabilities)


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
    if auth.family_role != FamilyRole.student_viewer.value:
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
    if auth.family_role != FamilyRole.student_viewer.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Student scope is not required for this role')
    if auth.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Student viewer access is not linked to a student record.',
        )
    return auth.student_id
