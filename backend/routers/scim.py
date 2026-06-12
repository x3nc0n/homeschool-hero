from __future__ import annotations

import secrets
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import AuditAction, FamilyMembership, FamilyRole, ScimGroup, User
from backend.rate_limit import RateLimitRule
from backend.security import get_request_ip, hash_password, normalize_email
from backend.services.audit import log_event
from backend.services.auth_provisioning import ensure_default_family
from backend.services.rbac import derive_family_role_from_app_roles, normalize_external_app_roles

SCIM_BASE_PATH = '/scim/v2'
SCIM_LIST_RESPONSE_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:ListResponse'
SCIM_ERROR_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:Error'
SCIM_PATCH_OP_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:PatchOp'
SCIM_RESOURCE_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:ResourceType'
SCIM_SCHEMA_DEFINITION = 'urn:ietf:params:scim:schemas:core:2.0:Schema'
SCIM_SERVICE_PROVIDER_CONFIG = 'urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig'
SCIM_USER_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:User'
SCIM_GROUP_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Group'
SCIM_RATE_LIMIT = RateLimitRule('scim', 60, 60)
SCIM_SYSTEM_EMAIL = 'scim-provisioner@homeschool-hero.local'
DEFAULT_SCIM_ROLE = FamilyRole.student_viewer
_FILTER_RE = re.compile(r'^\s*([A-Za-z][\w.:-]*)\s+eq\s+"([^"]+)"\s*$')
_MEMBER_FILTER_RE = re.compile(r'^members\[value\s+eq\s+"([^"]+)"\]$', re.IGNORECASE)

class ScimJSONResponse(JSONResponse):
    media_type = 'application/scim+json'


router = APIRouter(prefix=SCIM_BASE_PATH, tags=['scim'], default_response_class=ScimJSONResponse)


class ScimError(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        scim_type: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.scim_type = scim_type
        self.headers = headers or {}


def build_scim_error_response(
    request: Request,
    *,
    status_code: int,
    detail: str,
    scim_type: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        'schemas': [SCIM_ERROR_SCHEMA],
        'detail': detail,
        'status': str(status_code),
    }
    if scim_type:
        payload['scimType'] = scim_type
    return ScimJSONResponse(status_code=status_code, content=payload, headers=headers)


async def authorize_scim_request(request: Request) -> None:
    if not settings.scim_enabled:
        raise ScimError(status.HTTP_404_NOT_FOUND, 'SCIM is disabled for this deployment.')

    expected_token = (settings.scim_bearer_token or '').strip()
    auth_header = request.headers.get('authorization', '')
    scheme, _, token = auth_header.partition(' ')
    if scheme.lower() != 'bearer' or not token or not secrets.compare_digest(token.strip(), expected_token):
        raise ScimError(
            status.HTTP_401_UNAUTHORIZED,
            'A valid SCIM bearer token is required.',
            headers={'WWW-Authenticate': 'Bearer realm="scim"'},
        )

    allowed, retry_after = await request.app.state.rate_limiter.check(
        SCIM_RATE_LIMIT,
        f'ip:{get_request_ip(request)}',
    )
    if not allowed:
        raise ScimError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            'Too many SCIM requests. Please retry later.',
            headers={'Retry-After': str(retry_after)},
        )


router.dependencies.append(Depends(authorize_scim_request))


async def _get_scim_actor(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == SCIM_SYSTEM_EMAIL))
    actor = result.scalar_one_or_none()
    if actor is not None:
        return actor

    actor = User(
        email=SCIM_SYSTEM_EMAIL,
        display_name='SCIM Provisioner',
        password_hash=hash_password(secrets.token_urlsafe(32)),
        is_active=False,
        auth_provider='scim',
    )
    db.add(actor)
    await db.flush()
    return actor


async def _log_scim_change(
    db: AsyncSession,
    *,
    action: AuditAction,
    family_id: int,
    target_type: str,
    target_id: int | str | None,
    before: Any,
    after: Any,
    request: Request,
) -> None:
    await log_event(
        db,
        action=action,
        actor=await _get_scim_actor(db),
        family_id=family_id,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        request=request,
    )



def _absolute_url(request: Request, path: str) -> str:
    return f'{str(request.base_url).rstrip("/")}{path}'



