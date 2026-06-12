from __future__ import annotations

import pytest

from tests.contracts import AUTH, USERS, bootstrap_payload
from tests.helpers import sync_csrf_header


@pytest.mark.asyncio
async def test_auth_session_includes_default_user_preferences(authorized_client):
    response = await authorized_client.get(AUTH['me'])

    assert response.status_code == 200, response.text
    assert response.json()['ui_preferences'] == {
        'theme': 'system',
        'accent_color': '#2563eb',
        'font_size': 'medium',
        'density': 'comfortable',
        'sidebar_position': 'left',
    }


@pytest.mark.asyncio
async def test_user_preferences_endpoint_persists_changes(authorized_client, secondary_client):
    update = await authorized_client.put(
        USERS['preferences'],
        json={
            'theme': 'high-contrast',
            'accent_color': '#7c3aed',
            'font_size': 'large',
            'density': 'compact',
            'sidebar_position': 'right',
        },
    )

    assert update.status_code == 200, update.text
    assert update.json()['theme'] == 'high-contrast'

    logout = await authorized_client.post(AUTH['logout'])
    assert logout.status_code in {200, 204}, logout.text

    login = await secondary_client.post(
        AUTH['login'],
        json={'email': 'owner@example.com', 'password': bootstrap_payload()['password']},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)
    assert login.json()['ui_preferences'] == {
        'theme': 'high-contrast',
        'accent_color': '#7c3aed',
        'font_size': 'large',
        'density': 'compact',
        'sidebar_position': 'right',
    }

    fetch = await secondary_client.get(USERS['preferences'])
    assert fetch.status_code == 200, fetch.text
    assert fetch.json()['sidebar_position'] == 'right'
