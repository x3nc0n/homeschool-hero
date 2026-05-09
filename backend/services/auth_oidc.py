from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import Request

from backend.config import settings
from backend.security import normalize_email
from backend.services.auth_provisioning import ExternalIdentity

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


def _ensure_oidc_enabled() -> None:
    if settings.auth_provider.strip().lower() != 'oidc':
        raise OIDCConfigurationError('OIDC authentication is not enabled.')
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


def extract_identity(claims: Mapping[str, object]) -> ExternalIdentity:
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

    return ExternalIdentity(
        provider='oidc',
        external_id=external_id,
        email=normalize_email(email),
        display_name=display_name,
    )


async def begin_oidc_login(request: Request):
    _ensure_oidc_enabled()
    oauth = create_oauth_client()
    redirect_uri = str(request.url_for('oidc_callback'))
    return await oauth.oidc.authorize_redirect(request, redirect_uri)


async def complete_oidc_login(request: Request) -> ExternalIdentity:
    _ensure_oidc_enabled()
    oauth = create_oauth_client()
    try:
        token = await oauth.oidc.authorize_access_token(request)
    except OAuthError as exc:
        raise OIDCConfigurationError(f'OIDC sign-in failed: {exc.error}') from exc

    claims: Mapping[str, object] | None = token.get('userinfo') if isinstance(token, dict) else None
    if claims is None:
        try:
            parsed = await oauth.oidc.parse_id_token(request, token)
        except Exception:
            parsed = None
        if isinstance(parsed, Mapping):
            claims = parsed

    if claims is None:
        raise OIDCConfigurationError('OIDC provider did not return user claims.')

    return extract_identity(claims)