def _utc_iso(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')



def _resource_meta(request: Request, *, resource_type: str, resource_id: int, created_at: datetime, updated_at: datetime) -> dict[str, str]:
    return {
        'resourceType': resource_type,
        'created': _utc_iso(created_at),
        'lastModified': _utc_iso(updated_at),
        'location': _absolute_url(request, f'{SCIM_BASE_PATH}/{resource_type}s/{resource_id}'),
    }



def _list_response(resources: list[dict[str, Any]], *, total_results: int, start_index: int) -> dict[str, Any]:
    return {
        'schemas': [SCIM_LIST_RESPONSE_SCHEMA],
        'totalResults': total_results,
        'startIndex': start_index,
        'itemsPerPage': len(resources),
        'Resources': resources,
    }



def _default_display_name(email: str) -> str:
    return email.split('@', 1)[0].replace('.', ' ').replace('_', ' ').title()



def _validate_schemas(payload: dict[str, Any], expected_schema: str) -> None:
    raw_schemas = payload.get('schemas')
    if raw_schemas is None:
        return
    if not isinstance(raw_schemas, list) or not all(isinstance(item, str) and item.strip() for item in raw_schemas):
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'schemas must be a non-empty array of URNs.', scim_type='invalidSyntax')
    if expected_schema not in raw_schemas:
        raise ScimError(status.HTTP_400_BAD_REQUEST, f'{expected_schema} must be declared in schemas.', scim_type='invalidSyntax')



def _parse_filter(raw_filter: str | None) -> tuple[str, str] | None:
    if raw_filter is None or not raw_filter.strip():
        return None
    match = _FILTER_RE.match(raw_filter)
    if match is None:
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'Only simple eq filters are supported.', scim_type='invalidFilter')
    return match.group(1), match.group(2)



def _parse_member_filter(path: str) -> str | None:
    match = _MEMBER_FILTER_RE.match(path.strip())
    return None if match is None else match.group(1)



def _normalize_pagination(start_index: int, count: int) -> tuple[int, int]:
    if start_index < 1:
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'startIndex must be greater than or equal to 1.', scim_type='invalidValue')
    if count < 0:
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'count must be greater than or equal to 0.', scim_type='invalidValue')
    return start_index, count



def _normalize_external_id(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'externalId must be a string.', scim_type='invalidValue')
    normalized = value.strip()
    return normalized or None



def _extract_email_value(raw_emails: Any) -> str | None:
    if raw_emails is None:
        return None
    if not isinstance(raw_emails, list):
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'emails must be an array.', scim_type='invalidValue')
    primary = None
    fallback = None
    for item in raw_emails:
        if not isinstance(item, dict):
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'emails entries must be objects.', scim_type='invalidValue')
        value = item.get('value')
        if not isinstance(value, str) or not value.strip():
            continue
        if fallback is None:
            fallback = value.strip()
        if item.get('primary') is True:
            primary = value.strip()
            break
    return primary or fallback



def _resolve_user_name(payload: dict[str, Any], *, required: bool) -> str | None:
    raw_user_name = payload.get('userName')
    candidate = raw_user_name if isinstance(raw_user_name, str) and raw_user_name.strip() else _extract_email_value(payload.get('emails'))
    if candidate is None:
        if required:
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'userName is required.', scim_type='invalidValue')
        return None
    return normalize_email(candidate)



def _resolve_display_name(payload: dict[str, Any], *, email: str) -> str:
    raw_display_name = payload.get('displayName')
    if isinstance(raw_display_name, str) and raw_display_name.strip():
        return raw_display_name.strip()
    raw_name = payload.get('name')
    if isinstance(raw_name, dict):
        formatted = raw_name.get('formatted')
        if isinstance(formatted, str) and formatted.strip():
            return formatted.strip()
    return _default_display_name(email)



def _ensure_int_id(resource_id: str, *, resource_type: str) -> int:
    try:
        return int(resource_id)
    except ValueError as exc:
        raise ScimError(status.HTTP_404_NOT_FOUND, f'{resource_type} not found.') from exc



def _managed_user_predicate() -> Any:
    return and_(User.email != SCIM_SYSTEM_EMAIL, or_(User.scim_external_id.is_not(None), User.auth_provider == 'scim'))


async def _get_user_or_404(db: AsyncSession, resource_id: str) -> User:
    user = await db.get(User, _ensure_int_id(resource_id, resource_type='User'))
    if user is None:
        raise ScimError(status.HTTP_404_NOT_FOUND, 'User not found.')
    return user


async def _get_group_or_404(db: AsyncSession, resource_id: str) -> ScimGroup:
    group = await db.get(ScimGroup, _ensure_int_id(resource_id, resource_type='Group'))
    if group is None:
        raise ScimError(status.HTTP_404_NOT_FOUND, 'Group not found.')
    return group


