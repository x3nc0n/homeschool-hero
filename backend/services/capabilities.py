from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytesseract

from backend.config import Settings, settings
from backend.services.backup_service import get_backup_configuration, validate_backup_configuration

logger = logging.getLogger(__name__)

_AZURE_PROVIDER_ALIASES = {'azure_openai', 'azure', 'foundry', 'azure-openai'}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status(name: str, *, enabled: bool, configured: bool, reason: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'name': name,
        'enabled': enabled,
        'configured': configured,
        'status': 'enabled' if enabled else 'disabled',
        'reason': reason,
        'details': details or {},
        'checked_at': _timestamp(),
    }


def get_auth_providers(config: Settings = settings) -> dict[str, Any]:
    provider = config.normalized_auth_provider
    local_enabled = config.local_auth_enabled
    oidc_enabled = config.oidc_configured
    saml_enabled = config.saml_configured

    available_providers: list[str] = []
    if local_enabled:
        available_providers.append('local')
    if oidc_enabled:
        available_providers.append('oidc')
    if saml_enabled:
        available_providers.append('saml')

    return {
        'current_provider': provider,
        'available_providers': available_providers,
        'local_enabled': local_enabled,
        'oidc_enabled': oidc_enabled,
        'saml_enabled': saml_enabled,
    }


def _check_azure_openai_grading(config: Settings, provider: str) -> dict[str, Any]:
    endpoint = (config.azure_openai_endpoint or '').strip()
    deployment = (config.azure_openai_deployment or '').strip()
    if not endpoint or not deployment:
        return _status(
            'ai_grading',
            enabled=False,
            configured=False,
            reason='AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT must be configured for Azure OpenAI grading.',
            details={'provider': provider},
        )

    from backend.services.ai_grader import AIServiceUnavailable, azure_openai_chat_url, azure_openai_request_headers

    details = {'provider': provider, 'endpoint': endpoint, 'deployment': deployment}
    try:
        headers = azure_openai_request_headers(config)
        url = azure_openai_chat_url(config)
        probe_body = {'messages': [{'role': 'user', 'content': 'ping'}], 'max_tokens': 1}
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                url,
                headers=headers,
                params={'api-version': config.azure_openai_api_version},
                json=probe_body,
            )
    except AIServiceUnavailable as exc:
        return _status(
            'ai_grading',
            enabled=False,
            configured=True,
            reason=f'Azure OpenAI authentication failed: {exc}',
            details=details,
        )
    except Exception as exc:  # noqa: BLE001 - report any reachability failure uniformly
        return _status(
            'ai_grading',
            enabled=False,
            configured=True,
            reason=f'Azure OpenAI is unreachable: {exc}',
            details=details,
        )

    # The least-privilege "Cognitive Services OpenAI User" role permits inference but not
    # management operations (e.g. list-deployments returns 404). A minimal chat/completions
    # call returns 200 (or a model-layer 4xx such as invalid_request_error) when the deployment
    # is reachable; only auth/permission (401/403) or server (5xx) responses indicate the
    # provider is genuinely unavailable.
    status_code = response.status_code
    details = {**details, 'status_code': status_code}
    if status_code in (401, 403):
        return _status(
            'ai_grading',
            enabled=False,
            configured=True,
            reason=f'Azure OpenAI authorization failed (HTTP {status_code}).',
            details=details,
        )
    if status_code >= 500:
        return _status(
            'ai_grading',
            enabled=False,
            configured=True,
            reason=f'Azure OpenAI is unreachable (HTTP {status_code}).',
            details=details,
        )

    return _status(
        'ai_grading',
        enabled=True,
        configured=True,
        reason='Azure OpenAI is reachable.',
        details=details,
    )


