from __future__ import annotations

import pytest

from backend.i18n import parse_accept_language
from tests.contracts import AUTH


def test_parse_accept_language_prefers_supported_locale() -> None:
    assert parse_accept_language('es-MX,es;q=0.9,en;q=0.8') == 'es'
    assert parse_accept_language('fr-CA,fr;q=0.9,en;q=0.4') == 'en'


@pytest.mark.asyncio
async def test_unauthenticated_error_localizes_to_spanish(async_client) -> None:
    response = await async_client.get(AUTH['me'], headers={'Accept-Language': 'es-MX,es;q=0.9'})

    assert response.status_code == 401, response.text
    payload = response.json()
    assert payload['detail'] == 'Autenticación requerida'
    assert payload['error']['message_key'] == 'errors.auth.required'
    assert payload['locale']['resolved'] == 'es'
    assert response.headers['Content-Language'] == 'es'
    assert response.headers['X-Date-Format-Hint'].startswith('locale=es;')


@pytest.mark.asyncio
async def test_login_error_falls_back_to_english_when_locale_unsupported(authorized_client, secondary_client) -> None:
    response = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': 'wrong-password'},
        headers={'Accept-Language': 'fr-FR,fr;q=0.9'},
    )

    assert response.status_code == 401, response.text
    payload = response.json()
    assert payload['detail'] == 'Invalid email or password'
    assert payload['error']['message_key'] == 'errors.auth.invalid_credentials'
    assert payload['locale']['resolved'] == 'en'
    assert response.headers['Content-Language'] == 'en'