async def _ensure_unique_user_name(db: AsyncSession, *, user_name: str, exclude_user_id: int | None = None) -> None:
    stmt = select(User.id).where(func.lower(User.email) == user_name.casefold())
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise ScimError(status.HTTP_409_CONFLICT, 'userName already exists.', scim_type='uniqueness')


async def _ensure_unique_scim_external_id(
    db: AsyncSession,
    *,
    external_id: str | None,
    exclude_user_id: int | None = None,
) -> None:
    if external_id is None:
        return
    stmt = select(User.id).where(User.scim_external_id == external_id)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise ScimError(status.HTTP_409_CONFLICT, 'externalId already exists.', scim_type='uniqueness')


async def _get_default_membership(db: AsyncSession, *, user_id: int, family_id: int) -> FamilyMembership | None:
    result = await db.execute(
        select(FamilyMembership).where(
            FamilyMembership.user_id == user_id,
            FamilyMembership.family_id == family_id,
        )
    )
    return result.scalar_one_or_none()


async def _ensure_default_membership(
    db: AsyncSession,
    *,
    user: User,
    family_id: int,
    role: FamilyRole | None = None,
) -> FamilyMembership:
    membership = await _get_default_membership(db, user_id=user.id, family_id=family_id)
    if membership is None:
        now = datetime.now(timezone.utc)
        membership = FamilyMembership(
            user_id=user.id,
            family_id=family_id,
            role=role or DEFAULT_SCIM_ROLE,
            is_owner=False,
            invited_at=now,
            accepted_at=now,
        )
        db.add(membership)
        await db.flush()
        return membership

    if membership.accepted_at is None:
        membership.accepted_at = datetime.now(timezone.utc)
    if role is not None and membership.role != role:
        if membership.is_owner:
            raise ScimError(
                status.HTTP_409_CONFLICT,
                'SCIM cannot modify owner-managed family roles.',
                scim_type='mutability',
            )
        membership.role = role
    return membership



def _family_role_aliases() -> dict[str, FamilyRole]:
    return {
        'parent': FamilyRole.parent,
        'co-parent': FamilyRole.co_parent,
        'coparent': FamilyRole.co_parent,
        'co_parent': FamilyRole.co_parent,
        'tutor': FamilyRole.tutor,
        'student': FamilyRole.student_viewer,
        'student-viewer': FamilyRole.student_viewer,
        'student_viewer': FamilyRole.student_viewer,
        'studentviewer': FamilyRole.student_viewer,
    }



def _resolve_group_role(display_name: str) -> FamilyRole:
    normalized = display_name.strip().casefold()
    direct = _family_role_aliases().get(normalized)
    if direct is not None:
        return direct

    app_roles = normalize_external_app_roles([display_name], external_role_mappings=settings.external_role_mappings)
    if app_roles:
        return derive_family_role_from_app_roles([role.value for role in app_roles])

    raise ScimError(
        status.HTTP_400_BAD_REQUEST,
        'displayName must map to a supported family role or configured external role.',
        scim_type='invalidValue',
    )


