from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import httpx
from fastapi import Request

from backend.config import settings
from backend.security import normalize_email, resolve_external_app_roles
from backend.services.auth_provisioning import ExternalIdentity
from backend.services.security_events import emit_role_mapping_failure

logger = logging.getLogger(__name__)

try:
    from authlib.integrations.starlette_client import OAuth, OAuthError
    AUTHLIB_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AUTHLIB_AVAILABLE = False
    OAuth = Any  # type: ignore[assignment]

    class OAuthError(Exception):
        error = 'authlib_unavailable'

        def __init__(self, error: str = 'authlib_unavailable'):
            super().__init__(error)
            self.error = error


class OIDCConfigurationError(RuntimeError):
    """Raised when OIDC is not available or returns unusable claims."""


def _oidc_provider_error_detail(exc: Exception) -> str | None:
    if isinstance(exc, OAuthError):
        detail = str(getattr(exc, 'error', '') or '').strip()
        if detail:
            return detail
    if isinstance(exc, httpx.HTTPStatusError):
        return f'provider discovery returned HTTP {exc.response.status_code}'
    if isinstance(exc, httpx.RequestError):
        return 'provider discovery endpoint is unreachable'
    # Do not expose raw exception messages for unknown error types — log server-side only.
    logger.debug('Unclassified OIDC provider error: %s', exc)
    return None


def _oidc_login_error_message(exc: Exception) -> str:
    if isinstance(exc, OIDCConfigurationError):
        return str(exc)
    detail = _oidc_provider_error_detail(exc)
    if detail:
        return f'OIDC sign-in is unavailable: {detail}'
    return 'OIDC sign-in is temporarily unavailable. Please try again.'


def _oidc_callback_error_message(exc: Exception) -> str:
    if isinstance(exc, OIDCConfigurationError):
        return str(exc)
    detail = _oidc_provider_error_detail(exc)
    if detail:
        return f'OIDC sign-in failed: {detail}'
    return 'OIDC sign-in failed. Please try again.'


def _ensure_oidc_enabled() -> None:
    missing = [
        name
        for name, value in {
            'OIDC_CLIENT_ID': settings.oidc_client_id,
            'OIDC_CLIENT_SECRET': settings.oidc_client_secret,
            'OIDC_DISCOVERY_URL': settings.oidc_discovery_url,
        }.items()
        if not (value or '').strip()
    ]
    if missing:
        raise OIDCConfigurationError('OIDC authentication requires these settings: ' + ', '.join(missing))
    if not AUTHLIB_AVAILABLE:
        raise OIDCConfigurationError('OIDC authentication requires the optional authlib dependency.')


def create_oauth_client() -> OAuth:
    oauth = OAuth()
    oauth.register(
        name='oidc',
        client_id=(settings.oidc_client_id or '').strip(),
        client_secret=(settings.oidc_client_secret or '').strip(),
        server_metadata_url=(settings.oidc_discovery_url or '').strip(),
        client_kwargs={'scope': 'openid email profile'},
    )
    return oauth


def _coalesce_claim(claims: Mapping[str, object], *names: str) -> str | None:
    for name in names:
        value = claims.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _claim_values(claims: Mapping[str, object], *names: str) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for name in names:
        raw_value = claims.get(name)
        items: list[str] = []
        if isinstance(raw_value, str):
            items = [raw_value]
        elif isinstance(raw_value, list | tuple | set):
            items = [item for item in raw_value if isinstance(item, str)]
        for item in items:
            candidate = item.strip()
            if candidate and candidate not in seen:
                values.append(candidate)
                seen.add(candidate)
    return tuple(values)


def _warn_unmapped_roles(
    external_roles: tuple[str, ...],
    *,
    source: str,
    request: Request | None = None,
    email: str | None = None,
    external_id: str | None = None,
) -> None:
    unmapped = sorted(
        {
            role
            for role in external_roles
            if role.strip() and role.strip().casefold() not in settings.external_role_mappings
        }
    )
    if unmapped:
        logger.warning('OIDC %s contained unmapped role values: %s', source, ', '.join(unmapped))
        emit_role_mapping_failure(
            logger,
            provider='oidc',
            source=source,
            request=request,
            email=email,
            external_id=external_id,
            unmapped_roles=unmapped,
        )


def _normalize_external_roles(
    external_roles: tuple[str, ...],
    *,
    source: str,
    request: Request | None = None,
    email: str | None = None,
    external_id: str | None = None,
) -> tuple[str, ...]:
    if not external_roles:
        return ()
    _warn_unmapped_roles(external_roles, source=source, request=request, email=email, external_id=external_id)
    return tuple(resolve_external_app_roles(list(external_roles)))


def _groups_overage_detected(claims: Mapping[str, object]) -> bool:
    claim_names = claims.get('_claim_names')
    if not isinstance(claim_names, Mapping):
        return False

    groups_claim = (settings.oidc_groups_claim or 'groups').strip() or 'groups'
    source_name = claim_names.get(groups_claim) or claim_names.get('groups')
    if not isinstance(source_name, str) or not source_name.strip():
        return False

    claim_sources = claims.get('_claim_sources')
    if isinstance(claim_sources, Mapping) and source_name.strip() not in claim_sources:
        return False
    return True


