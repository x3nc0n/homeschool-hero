from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import ApiToken
from backend.security import AuthSession

DELEGATABLE_CAPABILITIES = {
    'manage_curriculum',
    'manage_submissions',
    'manage_grading',
}
_MINIMUM_HS256_SECRET_LENGTH = 32


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _assert_api_token_signing_configuration() -> str:
    if not settings.jwt_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='JWT bearer authentication must be enabled before creating API tokens.',
        )
    if settings.jwt_algorithm.strip().upper() != 'HS256':
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='API token issuance requires JWT_ALGORITHM=HS256.',
        )

    secret = settings.jwt_secret.strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='API token issuance requires JWT_SECRET to be configured.',
        )
    if len(secret) < _MINIMUM_HS256_SECRET_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f'JWT_SECRET must be at least {_MINIMUM_HS256_SECRET_LENGTH} characters for API token issuance.',
        )
    return secret


def normalize_api_token_capabilities(capabilities: list[str]) -> list[str]:
    normalized = sorted({value.strip() for value in capabilities if value.strip()})
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='At least one capability is required.')

    invalid = [value for value in normalized if value not in DELEGATABLE_CAPABILITIES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid or non-delegatable capability: '{invalid[0]}'.",
        )
    return normalized


async def create_api_token(
    db: AsyncSession,
    *,
    auth: AuthSession,
    name: str,
    capabilities: list[str],
    expires_in_days: int,
) -> tuple[ApiToken, str]:
    secret = _assert_api_token_signing_configuration()
    normalized_capabilities = normalize_api_token_capabilities(capabilities)
    now = _utc_now()

    active_count = (
        await db.execute(
            select(func.count(ApiToken.id)).where(
                ApiToken.family_id == auth.family_id,
                ApiToken.revoked_at.is_(None),
                ApiToken.expires_at > now,
            )
        )
    ).scalar_one()
    if int(active_count or 0) >= settings.api_token_max_active_per_family:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Maximum active API tokens ({settings.api_token_max_active_per_family}) reached for this family.',
        )

    existing = (
        await db.execute(
            select(ApiToken.id).where(
                ApiToken.family_id == auth.family_id,
                ApiToken.name == name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A token named '{name}' already exists in this family.",
        )

    token_id = str(uuid.uuid4())
    expires_at = now + timedelta(days=expires_in_days)
    claims: dict[str, object] = {
        'sub': str(auth.user_id),
        'user_id': auth.user_id,
        'family_id': auth.family_id,
        'email': auth.email,
        'name': auth.display_name,
        'roles': list(auth.app_roles),
        'family_role': auth.family_role,
        'jti': token_id,
        'token_type': 'api_token',
        'capabilities': normalized_capabilities,
        'iat': int(now.timestamp()),
        'exp': int(expires_at.timestamp()),
    }
    if settings.jwt_issuer.strip():
        claims['iss'] = settings.jwt_issuer.strip()
    if settings.jwt_audience.strip():
        claims['aud'] = settings.jwt_audience.strip()

    raw_token = jwt.encode(claims, secret, algorithm='HS256')
    token_digest = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    api_token = ApiToken(
        id=token_id,
        family_id=auth.family_id,
        created_by_user_id=auth.user_id,
        name=name,
        token_digest=token_digest,
        capabilities=normalized_capabilities,
        expires_at=expires_at,
        revoked_at=None,
        last_used_at=None,
    )
    db.add(api_token)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A token named '{name}' already exists in this family.",
        ) from exc
    await db.refresh(api_token)
    return api_token, raw_token


async def list_api_tokens(
    db: AsyncSession,
    *,
    family_id: int,
) -> list[ApiToken]:
    result = await db.execute(
        select(ApiToken)
        .where(ApiToken.family_id == family_id)
        .order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
    )
    return list(result.scalars().all())


async def revoke_api_token(
    db: AsyncSession,
    *,
    family_id: int,
    token_id: str,
) -> None:
    token = (
        await db.execute(
            select(ApiToken).where(
                ApiToken.id == token_id,
                ApiToken.family_id == family_id,
            )
        )
    ).scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='API token not found')
    if token.revoked_at is None:
        token.revoked_at = _utc_now()
        await db.commit()