async def _ensure_unique_group_external_id(
    db: AsyncSession,
    *,
    external_id: str | None,
    exclude_group_id: int | None = None,
) -> None:
    if external_id is None:
        return
    stmt = select(ScimGroup.id).where(ScimGroup.external_id == external_id)
    if exclude_group_id is not None:
        stmt = stmt.where(ScimGroup.id != exclude_group_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise ScimError(status.HTTP_409_CONFLICT, 'externalId already exists.', scim_type='uniqueness')


async def _ensure_unique_group_role(
    db: AsyncSession,
    *,
    family_id: int,
    role: FamilyRole,
    exclude_group_id: int | None = None,
) -> None:
    stmt = select(ScimGroup.id).where(ScimGroup.family_id == family_id, ScimGroup.role == role)
    if exclude_group_id is not None:
        stmt = stmt.where(ScimGroup.id != exclude_group_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise ScimError(status.HTTP_409_CONFLICT, 'A SCIM group for that role already exists.', scim_type='uniqueness')


async def _group_member_rows(db: AsyncSession, *, family_id: int, role: FamilyRole) -> list[tuple[FamilyMembership, User]]:
    result = await db.execute(
        select(FamilyMembership, User)
        .join(User, User.id == FamilyMembership.user_id)
        .where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.role == role,
            _managed_user_predicate(),
        )
        .order_by(User.id)
    )
    return list(result.all())


async def _group_members(db: AsyncSession, *, family_id: int, role: FamilyRole) -> list[User]:
    rows = await _group_member_rows(db, family_id=family_id, role=role)
    return [user for membership, user in rows if user.is_active]



def _user_resource(request: Request, user: User) -> dict[str, Any]:
    resource: dict[str, Any] = {
        'schemas': [SCIM_USER_SCHEMA],
        'id': str(user.id),
        'userName': user.email,
        'displayName': user.display_name,
        'active': user.is_active,
        'emails': [
            {
                'value': user.email,
                'type': 'work',
                'primary': True,
            }
        ],
        'meta': _resource_meta(
            request,
            resource_type='User',
            resource_id=user.id,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    }
    if user.scim_external_id:
        resource['externalId'] = user.scim_external_id
    return resource


async def _group_resource(request: Request, db: AsyncSession, group: ScimGroup) -> dict[str, Any]:
    members = [
        {
            'value': str(user.id),
            '$ref': _absolute_url(request, f'{SCIM_BASE_PATH}/Users/{user.id}'),
            'display': user.display_name,
        }
        for user in await _group_members(db, family_id=group.family_id, role=group.role)
    ]
    resource: dict[str, Any] = {
        'schemas': [SCIM_GROUP_SCHEMA],
        'id': str(group.id),
        'displayName': group.display_name,
        'members': members,
        'meta': _resource_meta(
            request,
            resource_type='Group',
            resource_id=group.id,
            created_at=group.created_at,
            updated_at=group.updated_at,
        ),
    }
    if group.external_id:
        resource['externalId'] = group.external_id
    return resource


async def _apply_user_update_fields(db: AsyncSession, user: User, updates: dict[str, Any]) -> None:
    email = user.email
    if 'userName' in updates:
        raw_user_name = updates['userName']
        if not isinstance(raw_user_name, str) or not raw_user_name.strip():
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'userName must be a non-empty string.', scim_type='invalidValue')
        email = normalize_email(raw_user_name)
    elif 'emails' in updates:
        email_candidate = _extract_email_value(updates['emails'])
        if email_candidate is None:
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'emails must include at least one value.', scim_type='invalidValue')
        email = normalize_email(email_candidate)

    external_id = user.scim_external_id
    if 'externalId' in updates:
        external_id = _normalize_external_id(updates['externalId'])

    if 'active' in updates and not isinstance(updates['active'], bool):
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'active must be a boolean.', scim_type='invalidValue')

    await _ensure_unique_user_name(db, user_name=email, exclude_user_id=user.id)
    await _ensure_unique_scim_external_id(db, external_id=external_id, exclude_user_id=user.id)

    user.email = email
    user.scim_external_id = external_id

    display_name = user.display_name
    if 'displayName' in updates:
        raw_display_name = updates['displayName']
        if raw_display_name is None:
            display_name = _default_display_name(email)
        elif not isinstance(raw_display_name, str) or not raw_display_name.strip():
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'displayName must be a non-empty string.', scim_type='invalidValue')
        else:
            display_name = raw_display_name.strip()
    elif 'name' in updates:
        raw_name = updates['name']
        if raw_name is None:
            display_name = _default_display_name(email)
        elif not isinstance(raw_name, dict):
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'name must be an object.', scim_type='invalidValue')
        else:
            formatted = raw_name.get('formatted')
            if formatted is None:
                display_name = _default_display_name(email)
            elif not isinstance(formatted, str) or not formatted.strip():
                raise ScimError(status.HTTP_400_BAD_REQUEST, 'name.formatted must be a non-empty string.', scim_type='invalidValue')
            else:
                display_name = formatted.strip()
    user.display_name = display_name

    if 'active' in updates:
        user.is_active = updates['active']


async def _apply_user_patch_operation(db: AsyncSession, user: User, operation: dict[str, Any]) -> None:
    op = str(operation.get('op', '')).strip().lower()
    if op not in {'add', 'replace', 'remove'}:
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'Unsupported PATCH op.', scim_type='invalidSyntax')

    path = operation.get('path')
    value = operation.get('value')
    if path is None:
        if op == 'remove' or not isinstance(value, dict):
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'PATCH operations without a path require an object value.', scim_type='invalidSyntax')
        await _apply_user_update_fields(db, user, value)
        return

    if not isinstance(path, str) or not path.strip():
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'PATCH path must be a string.', scim_type='invalidSyntax')

    normalized_path = path.strip()
    if normalized_path == 'displayName':
        await _apply_user_update_fields(db, user, {'displayName': None if op == 'remove' else value})
        return
    if normalized_path == 'userName':
        if op == 'remove':
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'userName cannot be removed.', scim_type='mutability')
        await _apply_user_update_fields(db, user, {'userName': value})
        return
    if normalized_path == 'externalId':
        await _apply_user_update_fields(db, user, {'externalId': None if op == 'remove' else value})
        return
    if normalized_path == 'active':
        if op == 'remove':
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'active cannot be removed.', scim_type='mutability')
        await _apply_user_update_fields(db, user, {'active': value})
        return
    if normalized_path == 'emails':
        if op == 'remove':
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'emails cannot be removed.', scim_type='mutability')
        await _apply_user_update_fields(db, user, {'emails': value})
        return
    if normalized_path == 'name.formatted':
        await _apply_user_update_fields(db, user, {'name': {'formatted': None if op == 'remove' else value}})
        return

    raise ScimError(status.HTTP_400_BAD_REQUEST, f'Unsupported PATCH path: {normalized_path}', scim_type='invalidPath')