def check_ai_grading(config: Settings = settings) -> dict[str, Any]:
    provider = config.ai_provider.strip().lower() or 'ollama'

    if provider in _AZURE_PROVIDER_ALIASES:
        return _check_azure_openai_grading(config, provider)

    if provider == 'openai':
        if not config.openai_api_key:
            return _status(
                'ai_grading',
                enabled=False,
                configured=False,
                reason='OpenAI API key is not configured.',
                details={'provider': provider},
            )

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    'https://api.openai.com/v1/models',
                    headers={'Authorization': f'Bearer {config.openai_api_key}'},
                )
                response.raise_for_status()
        except Exception as exc:
            return _status(
                'ai_grading',
                enabled=False,
                configured=True,
                reason=f'OpenAI is unreachable: {exc}',
                details={'provider': provider},
            )

        return _status(
            'ai_grading',
            enabled=True,
            configured=True,
            reason='OpenAI is reachable.',
            details={'provider': provider},
        )

    if provider != 'ollama':
        return _status(
            'ai_grading',
            enabled=False,
            configured=False,
            reason=f"Unsupported AI provider '{provider}'.",
            details={'provider': provider},
        )

    if not config.ollama_host.strip() or not config.ollama_model.strip():
        return _status(
            'ai_grading',
            enabled=False,
            configured=False,
            reason='OLLAMA_HOST and OLLAMA_MODEL must be configured for Ollama grading.',
            details={'provider': provider},
        )

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{config.ollama_host.rstrip('/')}/api/tags")
            response.raise_for_status()
        body = response.json()
    except Exception as exc:
        return _status(
            'ai_grading',
            enabled=False,
            configured=True,
            reason=f'Ollama is unreachable: {exc}',
            details={'provider': provider, 'host': config.ollama_host},
        )

    configured_model = config.ollama_model.strip()
    available_models = {
        str(model.get('name', '')).strip()
        for model in body.get('models', [])
        if isinstance(model, dict)
    }
    model_available = any(
        name == configured_model or name == f'{configured_model}:latest' or name.startswith(f'{configured_model}:')
        for name in available_models
    )
    if not model_available:
        return _status(
            'ai_grading',
            enabled=False,
            configured=True,
            reason=f"Ollama model '{configured_model}' is not loaded.",
            details={'provider': provider, 'host': config.ollama_host, 'model': configured_model},
        )

    return _status(
        'ai_grading',
        enabled=True,
        configured=True,
        reason='Ollama is reachable.',
        details={'provider': provider, 'host': config.ollama_host, 'model': configured_model},
    )


def check_email(config: Settings = settings) -> dict[str, Any]:
    from backend.services.email_service import check_provider_health

    return check_provider_health(config)


def check_backup(config: Settings = settings) -> dict[str, Any]:
    if not config.backup_target:
        return _status(
            'backup',
            enabled=False,
            configured=False,
            reason='BACKUP_TARGET is not configured.',
            details={},
        )

    try:
        validate_backup_configuration(config)
        details = get_backup_configuration(config)
    except Exception as exc:
        return _status(
            'backup',
            enabled=False,
            configured=True,
            reason=f'Backup target is unavailable: {exc}',
            details={'target': str(config.backup_target)},
        )

    return _status(
        'backup',
        enabled=True,
        configured=True,
        reason='Backup target is configured.',
        details={
            'target': str(config.backup_target),
            'destination': getattr(details['destination'], 'value', details['destination']),
            'schedule': details['schedule'],
            'restic_enabled': details['restic_enabled'],
        },
    )


def check_ocr(_: Settings = settings) -> dict[str, Any]:
    executable = shutil.which('tesseract')
    if not executable:
        return _status(
            'ocr',
            enabled=False,
            configured=False,
            reason='Tesseract is not installed or not on PATH.',
            details={},
        )

    try:
        version = str(pytesseract.get_tesseract_version())
    except Exception as exc:
        return _status(
            'ocr',
            enabled=False,
            configured=True,
            reason=f'Tesseract could not be queried: {exc}',
            details={'path': executable},
        )

    return _status(
        'ocr',
        enabled=True,
        configured=True,
        reason='Tesseract is available.',
        details={'path': executable, 'version': version},
    )


class CapabilityRegistry:
    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    def check_all_sync(self) -> dict[str, dict[str, Any]]:
        capabilities = {
            'ai_grading': check_ai_grading(self._config),
            'email': check_email(self._config),
            'backup': check_backup(self._config),
            'ocr': check_ocr(self._config),
        }
        disabled = [item for item in capabilities.values() if not item['enabled']]
        for item in disabled:
            logger.warning('Capability unavailable: %s (%s)', item['name'], item['reason'])
        return capabilities

    def check_one_sync(self, name: str) -> dict[str, Any]:
        return self.check_all_sync()[name]

    async def check_all(self) -> dict[str, dict[str, Any]]:
        return await asyncio.to_thread(self.check_all_sync)


capability_registry = CapabilityRegistry()


def get_capability_registry() -> CapabilityRegistry:
    return capability_registry
