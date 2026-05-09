from __future__ import annotations

from typing import Any

DEFAULT_LOCALE = 'en'
SUPPORTED_LOCALES = ('en', 'es')
DATE_FORMAT_HINT = {
    'locale': DEFAULT_LOCALE,
    'date_style': 'medium',
    'time_style': 'short',
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    'errors.auth.required': {
        'en': 'Authentication required',
        'es': 'Autenticación requerida',
    },
    'errors.auth.invalid_credentials': {
        'en': 'Invalid email or password',
        'es': 'Correo o contraseña inválidos',
    },
    'errors.auth.locked': {
        'en': 'Account temporarily locked. Try again later.',
        'es': 'La cuenta está bloqueada temporalmente. Inténtalo más tarde.',
    },
    'errors.auth.bootstrap_unavailable': {
        'en': 'Bootstrap is no longer available',
        'es': 'La configuración inicial ya no está disponible',
    },
    'errors.security.csrf_failed': {
        'en': 'CSRF validation failed',
        'es': 'La validación CSRF falló',
    },
    'errors.request.invalid': {
        'en': 'Invalid request.',
        'es': 'Solicitud inválida.',
    },
    'errors.request.internal': {
        'en': 'An unexpected error occurred.',
        'es': 'Ocurrió un error inesperado.',
    },
    'errors.request.rate_limited': {
        'en': 'Too many requests. Please try again later.',
        'es': 'Demasiadas solicitudes. Inténtalo más tarde.',
    },
    'errors.request.failed': {
        'en': 'Request failed',
        'es': 'La solicitud falló',
    },
    'errors.maintenance.active': {
        'en': 'Service is temporarily unavailable.',
        'es': 'El servicio no está disponible temporalmente.',
    },
}

LEGACY_MESSAGE_KEYS: dict[str, tuple[str, str]] = {
    'Authentication required': ('errors.auth.required', 'Authentication required'),
    'Invalid email or password': ('errors.auth.invalid_credentials', 'Invalid email or password'),
    'Account temporarily locked. Try again later.': ('errors.auth.locked', 'Account temporarily locked. Try again later.'),
    'Bootstrap is no longer available': ('errors.auth.bootstrap_unavailable', 'Bootstrap is no longer available'),
    'CSRF validation failed': ('errors.security.csrf_failed', 'CSRF validation failed'),
    'Invalid request.': ('errors.request.invalid', 'Invalid request.'),
    'An unexpected error occurred.': ('errors.request.internal', 'An unexpected error occurred.'),
    'Too many requests. Please try again later.': ('errors.request.rate_limited', 'Too many requests. Please try again later.'),
    'Request failed': ('errors.request.failed', 'Request failed'),
}


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    primary = value.strip().lower().split('-')[0]
    if primary in SUPPORTED_LOCALES:
        return primary
    return DEFAULT_LOCALE


def parse_accept_language(header: str | None) -> str:
    if not header:
        return DEFAULT_LOCALE

    candidates: list[tuple[float, str]] = []
    for part in header.split(','):
        token = part.strip()
        if not token:
            continue
        language, _, params = token.partition(';')
        quality = 1.0
        if params:
            for attribute in params.split(';'):
                attribute = attribute.strip()
                if attribute.startswith('q='):
                    try:
                        quality = float(attribute[2:])
                    except ValueError:
                        quality = 0.0
        candidates.append((quality, normalize_locale(language)))

    if not candidates:
        return DEFAULT_LOCALE

    candidates.sort(key=lambda item: item[0], reverse=True)
    for _, locale in candidates:
        if locale in SUPPORTED_LOCALES:
            return locale
    return DEFAULT_LOCALE


def translate(message_key: str | None, locale: str, default_message: str) -> str:
    if not message_key:
        return default_message
    translations = TRANSLATIONS.get(message_key, {})
    return translations.get(locale) or translations.get(DEFAULT_LOCALE) or default_message


def error_detail(*, code: str, message_key: str, default_message: str, details: Any | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'code': code,
        'message_key': message_key,
        'default_message': default_message,
    }
    if details is not None:
        payload['details'] = details
    return payload


def build_locale_guidance(locale: str, requested_locale: str | None = None) -> dict[str, Any]:
    return {
        'requested': requested_locale,
        'resolved': locale,
        'fallback': DEFAULT_LOCALE,
        'date_format': {
            **DATE_FORMAT_HINT,
            'locale': locale,
        },
    }


def build_error_payload(
    detail: Any,
    *,
    locale: str,
    requested_locale: str | None = None,
    fallback_code: str = 'http_error',
    fallback_message: str = 'Request failed',
) -> dict[str, Any]:
    code = fallback_code
    message_key: str | None = None
    default_message = fallback_message
    details = None

    if isinstance(detail, dict):
        code = str(detail.get('code') or fallback_code)
        message_key = detail.get('message_key') if isinstance(detail.get('message_key'), str) else None
        default_message = str(detail.get('default_message') or fallback_message)
        details = detail.get('details')
    elif isinstance(detail, str):
        mapped = LEGACY_MESSAGE_KEYS.get(detail)
        if mapped:
            message_key, default_message = mapped
        else:
            default_message = detail
    elif detail is not None:
        default_message = str(detail)

    message = translate(message_key, locale, default_message)
    payload: dict[str, Any] = {
        'detail': message,
        'error': {
            'code': code,
            'message': message,
        },
        'locale': build_locale_guidance(locale, requested_locale),
    }
    if message_key:
        payload['error']['message_key'] = message_key
    if details is not None:
        payload['error']['details'] = details
    return payload