def _extract_member_ids(value: Any) -> list[int]:
    values = value if isinstance(value, list) else [value]
    member_ids: list[int] = []
    for item in values:
        if isinstance(item, dict):
            raw_id = item.get('value')
        else:
            raw_id = item
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'members entries must include a value.', scim_type='invalidValue')
        member_ids.append(_ensure_int_id(raw_id, resource_type='User'))
    return member_ids


async def _set_group_role(db: AsyncSession, *, group: ScimGroup, display_name: str) -> None:
    new_display_name = display_name.strip()
    if not new_display_name:
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'displayName must be a non-empty string.', scim_type='invalidValue')
    new_role = _resolve_group_role(new_display_name)
    await _ensure_unique_group_role(db, family_id=group.family_id, role=new_role, exclude_group_id=group.id)
    if group.role != new_role:
        for membership, user in await _group_member_rows(db, family_id=group.family_id, role=group.role):
            if membership.is_owner:
                raise ScimError(
                    status.HTTP_409_CONFLICT,
                    'SCIM cannot modify owner-managed family roles.',
                    scim_type='mutability',
                )
            membership.role = new_role
    group.role = new_role
    group.display_name = new_display_name


async def _assign_group_members(db: AsyncSession, *, group: ScimGroup, member_ids: list[int]) -> None:
    for member_id in member_ids:
        user = await db.get(User, member_id)
        if user is None:
            raise ScimError(status.HTTP_404_NOT_FOUND, 'User not found.')
        await _ensure_default_membership(db, user=user, family_id=group.family_id, role=group.role)


async def _remove_group_members(db: AsyncSession, *, group: ScimGroup, member_ids: list[int]) -> None:
    for member_id in member_ids:
        membership = await _get_default_membership(db, user_id=member_id, family_id=group.family_id)
        if membership is None or membership.role != group.role:
            continue
        if membership.is_owner:
            raise ScimError(
                status.HTTP_409_CONFLICT,
                'SCIM cannot modify owner-managed family roles.',
                scim_type='mutability',
            )
        membership.role = DEFAULT_SCIM_ROLE


async def _replace_group_members(db: AsyncSession, *, group: ScimGroup, member_ids: list[int]) -> None:
    target_ids = set(member_ids)
    current_members = await _group_member_rows(db, family_id=group.family_id, role=group.role)
    current_ids = {user.id for membership, user in current_members}
    remove_ids = sorted(current_ids - target_ids)
    add_ids = sorted(target_ids - current_ids)
    await _remove_group_members(db, group=group, member_ids=remove_ids)
    await _assign_group_members(db, group=group, member_ids=add_ids)


