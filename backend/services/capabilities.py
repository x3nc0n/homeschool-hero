from __future__ import annotations

import asyncio
import logging
import os
import shutil
import smtplib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytesseract

from backend.config import Settings, settings

logger = logging.getLogger(__name__)


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
    provider = (config.auth_provider or 'local').strip().lower() or 'local'
    available_providers = ['local']
    if provider in {'oidc', 'saml'}:
        available_providers.append(provider)
    return {
        'current_provider': provider,
        'available_providers': available_providers,
        'local_enabled': True,
        'oidc_enabled': provider == 'oidc',
        'saml_enabled': provider == 'saml',
    }


def check_ai_grading(config: Settings = settings) -> dict[str, Any]:
    provider = config.ai_provider.strip().lower() or 'ollama'

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
    if not config.smtp_host or not config.smtp_from_email:
        return _status(
            'email',
            enabled=False,
            configured=False,
            reason='SMTP_HOST and SMTP_FROM_EMAIL must be configured to enable email.',
            details={},
        )

    if config.smtp_username and not config.smtp_password:
        return _status(
            'email',
            enabled=False,
            configured=False,
            reason='SMTP_PASSWORD is required when SMTP_USERNAME is configured.',
            details={'host': config.smtp_host, 'port': config.smtp_port},
        )

    server: smtplib.SMTP | None = None
    try:
        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=5)
        server.ehlo()
        if config.smtp_use_tls:
            server.starttls()
            server.ehlo()
        if config.smtp_username:
            server.login(config.smtp_username, config.smtp_password or '')
        code, _ = server.noop()
        if code >= 400:
            raise RuntimeError(f'SMTP NOOP returned {code}')
    except Exception as exc:
        return _status(
            'email',
            enabled=False,
            configured=True,
            reason=f'SMTP is unreachable: {exc}',
            details={'host': config.smtp_host, 'port': config.smtp_port},
        )
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

    return _status(
        'email',
        enabled=True,
        configured=True,
        reason='SMTP is reachable.',
        details={'host': config.smtp_host, 'port': config.smtp_port},
    )


def check_backup(config: Settings = settings) -> dict[str, Any]:
    if not config.backup_target:
        return _status(
            'backup',
            enabled=False,
            configured=False,
            reason='BACKUP_TARGET is not configured.',
            details={},
        )

    target = Path(config.backup_target)
    try:
        if target.exists():
            if not target.is_dir():
                raise RuntimeError('target exists but is not a directory')
            if not os.access(target, os.W_OK):
                raise RuntimeError('target directory is not writable')
        else:
            parent = target.parent if str(target.parent) not in {'', '.'} else Path('.')
            if not parent.exists():
                raise RuntimeError('parent directory does not exist')
            if not parent.is_dir():
                raise RuntimeError('parent path is not a directory')
            if not os.access(parent, os.W_OK):
                raise RuntimeError('parent directory is not writable')
    except Exception as exc:
        return _status(
            'backup',
            enabled=False,
            configured=True,
            reason=f'Backup target is unavailable: {exc}',
            details={'target': str(target)},
        )

    return _status(
        'backup',
        enabled=True,
        configured=True,
        reason='Backup target is configured.',
        details={'target': str(target)},
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
