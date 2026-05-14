from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from backend.config import settings
from backend.models import FamilyRole
from backend.services.rbac import normalize_external_app_roles

logger = logging.getLogger(__name__)

_JWKS_CACHE_TTL_SECONDS = 300.0
_FAMILY_ID_HEADER = 'x-family-id'


@dataclass(slots=True)
class CachedJwks:
    payload: dict[str, Any]
    expires_at: float


_JWKS_CACHE: dict[str, CachedJwks] = {}
_JWKS_LOCKS: dict[str, asyncio.Lock] = {}


class JWTAuthenticationError(HTTPException):
    def __init__(self, *, status_code: int, detail: str):
        headers = {'WWW-Authenticate': 'Bearer'} if status_code == status.HTTP_401_UNAUTHORIZED else None
        super().__init__(status_code=status_code, detail=detail, headers=headers)


@dataclass(slots=True)
class BearerSessionClaims:
    family_id: int
    email: str
    display_name: str
    app_roles: list[str]
    family_role: str
    user_id: int | None = None
    external_id_candidates: tuple[str, ...] = ()
    tenant_id: str | None = None
    groups: tuple[str, ...] = ()
    groups_overage: bool = False
    auth_provider: str = 'jwt'
    family_name: str = ''
    family_state_code: str = 'CUSTOM'
    is_owner: bool = False
    student_id: int | None = None
    enabled_features: dict[str, bool] | None = None
    ui_preferences: dict[str, str] | None = None


async def authenticate_bearer_token(request: Request) -> BearerSessionClaims | None:
    authorization = request.headers.get('authorization', '')
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer':
        return None
    if not settings.jwt_enabled:
        return None
    if not token.strip():
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bearer token is required')

    claims = await _decode_token(token.strip())
    return _build_bearer_claims(claims, request=request)


async def _decode_token(token: str) -> dict[str, Any]:
    try:
        key = await _resolve_signing_key(token)
        required_claims = ['exp']
        if settings.jwt_issuer.strip():
            required_claims.append('iss')
        if settings.jwt_audience.strip():
            required_claims.append('aud')
        return jwt.decode(
            token,
            key=key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer.strip() or None,
            audience=settings.jwt_audience.strip() or None,
            options={'require': required_claims},
        )
    except jwt.ExpiredSignatureError as exc:
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bearer token has expired') from exc
    except jwt.ImmatureSignatureError as exc:
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bearer token is not active yet') from exc
    except jwt.InvalidIssuerError as exc:
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bearer token issuer is invalid') from exc
    except jwt.InvalidAudienceError as exc:
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bearer token audience is invalid') from exc
    except InvalidTokenError as exc:
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bearer token is invalid') from exc


async def _resolve_signing_key(token: str) -> str | bytes | Any:
    secret = settings.jwt_secret.strip()
    if secret:
        return secret

    jwks_url = settings.jwt_jwks_url.strip()
    if not jwks_url:
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='JWT validation is not configured')

    header = jwt.get_unverified_header(token)
    kid = str(header.get('kid', '')).strip()
    jwks = await _get_jwks(jwks_url)
    keys = jwks.get('keys')
    if not isinstance(keys, list):
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='JWT key set is invalid')

    matching_key: dict[str, Any] | None = None
    if kid:
        matching_key = next((key for key in keys if isinstance(key, dict) and key.get('kid') == kid), None)
    elif len(keys) == 1 and isinstance(keys[0], dict):
        matching_key = keys[0]

    if matching_key is None:
        raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bearer token signing key was not found')
    return RSAAlgorithm.from_jwk(json.dumps(matching_key))


async def _get_jwks(jwks_url: str) -> dict[str, Any]:
    cached = _JWKS_CACHE.get(jwks_url)
    now = monotonic()
    if cached is not None and cached.expires_at > now:
        return cached.payload

    lock = _JWKS_LOCKS.setdefault(jwks_url, asyncio.Lock())
    async with lock:
        cached = _JWKS_CACHE.get(jwks_url)
        now = monotonic()
        if cached is not None and cached.expires_at > now:
            return cached.payload

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(jwks_url, headers={'Accept': 'application/json'})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unable to fetch JWT signing keys') from exc

        if not isinstance(payload, dict) or not isinstance(payload.get('keys'), list):
            raise JWTAuthenticationError(status_code=status.HTTP_401_UNAUTHORIZED, detail='JWT key set is invalid')

        _JWKS_CACHE[jwks_url] = CachedJwks(payload=payload, expires_at=now + _JWKS_CACHE_TTL_SECONDS)
        return payload