async def _apply_group_patch_operation(db: AsyncSession, group: ScimGroup, operation: dict[str, Any]) -> None:
    op = str(operation.get('op', '')).strip().lower()
    if op not in {'add', 'replace', 'remove'}:
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'Unsupported PATCH op.', scim_type='invalidSyntax')

    path = operation.get('path')
    value = operation.get('value')
    if path is None:
        if op == 'remove' or not isinstance(value, dict):
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'PATCH operations without a path require an object value.', scim_type='invalidSyntax')
        if 'displayName' in value:
            await _set_group_role(db, group=group, display_name=value['displayName'])
        if 'externalId' in value:
            external_id = _normalize_external_id(value['externalId'])
            await _ensure_unique_group_external_id(db, external_id=external_id, exclude_group_id=group.id)
            group.external_id = external_id
        if 'members' in value:
            await _replace_group_members(db, group=group, member_ids=_extract_member_ids(value['members']))
        return

    if not isinstance(path, str) or not path.strip():
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'PATCH path must be a string.', scim_type='invalidSyntax')

    normalized_path = path.strip()
    if normalized_path == 'displayName':
        if op == 'remove':
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'displayName cannot be removed.', scim_type='mutability')
        if not isinstance(value, str):
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'displayName must be a string.', scim_type='invalidValue')
        await _set_group_role(db, group=group, display_name=value)
        return
    if normalized_path == 'externalId':
        external_id = None if op == 'remove' else _normalize_external_id(value)
        await _ensure_unique_group_external_id(db, external_id=external_id, exclude_group_id=group.id)
        group.external_id = external_id
        return
    if normalized_path == 'members':
        member_ids = [] if op == 'replace' and value in (None, []) else _extract_member_ids(value)
        if op == 'add':
            await _assign_group_members(db, group=group, member_ids=member_ids)
        elif op == 'replace':
            await _replace_group_members(db, group=group, member_ids=member_ids)
        else:
            await _remove_group_members(db, group=group, member_ids=member_ids)
        return

    member_id = _parse_member_filter(normalized_path)
    if member_id is not None:
        await _remove_group_members(db, group=group, member_ids=[_ensure_int_id(member_id, resource_type='User')])
        return

    raise ScimError(status.HTTP_400_BAD_REQUEST, f'Unsupported PATCH path: {normalized_path}', scim_type='invalidPath')


@router.get('/ServiceProviderConfig')
async def service_provider_config() -> dict[str, Any]:
    return {
        'schemas': [SCIM_SERVICE_PROVIDER_CONFIG],
        'patch': {'supported': True},
        'bulk': {'supported': False, 'maxOperations': 0, 'maxPayloadSize': 0},
        'filter': {'supported': True, 'maxResults': 100},
        'changePassword': {'supported': False},
        'sort': {'supported': False},
        'etag': {'supported': False},
        'authenticationSchemes': [
            {
                'type': 'oauthbearertoken',
                'name': 'Bearer Token',
                'description': 'Static bearer token configured with SCIM_BEARER_TOKEN.',
                'specUri': 'https://datatracker.ietf.org/doc/html/rfc6750',
                'primary': True,
            }
        ],
    }


@router.get('/ResourceTypes')
async def resource_types(request: Request) -> dict[str, Any]:
    resources = [
        {
            'schemas': [SCIM_RESOURCE_SCHEMA],
            'id': 'User',
            'name': 'User',
            'endpoint': f'{SCIM_BASE_PATH}/Users',
            'schema': SCIM_USER_SCHEMA,
            'meta': {'location': _absolute_url(request, f'{SCIM_BASE_PATH}/ResourceTypes/User'), 'resourceType': 'ResourceType'},
        },
        {
            'schemas': [SCIM_RESOURCE_SCHEMA],
            'id': 'Group',
            'name': 'Group',
            'endpoint': f'{SCIM_BASE_PATH}/Groups',
            'schema': SCIM_GROUP_SCHEMA,
            'meta': {'location': _absolute_url(request, f'{SCIM_BASE_PATH}/ResourceTypes/Group'), 'resourceType': 'ResourceType'},
        },
    ]
    return _list_response(resources, total_results=len(resources), start_index=1)


@router.get('/Schemas')
async def schemas(request: Request) -> dict[str, Any]:
    resources = [
        {
            'schemas': [SCIM_SCHEMA_DEFINITION],
            'id': SCIM_USER_SCHEMA,
            'name': 'User',
            'description': 'SCIM core user schema for Homeschool Hero provisioning.',
            'attributes': [
                {'name': 'userName', 'type': 'string', 'required': True, 'mutability': 'readWrite'},
                {'name': 'displayName', 'type': 'string', 'required': False, 'mutability': 'readWrite'},
                {'name': 'active', 'type': 'boolean', 'required': False, 'mutability': 'readWrite'},
                {'name': 'externalId', 'type': 'string', 'required': False, 'mutability': 'readWrite'},
                {'name': 'emails', 'type': 'complex', 'required': False, 'mutability': 'readWrite'},
            ],
            'meta': {'location': _absolute_url(request, f'{SCIM_BASE_PATH}/Schemas/User'), 'resourceType': 'Schema'},
        },
        {
            'schemas': [SCIM_SCHEMA_DEFINITION],
            'id': SCIM_GROUP_SCHEMA,
            'name': 'Group',
            'description': 'SCIM core group schema mapped to Homeschool Hero family roles.',
            'attributes': [
                {'name': 'displayName', 'type': 'string', 'required': True, 'mutability': 'readWrite'},
                {'name': 'externalId', 'type': 'string', 'required': False, 'mutability': 'readWrite'},
                {'name': 'members', 'type': 'complex', 'required': False, 'mutability': 'readWrite'},
            ],
            'meta': {'location': _absolute_url(request, f'{SCIM_BASE_PATH}/Schemas/Group'), 'resourceType': 'Schema'},
        },
    ]
    return _list_response(resources, total_results=len(resources), start_index=1)


