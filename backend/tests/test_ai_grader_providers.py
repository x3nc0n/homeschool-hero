from __future__ import annotations

from typing import Any

import pytest

from backend.services import ai_grader
from backend.services.ai_grader import AIServiceUnavailable


class _FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._body


class _FakeClient:
    """Records the last POST and returns a canned chat-completion response."""

    calls: list[dict[str, Any]] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def post(self, url: str, *, headers: dict[str, str] | None = None, params: dict[str, str] | None = None, json: dict[str, Any] | None = None) -> _FakeResponse:
        _FakeClient.calls.append({'url': url, 'headers': headers or {}, 'params': params or {}, 'json': json or {}})
        content = '{"score": 91, "confidence": 0.88, "feedback": "Solid reasoning."}'
        return _FakeResponse({'choices': [{'message': {'content': content}}]})


@pytest.fixture(autouse=True)
def _reset_calls() -> None:
    _FakeClient.calls = []


def _configure_azure(monkeypatch: pytest.MonkeyPatch, *, api_key: str | None = None) -> None:
    monkeypatch.setattr(ai_grader.httpx, 'Client', _FakeClient)
    monkeypatch.setattr(ai_grader.settings, 'ai_provider', 'azure_openai')
    monkeypatch.setattr(ai_grader.settings, 'azure_openai_endpoint', 'https://acct.openai.azure.com/')
    monkeypatch.setattr(ai_grader.settings, 'azure_openai_deployment', 'gpt-4o')
    monkeypatch.setattr(ai_grader.settings, 'azure_openai_api_version', '2024-10-21')
    monkeypatch.setattr(ai_grader.settings, 'azure_openai_api_key', api_key)


def test_azure_openai_dispatch_uses_managed_identity_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_azure(monkeypatch, api_key=None)
    monkeypatch.setattr(ai_grader, '_get_azure_ad_token', lambda: 'fake-mi-token')

    result = ai_grader.grade_submission_text('Fractions', '1) 3/4', '1) 3/4')

    assert result['unavailable'] is False
    assert result['score'] == 91
    assert result['confidence'] == pytest.approx(0.88)

    call = _FakeClient.calls[-1]
    assert call['url'] == 'https://acct.openai.azure.com/openai/deployments/gpt-4o/chat/completions'
    assert call['params'] == {'api-version': '2024-10-21'}
    assert call['headers'].get('Authorization') == 'Bearer fake-mi-token'
    assert 'api-key' not in call['headers']


def test_azure_openai_dispatch_prefers_api_key_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_azure(monkeypatch, api_key='secret-key-123')

    def _fail() -> str:
        raise AssertionError('managed identity must not be used when API key is configured')

    monkeypatch.setattr(ai_grader, '_get_azure_ad_token', _fail)

    result = ai_grader.grade_submission_text('Fractions', None, '1) 3/4')

    assert result['unavailable'] is False
    call = _FakeClient.calls[-1]
    assert call['headers'].get('api-key') == 'secret-key-123'
    assert 'Authorization' not in call['headers']


def test_azure_openai_requires_endpoint_and_deployment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_grader.httpx, 'Client', _FakeClient)
    monkeypatch.setattr(ai_grader.settings, 'ai_provider', 'azure_openai')
    monkeypatch.setattr(ai_grader.settings, 'azure_openai_endpoint', None)
    monkeypatch.setattr(ai_grader.settings, 'azure_openai_deployment', None)

    with pytest.raises(AIServiceUnavailable):
        ai_grader.azure_openai_chat_url(ai_grader.settings)

    # Grading degrades gracefully instead of raising to the caller.
    result = ai_grader.grade_submission_text('Fractions', None, '1) 3/4')
    assert result['unavailable'] is True


def test_openai_model_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_grader.httpx, 'Client', _FakeClient)
    monkeypatch.setattr(ai_grader.settings, 'ai_provider', 'openai')
    monkeypatch.setattr(ai_grader.settings, 'openai_api_key', 'sk-test')
    monkeypatch.setattr(ai_grader.settings, 'openai_model', 'gpt-4o')

    result = ai_grader.grade_submission_text('Fractions', None, '1) 3/4')

    assert result['unavailable'] is False
    call = _FakeClient.calls[-1]
    assert call['json'].get('model') == 'gpt-4o'
