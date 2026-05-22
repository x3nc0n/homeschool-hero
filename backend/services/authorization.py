from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from backend.models import FamilyRole
from backend.security import AuthSession, get_auth_session
from backend.services.rbac import AppRole, Capability, expand_capability_aliases, normalize_app_role_names


_APP_ROLE_IMPLICATIONS: dict[AppRole, set[AppRole]] = {
    AppRole.admin: {AppRole.admin, AppRole.teacher, AppRole.student},
    AppRole.teacher: {AppRole.teacher},
    AppRole.student: {AppRole.student},
}


def role_from_auth(auth: AuthSession) -> FamilyRole:
    return FamilyRole(auth.family_role)


def has_capability(auth: AuthSession, capability: Capability) -> bool:
    required_capabilities = expand_capability_aliases(capability)
    return any(required.value in auth.effective_capabilities for required in required_capabilities)


def has_app_role(auth: AuthSession, app_role: AppRole) -> bool:
    normalized_roles = normalize_app_role_names(auth.app_roles)
    return any(app_role in _APP_ROLE_IMPLICATIONS[assigned_role] for assigned_role in normalized_roles)


def require_any_role(*roles: str | AppRole, action: str = 'access this resource') -> Callable[[AuthSession], AuthSession]:
    normalized_roles = normalize_app_role_names(roles)
    if not normalized_roles:
        raise ValueError('require_any_role requires at least one application role')

    async def dependency(auth: AuthSession = Depends(get_auth_session)) -> AuthSession:
        if not any(has_app_role(auth, role) for role in normalized_roles):
            expected = ', '.join(role.value for role in normalized_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"App roles '{', '.join(auth.app_roles) or 'none'}' are not allowed to {action}; expected one of: {expected}.",
            )
        return auth

    return dependency


def require_admin(*, action: str = 'access admin resources') -> Callable[[AuthSession], AuthSession]:
    return require_any_role(AppRole.admin, action=action)


def require_teacher(*, action: str = 'access teacher resources') -> Callable[[AuthSession], AuthSession]:
    return require_any_role(AppRole.teacher, action=action)


def require_student(*, action: str = 'access student resources') -> Callable[[AuthSession], AuthSession]:
    return require_any_role(AppRole.student, action=action)


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