@router.get('/Users')
async def list_users(
    request: Request,
    filter: str | None = None,
    startIndex: int = 1,
    count: int = 100,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    start_index, count = _normalize_pagination(startIndex, count)
    parsed_filter = _parse_filter(filter)

    stmt = select(User)
    if parsed_filter is None:
        stmt = stmt.where(_managed_user_predicate())
    else:
        attribute, value = parsed_filter
        if attribute == 'userName':
            stmt = stmt.where(func.lower(User.email) == normalize_email(value))
        elif attribute == 'externalId':
            stmt = stmt.where(User.scim_external_id == value)
        elif attribute == 'id':
            stmt = stmt.where(User.id == _ensure_int_id(value, resource_type='User'))
        elif attribute == 'displayName':
            stmt = stmt.where(User.display_name == value)
        else:
            raise ScimError(status.HTTP_400_BAD_REQUEST, f'Unsupported User filter attribute: {attribute}', scim_type='invalidFilter')

    total_results = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    items = [] if count == 0 else list((await db.execute(stmt.order_by(User.id).offset(start_index - 1).limit(count))).scalars().all())
    return _list_response([_user_resource(request, user) for user in items], total_results=total_results, start_index=start_index)


@router.post('/Users', status_code=status.HTTP_201_CREATED)
async def create_user(request: Request, payload: dict[str, Any], db: AsyncSession = Depends(get_db)) -> JSONResponse:
    _validate_schemas(payload, SCIM_USER_SCHEMA)
    user_name = _resolve_user_name(payload, required=True)
    display_name = _resolve_display_name(payload, email=user_name)
    active = payload.get('active', True)
    if not isinstance(active, bool):
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'active must be a boolean.', scim_type='invalidValue')
    external_id = _normalize_external_id(payload.get('externalId'))
    await _ensure_unique_user_name(db, user_name=user_name)
    await _ensure_unique_scim_external_id(db, external_id=external_id)

    family = await ensure_default_family(db)
    user = User(
        email=user_name,
        display_name=display_name,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        is_active=active,
        auth_provider='scim',
        scim_external_id=external_id,
    )
    db.add(user)
    await db.flush()
    await _ensure_default_membership(db, user=user, family_id=family.id)
    await db.refresh(user)
    await _log_scim_change(
        db,
        action=AuditAction.config_change,
        family_id=family.id,
        target_type='scim_user',
        target_id=user.id,
        before=None,
        after=_user_resource(request, user),
        request=request,
    )
    await db.commit()
    resource = _user_resource(request, user)
    return ScimJSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=resource,
        headers={'Location': resource['meta']['location']},
    )


@router.get('/Users/{user_id}')
async def get_user(user_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return _user_resource(request, await _get_user_or_404(db, user_id))


@router.patch('/Users/{user_id}')
async def patch_user(user_id: str, request: Request, payload: dict[str, Any], db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    _validate_schemas(payload, SCIM_PATCH_OP_SCHEMA)
    operations = payload.get('Operations')
    if not isinstance(operations, list) or not operations:
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'PATCH requires a non-empty Operations array.', scim_type='invalidSyntax')

    user = await _get_user_or_404(db, user_id)
    family = await ensure_default_family(db)
    before = _user_resource(request, user)
    for operation in operations:
        if not isinstance(operation, dict):
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'Operations entries must be objects.', scim_type='invalidSyntax')
        await _apply_user_patch_operation(db, user, operation)

    if user.scim_external_id or user.auth_provider == 'scim':
        await _ensure_default_membership(db, user=user, family_id=family.id)
    await db.flush()
    await db.refresh(user)
    await _log_scim_change(
        db,
        action=AuditAction.config_change,
        family_id=family.id,
        target_type='scim_user',
        target_id=user.id,
        before=before,
        after=_user_resource(request, user),
        request=request,
    )
    await db.commit()
    return _user_resource(request, user)


