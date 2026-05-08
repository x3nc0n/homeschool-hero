from __future__ import annotations

import os

import pytest

from tests.contracts import AUTH


@pytest.mark.asyncio
async def test_login_sets_family_session_cookie(async_client):
    response = await async_client.post(
        AUTH["login"],
        json={"method": "password", "credential": os.environ["FAMILY_PASSWORD"]},
    )

    assert response.status_code in {200, 204}, response.text
    assert any(cookie.name for cookie in async_client.cookies.jar), "expected session cookie after login"


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(async_client):
    response = await async_client.post(
        AUTH["login"],
        json={"method": "password", "credential": "definitely-wrong"},
    )

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_me_requires_authentication(async_client):
    response = await async_client.get(AUTH["me"])

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_logout_invalidates_session(async_client):
    login = await async_client.post(
        AUTH["login"],
        json={"method": "password", "credential": os.environ["FAMILY_PASSWORD"]},
    )
    assert login.status_code in {200, 204}, login.text

    logout = await async_client.post(AUTH["logout"])

    assert logout.status_code in {200, 204}, logout.text

    me = await async_client.get(AUTH["me"])
    assert me.status_code == 401, me.text
