from __future__ import annotations

from collections.abc import Callable
import logging

from fastapi import Depends, HTTPException, Request, status

from backend.models import FamilyRole
from backend.security import AuthSession, get_auth_session
from backend.services.rbac import AppRole, Capability, expand_capability_aliases, normalize_app_role_names
from backend.services.security_events import emit_rbac_denial

logger = logging.getLogger(__name__)


def _forbidden(
    *,
    request: Request | None,
    auth: AuthSession,
    action: str,
    detail: str,
    reason: str,
    details: dict[str, object] | None = None,
) -> HTTPException:
    emit_rbac_denial(logger, request=request, auth=auth, action=action, reason=reason, details=details)
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


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

    async def dependency(request: Request, auth: AuthSession = Depends(get_auth_session)) -> AuthSession:
        if not any(has_app_role(auth, role) for role in normalized_roles):
            expected = ', '.join(role.value for role in normalized_roles)
            raise _forbidden(
                request=request,
                auth=auth,
                action=action,
                reason='missing_app_role',
                detail=f"App roles '{', '.join(auth.app_roles) or 'none'}' are not allowed to {action}; expected one of: {expected}.",
                details={
                    'assigned_app_roles': list(auth.app_roles),
                    'expected_app_roles': [role.value for role in normalized_roles],
                },
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
    async def dependency(request: Request, auth: AuthSession = Depends(get_auth_session)) -> AuthSession:
        missing = [capability for capability in capabilities if not has_capability(auth, capability)]
        if missing:
            raise _forbidden(
                request=request,
                auth=auth,
                action=action,
                reason='missing_capability',
                detail=f"Role '{auth.role}' is not allowed to {action}.",
                details={'missing_capabilities': [capability.value for capability in missing]},
            )
        return auth

    return dependency


def ensure_student_scope(auth: AuthSession, student_id: int, *, action: str, request: Request | None = None) -> None:
    if auth.family_role != FamilyRole.student_viewer.value:
        return
    if auth.student_id is None:
        raise _forbidden(
            request=request,
            auth=auth,
            action=action,
            reason='missing_student_scope',
            detail='Student viewer access is not linked to a student record.',
        )
    if auth.student_id != student_id:
        raise _forbidden(
            request=request,
            auth=auth,
            action=action,
            reason='student_scope_mismatch',
            detail=f"Role '{auth.role}' is not allowed to {action} for another student.",
            details={'requested_student_id': student_id, 'authorized_student_id': auth.student_id},
        )


def get_student_scope_id(auth: AuthSession, request: Request | None = None) -> int:
    if auth.family_role != FamilyRole.student_viewer.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Student scope is not required for this role')
    if auth.student_id is None:
        raise _forbidden(
            request=request,
            auth=auth,
            action='resolve student scope',
            reason='missing_student_scope',
            detail='Student viewer access is not linked to a student record.',
        )
    return auth.student_id