@router.delete('/Users/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    user = await _get_user_or_404(db, user_id)
    family = await ensure_default_family(db)
    before = _user_resource(request, user)
    user.is_active = False
    await db.flush()
    await db.refresh(user)
    await _log_scim_change(
        db,
        action=AuditAction.config_change,
        family_id=family.id,
        target_type='scim_user',
        target_id=user.id,
        before=before,
        after=_user_resource(request, user),
        request=request,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, media_type='application/scim+json')


@router.get('/Groups')
async def list_groups(
    request: Request,
    filter: str | None = None,
    startIndex: int = 1,
    count: int = 100,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    start_index, count = _normalize_pagination(startIndex, count)
    parsed_filter = _parse_filter(filter)

    stmt = select(ScimGroup)
    if parsed_filter is not None:
        attribute, value = parsed_filter
        if attribute == 'displayName':
            stmt = stmt.where(ScimGroup.display_name == value)
        elif attribute == 'externalId':
            stmt = stmt.where(ScimGroup.external_id == value)
        elif attribute == 'id':
            stmt = stmt.where(ScimGroup.id == _ensure_int_id(value, resource_type='Group'))
        else:
            raise ScimError(status.HTTP_400_BAD_REQUEST, f'Unsupported Group filter attribute: {attribute}', scim_type='invalidFilter')

    total_results = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    groups = [] if count == 0 else list((await db.execute(stmt.order_by(ScimGroup.id).offset(start_index - 1).limit(count))).scalars().all())
    resources = [await _group_resource(request, db, group) for group in groups]
    return _list_response(resources, total_results=total_results, start_index=start_index)


@router.post('/Groups', status_code=status.HTTP_201_CREATED)
async def create_group(request: Request, payload: dict[str, Any], db: AsyncSession = Depends(get_db)) -> JSONResponse:
    _validate_schemas(payload, SCIM_GROUP_SCHEMA)
    raw_display_name = payload.get('displayName')
    if not isinstance(raw_display_name, str) or not raw_display_name.strip():
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'displayName is required.', scim_type='invalidValue')
    external_id = _normalize_external_id(payload.get('externalId'))

    family = await ensure_default_family(db)
    role = _resolve_group_role(raw_display_name)
    await _ensure_unique_group_role(db, family_id=family.id, role=role)
    await _ensure_unique_group_external_id(db, external_id=external_id)

    group = ScimGroup(
        family_id=family.id,
        display_name=raw_display_name.strip(),
        external_id=external_id,
        role=role,
    )
    db.add(group)
    await db.flush()
    if 'members' in payload:
        await _assign_group_members(db, group=group, member_ids=_extract_member_ids(payload['members']))
    await db.refresh(group)
    resource = await _group_resource(request, db, group)
    await _log_scim_change(
        db,
        action=AuditAction.role_change,
        family_id=family.id,
        target_type='scim_group',
        target_id=group.id,
        before=None,
        after=resource,
        request=request,
    )
    await db.commit()
    return ScimJSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=resource,
        headers={'Location': resource['meta']['location']},
    )


@router.get('/Groups/{group_id}')
async def get_group(group_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await _group_resource(request, db, await _get_group_or_404(db, group_id))


@router.patch('/Groups/{group_id}')
async def patch_group(group_id: str, request: Request, payload: dict[str, Any], db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    _validate_schemas(payload, SCIM_PATCH_OP_SCHEMA)
    operations = payload.get('Operations')
    if not isinstance(operations, list) or not operations:
        raise ScimError(status.HTTP_400_BAD_REQUEST, 'PATCH requires a non-empty Operations array.', scim_type='invalidSyntax')

    group = await _get_group_or_404(db, group_id)
    before = await _group_resource(request, db, group)
    for operation in operations:
        if not isinstance(operation, dict):
            raise ScimError(status.HTTP_400_BAD_REQUEST, 'Operations entries must be objects.', scim_type='invalidSyntax')
        await _apply_group_patch_operation(db, group, operation)

    await db.flush()
    await db.refresh(group)
    after = await _group_resource(request, db, group)
    await _log_scim_change(
        db,
        action=AuditAction.role_change,
        family_id=group.family_id,
        target_type='scim_group',
        target_id=group.id,
        before=before,
        after=after,
        request=request,
    )
    await db.commit()
    return after


@router.delete('/Groups/{group_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    group = await _get_group_or_404(db, group_id)
    before = await _group_resource(request, db, group)
    for membership, user in await _group_member_rows(db, family_id=group.family_id, role=group.role):
        if membership.is_owner:
            raise ScimError(
                status.HTTP_409_CONFLICT,
                'SCIM cannot modify owner-managed family roles.',
                scim_type='mutability',
            )
        membership.role = DEFAULT_SCIM_ROLE
    await _log_scim_change(
        db,
        action=AuditAction.role_change,
        family_id=group.family_id,
        target_type='scim_group',
        target_id=group.id,
        before=before,
        after=None,
        request=request,
    )
    await db.delete(group)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, media_type='application/scim+json')