def _build_bearer_claims(raw_claims: dict[str, Any], *, request: Request) -> BearerSessionClaims:
    app_roles = [
        app_role.value
        for app_role in normalize_external_app_roles(
            _claim_values(raw_claims.get('roles')),
            external_role_mappings=settings.external_role_mappings,
        )
    ]
    if not app_roles:
        raise JWTAuthenticationError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Bearer token does not grant any mapped application roles',
        )

    family_id = _claim_int(raw_claims.get('family_id')) or _claim_int(request.headers.get(_FAMILY_ID_HEADER))
    if family_id is None:
        raise JWTAuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Bearer token is missing family context',
        )

    tenant_id = _validate_tenant_id(raw_claims)
    user_id = _claim_int(raw_claims.get('user_id')) or _claim_int(raw_claims.get('uid')) or _claim_int(raw_claims.get('sub'))
    external_id_candidates = _external_id_candidates(raw_claims)
    if user_id is None and not external_id_candidates:
        raise JWTAuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Bearer token is missing a stable subject identifier',
        )

    email = _claim_string(raw_claims.get('email')) or _claim_string(raw_claims.get('preferred_username')) or _claim_string(raw_claims.get('sub'))
    if email is None:
        raise JWTAuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Bearer token is missing a principal identifier',
        )
    normalized_email = normalize_email(email)

    groups, groups_overage = _extract_groups(raw_claims)
    display_name = _claim_string(raw_claims.get('name')) or _claim_string(raw_claims.get('display_name')) or normalized_email
    family_role = _resolve_family_role(raw_claims, app_roles)
    family_state_code = (_claim_string(raw_claims.get('family_state_code')) or 'CUSTOM').upper()
    auth_provider = _claim_string(raw_claims.get('auth_provider')) or ('oidc' if tenant_id or _claim_string(raw_claims.get('oid')) else 'jwt')

    return BearerSessionClaims(
        family_id=family_id,
        email=normalized_email,
        display_name=display_name,
        app_roles=app_roles,
        family_role=family_role,
        user_id=user_id,
        external_id_candidates=external_id_candidates,
        tenant_id=tenant_id,
        groups=groups,
        groups_overage=groups_overage,
        auth_provider=auth_provider,
        family_name=_claim_string(raw_claims.get('family_name')) or '',
        family_state_code=family_state_code,
        is_owner=False,
        student_id=_claim_int(raw_claims.get('student_id')),
        enabled_features=_claim_dict(raw_claims.get('enabled_features')),
        ui_preferences=_claim_string_dict(raw_claims.get('ui_preferences')),
    )


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _claim_values(value: Any) -> list[str]:
    if isinstance(value, str):
        candidate = value.strip()
        return [candidate] if candidate else []
    if isinstance(value, list | tuple | set):
        values: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            candidate = item.strip()
            if candidate and candidate not in seen:
                values.append(candidate)
                seen.add(candidate)
        return values
    return []


def _claim_string(value: Any) -> str | None:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    return None


def _claim_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in {'true', '1', 'yes'}:
            return True
        if candidate in {'false', '0', 'no'}:
            return False
    return None


def _claim_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.isdigit():
            return int(candidate)
    return None


def _claim_dict(value: Any) -> dict[str, bool] | None:
    if not isinstance(value, dict):
        return None
    payload: dict[str, bool] = {}
    for key, item in value.items():
        if isinstance(key, str):
            payload[key] = bool(item)
    return payload


def _claim_string_dict(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    payload: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            candidate = item.strip()
            if candidate:
                payload[key] = candidate
    return payload or None


def _validate_tenant_id(raw_claims: dict[str, Any]) -> str | None:
    expected_tenant_id = settings.jwt_tenant_id.strip()
    if not expected_tenant_id:
        return _claim_string(raw_claims.get('tid'))

    actual_tenant_id = _claim_string(raw_claims.get('tid'))
    if actual_tenant_id is None:
        raise JWTAuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Bearer token is missing tenant context',
        )
    if actual_tenant_id.casefold() != expected_tenant_id.casefold():
        raise JWTAuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Bearer token tenant is invalid',
        )
    return actual_tenant_id


def _external_id_candidates(raw_claims: dict[str, Any]) -> tuple[str, ...]:
    candidates: list[str] = []
    seen: set[str] = set()
    for claim_name in ('oid', 'sub'):
        candidate = _claim_string(raw_claims.get(claim_name))
        if candidate and candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)
    return tuple(candidates)


def _groups_overage_detected(raw_claims: dict[str, Any]) -> bool:
    hasgroups = _claim_bool(raw_claims.get('hasgroups'))
    if hasgroups is True:
        return True

    claim_names = raw_claims.get('_claim_names')
    if not isinstance(claim_names, dict):
        return False

    source_name = claim_names.get('groups')
    if not isinstance(source_name, str) or not source_name.strip():
        return False

    claim_sources = raw_claims.get('_claim_sources')
    if isinstance(claim_sources, dict) and source_name.strip() not in claim_sources:
        return False
    return True


def _extract_groups(raw_claims: dict[str, Any]) -> tuple[tuple[str, ...], bool]:
    if _groups_overage_detected(raw_claims):
        logger.warning('Bearer token groups overage detected; keeping roles claim authoritative for RBAC.')
        return (), True
    return tuple(_claim_values(raw_claims.get('groups'))), False


def _resolve_family_role(raw_claims: dict[str, Any], app_roles: list[str]) -> str:
    for claim_name in ('family_role', 'role', 'membership_role'):
        candidate = _claim_string(raw_claims.get(claim_name))
        if candidate is None:
            continue
        try:
            return FamilyRole(candidate).value
        except ValueError as exc:
            raise JWTAuthenticationError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bearer token family role '{candidate}' is invalid",
            ) from exc

    return FamilyRole.student_viewer.value
