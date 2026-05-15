from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import Request

from backend.config import settings
from backend.security import normalize_email, resolve_external_app_roles
from backend.services.auth_provisioning import ExternalIdentity

logger = logging.getLogger(__name__)

_COMMON_ROLE_ATTRIBUTES = (
    'http://schemas.microsoft.com/ws/2008/06/identity/claims/role',
    'Role',
    'role',
    'http://schemas.xmlsoap.org/claims/Group',
)

try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
    from onelogin.saml2.settings import OneLogin_Saml2_Settings
    SAML_TOOLKIT_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    OneLogin_Saml2_Auth = Any  # type: ignore[assignment]
    OneLogin_Saml2_IdPMetadataParser = Any  # type: ignore[assignment]
    OneLogin_Saml2_Settings = Any  # type: ignore[assignment]
    SAML_TOOLKIT_AVAILABLE = False


class SAMLConfigurationError(RuntimeError):
    """Raised when SAML is unavailable or an assertion is invalid."""


def _ensure_saml_enabled() -> None:
    missing = [
        name
        for name, value in {
            'SAML_METADATA_URL': settings.saml_metadata_url,
            'SAML_ENTITY_ID': settings.saml_entity_id,
            'SAML_ACS_URL': settings.saml_acs_url,
        }.items()
        if not (value or '').strip()
    ]
    if missing:
        raise SAMLConfigurationError('SAML authentication requires these settings: ' + ', '.join(missing))
    if not SAML_TOOLKIT_AVAILABLE:
        raise SAMLConfigurationError('SAML authentication requires the optional python3-saml dependency.')


def _sp_settings() -> dict[str, Any]:
    return {
        'strict': True,
        'debug': settings.testing,
        'sp': {
            'entityId': (settings.saml_entity_id or '').strip(),
            'assertionConsumerService': {
                'url': (settings.saml_acs_url or '').strip(),
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST',
            },
            'x509cert': '',
            'privateKey': '',
        },
        'security': {
            'authnRequestsSigned': False,
            'wantAssertionsSigned': True,
            'wantMessagesSigned': False,
            'wantNameId': True,
        },
    }


def build_saml_settings() -> dict[str, Any]:
    _ensure_saml_enabled()
    parsed_settings = OneLogin_Saml2_IdPMetadataParser.parse_remote((settings.saml_metadata_url or '').strip())
    return OneLogin_Saml2_IdPMetadataParser.merge_settings(parsed_settings, _sp_settings())


async def build_request_data(request: Request) -> dict[str, Any]:
    form_data = await request.form() if request.method.upper() == 'POST' else {}
    host = request.url.hostname or 'localhost'
    port = request.url.port
    if port and port not in {80, 443}:
        host = f'{host}:{port}'

    return {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': host,
        'server_port': str(port or (443 if request.url.scheme == 'https' else 80)),
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
        'post_data': dict(form_data),
    }


async def create_saml_auth(request: Request) -> OneLogin_Saml2_Auth:
    return OneLogin_Saml2_Auth(await build_request_data(request), old_settings=build_saml_settings())


def get_metadata_xml() -> str:
    settings_obj = OneLogin_Saml2_Settings(settings=build_saml_settings(), custom_base_path=None)
    metadata = settings_obj.get_sp_metadata()
    errors = settings_obj.validate_metadata(metadata)
    if errors:
        raise SAMLConfigurationError('SAML metadata is invalid: ' + ', '.join(errors))
    return metadata


def _first_attribute(attributes: Mapping[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        value = attributes.get(key)
        if value and isinstance(value, list):
            candidate = next((item.strip() for item in value if isinstance(item, str) and item.strip()), None)
            if candidate:
                return candidate
    return None


def _attribute_values(attributes: Mapping[str, list[str]], *keys: str) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for key in keys:
        raw_values = attributes.get(key)
        if not isinstance(raw_values, list):
            continue
        for raw_value in raw_values:
            if not isinstance(raw_value, str):
                continue
            candidate = raw_value.strip()
            if candidate and candidate not in seen:
                values.append(candidate)
                seen.add(candidate)
    return tuple(values)


def _role_attribute_names() -> tuple[str, ...]:
    configured = (settings.saml_role_attribute or '').strip()
    names = [configured] if configured else []
    for candidate in _COMMON_ROLE_ATTRIBUTES:
        if candidate not in names:
            names.append(candidate)
    return tuple(names)


def _extract_roles(attributes: Mapping[str, list[str]]) -> tuple[str, ...]:
    external_roles = _attribute_values(attributes, *_role_attribute_names())
    if not external_roles:
        return ()

    unmapped = sorted(
        {
            role
            for role in external_roles
            if role.strip() and role.strip().casefold() not in settings.external_role_mappings
        }
    )
    if unmapped:
        logger.warning('SAML assertion contained unmapped role values: %s', ', '.join(unmapped))
    return tuple(resolve_external_app_roles(list(external_roles)))


def extract_identity(auth: OneLogin_Saml2_Auth) -> ExternalIdentity:
    attributes = auth.get_attributes()
    email = _first_attribute(
        attributes,
        'email',
        'Email',
        'mail',
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name',
    )
    if not email:
        name_id = auth.get_nameid()
        if name_id and '@' in name_id:
            email = name_id
    if not email:
        raise SAMLConfigurationError('SAML assertion did not include an email address.')

    display_name = _first_attribute(
        attributes,
        'displayName',
        'DisplayName',
        'name',
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name',
    ) or email.split('@', 1)[0]

    external_id = auth.get_nameid() or email
    return ExternalIdentity(
        provider='saml',
        external_id=external_id,
        email=normalize_email(email),
        display_name=display_name,
        roles=_extract_roles(attributes),
    )


async def begin_saml_login(request: Request) -> str:
    _ensure_saml_enabled()
    auth = await create_saml_auth(request)
    return auth.login()


async def complete_saml_login(request: Request) -> ExternalIdentity:
    _ensure_saml_enabled()
    auth = await create_saml_auth(request)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        reason = getattr(auth, 'get_last_error_reason', lambda: None)()
        detail = ', '.join(errors)
        if reason:
            detail = f'{detail}: {reason}'
        raise SAMLConfigurationError(f'SAML sign-in failed: {detail}')
    if not auth.is_authenticated():
        raise SAMLConfigurationError('SAML assertion could not be authenticated.')
    return extract_identity(auth)