def _roles_from_groups(
    claims: Mapping[str, object],
    *,
    request: Request | None = None,
    email: str | None = None,
    external_id: str | None = None,
) -> tuple[str, ...]:
    groups_claim = (settings.oidc_groups_claim or 'groups').strip() or 'groups'
    if _groups_overage_detected(claims):
        logger.warning('OIDC groups overage detected; skipping groups fallback and relying on roles claim only.')
        return ()

    groups = _claim_values(claims, groups_claim, 'groups')
    if not groups:
        return ()

    configured_group_roles = settings.oidc_group_role_mappings
    casefold_group_roles = {group.casefold(): role for group, role in configured_group_roles.items()}
    external_roles = [
        casefold_group_roles[group.casefold()]
        for group in groups
        if group.casefold() in casefold_group_roles
    ]
    return _normalize_external_roles(
        tuple(external_roles),
        source=f'{groups_claim} fallback',
        request=request,
        email=email,
        external_id=external_id,
    )


def extract_identity(claims: Mapping[str, object], *, request: Request | None = None) -> ExternalIdentity:
    email = _coalesce_claim(claims, 'email', 'preferred_username', 'upn', 'unique_name')
    if not email:
        raise OIDCConfigurationError('OIDC provider did not return an email claim.')

    external_id = _coalesce_claim(claims, 'sub', 'oid', 'id')
    if not external_id:
        raise OIDCConfigurationError('OIDC provider did not return a stable subject claim.')

    display_name = _coalesce_claim(claims, 'name')
    if not display_name:
        given_name = _coalesce_claim(claims, 'given_name')
        family_name = _coalesce_claim(claims, 'family_name')
        display_name = ' '.join(part for part in (given_name, family_name) if part) or email.split('@', 1)[0]

    roles_claim = (settings.oidc_roles_claim or 'roles').strip() or 'roles'
    roles = _normalize_external_roles(
        _claim_values(claims, roles_claim, 'roles'),
        source=f'{roles_claim} claim',
        request=request,
        email=normalize_email(email),
        external_id=external_id,
    )
    if not roles:
        roles = _roles_from_groups(
            claims,
            request=request,
            email=normalize_email(email),
            external_id=external_id,
        )

    return ExternalIdentity(
        provider='oidc',
        external_id=external_id,
        email=normalize_email(email),
        display_name=display_name,
        roles=roles,
    )


async def begin_oidc_login(request: Request):
    _ensure_oidc_enabled()
    oauth = create_oauth_client()
    redirect_uri = str(request.url_for('oidc_callback'))
    try:
        return await oauth.oidc.authorize_redirect(request, redirect_uri)
    except Exception as exc:
        raise OIDCConfigurationError(_oidc_login_error_message(exc)) from exc


async def complete_oidc_login(request: Request) -> ExternalIdentity:
    _ensure_oidc_enabled()
    oauth = create_oauth_client()
    try:
        token = await oauth.oidc.authorize_access_token(request)
    except Exception as exc:
        logger.warning('OIDC callback token exchange failed.', exc_info=exc)
        raise OIDCConfigurationError(_oidc_callback_error_message(exc)) from exc

    claims: Mapping[str, object] | None = token.get('userinfo') if isinstance(token, dict) else None
    if claims is None:
        try:
            parsed = await oauth.oidc.parse_id_token(request, token)
        except Exception as exc:
            logger.warning('OIDC callback ID token parsing failed.', exc_info=exc)
            raise OIDCConfigurationError(_oidc_callback_error_message(exc)) from exc
        if isinstance(parsed, Mapping):
            claims = parsed

    if claims is None:
        raise OIDCConfigurationError('OIDC provider did not return user claims.')

    return extract_identity(claims, request=request)


async def verify_oidc_configuration() -> dict[str, Any]:
    discovery_url = (settings.oidc_discovery_url or '').strip() or None
    try:
        _ensure_oidc_enabled()
    except OIDCConfigurationError:
        return {
            'configured': False,
            'reachable': False,
            'message': 'OIDC is not configured.',
            'discovery_url': discovery_url,
            'issuer': None,
            'authorization_endpoint': None,
        }

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(discovery_url, headers={'Accept': 'application/json'})
            response.raise_for_status()
            metadata = response.json()
    except Exception as exc:
        logger.warning('OIDC discovery failed: %s', exc)
        return {
            'configured': True,
            'reachable': False,
            'message': 'OIDC provider discovery endpoint is unreachable.',
            'discovery_url': discovery_url,
            'issuer': None,
            'authorization_endpoint': None,
        }

    if not isinstance(metadata, Mapping):
        return {
            'configured': True,
            'reachable': False,
            'message': 'OIDC discovery endpoint returned invalid metadata.',
            'discovery_url': discovery_url,
            'issuer': None,
            'authorization_endpoint': None,
        }

    issuer = metadata.get('issuer')
    authorization_endpoint = metadata.get('authorization_endpoint')
    issuer_value = issuer.strip() if isinstance(issuer, str) and issuer.strip() else None
    authorization_value = authorization_endpoint.strip() if isinstance(authorization_endpoint, str) and authorization_endpoint.strip() else None
    if authorization_value is None:
        return {
            'configured': True,
            'reachable': False,
            'message': 'OIDC discovery endpoint is missing an authorization endpoint.',
            'discovery_url': discovery_url,
            'issuer': issuer_value,
            'authorization_endpoint': None,
        }

    return {
        'configured': True,
        'reachable': True,
        'message': 'OIDC discovery endpoint is reachable.',
        'discovery_url': discovery_url,
        'issuer': issuer_value,
        'authorization_endpoint': authorization_value,
    }
