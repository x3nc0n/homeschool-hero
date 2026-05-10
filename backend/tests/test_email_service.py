from __future__ import annotations

import sys
import types

from backend.config import Settings
from backend.services.capabilities import check_email
from backend.services.email_service import check_provider_health, email_enabled, send_email


def test_email_provider_none_disables_email() -> None:
    config = Settings().model_copy(update={'email_provider': 'none', 'testing': True})

    result = check_provider_health(config)

    assert email_enabled(config) is False
    assert result['name'] == 'email'
    assert result['enabled'] is False
    assert result['configured'] is False
    assert result['status'] == 'disabled'
    assert 'EMAIL_PROVIDER' in result['reason']


def test_check_email_reports_acs_configuration(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeEmailClient:
        @classmethod
        def from_connection_string(cls, connection_string: str):  # noqa: ANN206
            seen['connection_string'] = connection_string
            return cls()

    azure_module = types.ModuleType('azure')
    communication_module = types.ModuleType('azure.communication')
    email_module = types.ModuleType('azure.communication.email')
    email_module.EmailClient = FakeEmailClient
    monkeypatch.setitem(sys.modules, 'azure', azure_module)
    monkeypatch.setitem(sys.modules, 'azure.communication', communication_module)
    monkeypatch.setitem(sys.modules, 'azure.communication.email', email_module)

    config = Settings().model_copy(
        update={
            'email_provider': 'acs',
            'acs_connection_string': 'endpoint=https://mail.test/;accesskey=fake',
            'acs_sender_address': 'DoNotReply@example.azurecomm.net',
            'testing': True,
        }
    )

    result = check_email(config)

    assert email_enabled(config) is True
    assert seen['connection_string'] == config.acs_connection_string
    assert result['enabled'] is True
    assert result['configured'] is True
    assert result['details']['provider'] == 'acs'
    assert result['details']['sender'] == config.acs_sender_address


def test_send_email_uses_acs_provider(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakePoller:
        def result(self) -> dict[str, str]:
            return {'id': 'message-123', 'status': 'Succeeded'}

    class FakeEmailClient:
        @classmethod
        def from_connection_string(cls, connection_string: str):  # noqa: ANN206
            seen['connection_string'] = connection_string
            return cls()

        def begin_send(self, message: dict[str, object]) -> FakePoller:
            seen['message'] = message
            return FakePoller()

    azure_module = types.ModuleType('azure')
    communication_module = types.ModuleType('azure.communication')
    email_module = types.ModuleType('azure.communication.email')
    email_module.EmailClient = FakeEmailClient
    monkeypatch.setitem(sys.modules, 'azure', azure_module)
    monkeypatch.setitem(sys.modules, 'azure.communication', communication_module)
    monkeypatch.setitem(sys.modules, 'azure.communication.email', email_module)

    config = Settings().model_copy(
        update={
            'email_provider': 'acs',
            'acs_connection_string': 'endpoint=https://mail.test/;accesskey=fake',
            'acs_sender_address': 'DoNotReply@example.azurecomm.net',
            'testing': True,
        }
    )

    send_email(
        to_email='family@example.com',
        subject='Welcome',
        html='<strong>Hello</strong>',
        config=config,
    )

    assert seen['connection_string'] == config.acs_connection_string
    assert seen['message'] == {
        'senderAddress': 'DoNotReply@example.azurecomm.net',
        'recipients': {'to': [{'address': 'family@example.com'}]},
        'content': {
            'subject': 'Welcome',
            'html': '<strong>Hello</strong>',
            'plainText': 'This email contains HTML content. Please view it in an HTML-capable client.',
        },
    }
