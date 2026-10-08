from __future__ import annotations

import asyncio
from copy import deepcopy
import ipaddress
import json
import logging
import mimetypes
import re
import socket
import time
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from docx import Document as DocxDocument
from pydantic import ValidationError
from pypdf import PdfReader

from backend.config import settings
from backend.local_ai import validate_local_ollama_host
from backend.schemas.curriculum import CurriculumImportDocument
from backend.services import ai_grader
from backend.services.logging_config import log_action

logger = logging.getLogger(__name__)
AI_IMPORT_TOOL_NAME = 'create_curriculum_import'
AI_IMPORT_SCHEMA_VERSION = '1.0'
RETRYABLE_PROVIDER_STATUS_CODES = frozenset({429, 502, 503, 504})
MAX_VALIDATION_ERROR_SUMMARY = 5
_FENCED_JSON_PATTERN = re.compile(r'^```[a-zA-Z0-9_-]*\s*\n?(.*?)\n?\s*```$', re.DOTALL)
AZURE_OPENAI_HOSTS = ('openai.azure.com',)
AZURE_DEPLOYMENTS_PATH_PREFIX = '/openai/deployments/'
ALLOWED_HTTP_SCHEMES = {'http', 'https'}
MAX_SOURCE_FETCH_REDIRECTS = 5
SUPPORTED_FILE_TYPES = {
    'text/plain',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
AI_IMPORT_SYSTEM_PROMPT = (
    'You are a curriculum import assistant. Convert raw source material into the homeschool curriculum JSON schema. '
    'Preserve the source structure when possible. Infer a sensible hierarchy of subjects, units, and lessons from '
    'scope-and-sequence documents, syllabi, textbook tables of contents, and lesson collections. Do not invent facts '
    'that are not supported by the source. Keep resource URLs only when they appear in the source. Prefer concise, '
    'clear names and descriptions. If the source is high level, create a lightweight unit/lesson outline instead of '
    'fabricating a detailed sequence.'
)
OLLAMA_JSON_INSTRUCTION = (
    ' Respond with a single JSON object that matches the provided JSON schema. Use JSON arrays for list fields and '
    'integers for numeric fields. Do not wrap the JSON in Markdown.'
)


def inline_json_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a Pydantic JSON schema with local $defs/$ref entries inlined."""
    schema_copy = deepcopy(schema)
    definitions = schema_copy.get('$defs')
    if not isinstance(definitions, dict):
        return schema_copy

    def _inline(value: Any) -> Any:
        if isinstance(value, dict):
            ref = value.get('$ref')
            if isinstance(ref, str) and ref.startswith('#/$defs/'):
                definition_name = ref.removeprefix('#/$defs/')
                definition = definitions.get(definition_name)
                if isinstance(definition, dict):
                    merged = deepcopy(definition)
                    for key, item in value.items():
                        if key != '$ref':
                            merged[key] = item
                    return _inline(merged)
            return {key: _inline(item) for key, item in value.items() if key != '$defs'}
        if isinstance(value, list):
            return [_inline(item) for item in value]
        return value

    return _inline(schema_copy)


class AIImportUnavailable(RuntimeError):
    """Raised when AI import is disabled or misconfigured."""


class AIImportError(RuntimeError):
    """Raised when AI import cannot extract or parse a source document.

    Messages are client-safe: they never include raw model output, source text, or validation input.
    """

    def __init__(self, message: str, *, code: str = 'ai_import_failed') -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class ExtractedSource:
    source_kind: str
    source_name: str
    content_type: str
    text: str
    source_url: str | None = None
    warnings: list[str] | None = None


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._parts.append(data.strip())

    def text(self) -> str:
        return ' '.join(self._parts)


class AICurriculumImportService:
    async def build_draft_from_upload(self, upload: Any) -> tuple[CurriculumImportDocument, ExtractedSource]:
        if upload is None:
            raise AIImportError('A file upload is required')
        self._ensure_configured()
        filename = getattr(upload, 'filename', None) or 'uploaded-document'
        content_type = getattr(upload, 'content_type', None) or ''
        payload = await upload.read()
        extracted = self._extract_from_bytes(
            payload,
            filename=filename,
            content_type=content_type,
            source_kind='file',
            source_name=filename,
        )
        return await self._build_draft(extracted)

    async def build_draft_from_url(self, url: str) -> tuple[CurriculumImportDocument, ExtractedSource]:
        if not settings.online_curriculum_enabled:
            raise AIImportUnavailable('Online curriculum URL imports are disabled by deployment policy.')
        self._ensure_configured()
        extracted = await self._extract_from_url(url)
        return await self._build_draft(extracted)

    async def build_draft_from_bytes(
        self,
        payload: bytes,
        *,
        filename: str,
        content_type: str,
    ) -> tuple[CurriculumImportDocument, ExtractedSource]:
        """Build a draft from an already bounded upload; extraction runs off the event loop."""
        self._ensure_configured()
        extracted = await asyncio.to_thread(
            self._extract_from_bytes,
            payload,
            filename=filename,
            content_type=content_type,
            source_kind='file',
            source_name=filename,
        )
        return await self._build_draft(extracted)

    def _ensure_configured(self) -> None:
        if not settings.ai_import_enabled:
            raise AIImportUnavailable('AI curriculum import is disabled. Set AI_IMPORT_ENABLED=true to enable it.')
        if settings.ai_local_only:
            if settings.ai_provider.strip().lower() != 'ollama':
                raise AIImportUnavailable('AI_LOCAL_ONLY=true requires AI_PROVIDER=ollama.')
            if (settings.ai_import_endpoint or '').strip():
                raise AIImportUnavailable(
                    'AI_IMPORT_ENDPOINT must be unset when AI_LOCAL_ONLY=true; curriculum import uses OLLAMA_HOST.'
                )
            if not settings.ollama_host.strip() or not settings.ollama_model.strip():
                raise AIImportUnavailable('OLLAMA_HOST and OLLAMA_MODEL must be configured for local AI import.')
            try:
                validate_local_ollama_host(settings.ollama_host)
            except ValueError as exc:
                raise AIImportUnavailable(str(exc)) from exc
            return
        endpoint = (settings.ai_import_endpoint or '').strip()
        if not endpoint:
            raise AIImportUnavailable('AI curriculum import is not configured. Set AI_IMPORT_ENDPOINT.')
        parsed_endpoint = urlparse(endpoint)
        # Azure OpenAI authenticates via managed identity; non-Azure endpoints still require an API key.
        if not self._is_azure_openai_endpoint(parsed_endpoint) and not (settings.ai_import_api_key or '').strip():
            raise AIImportUnavailable('AI curriculum import is not configured. Set AI_IMPORT_API_KEY.')

    async def _extract_from_url(self, url: str) -> ExtractedSource:
        timeout = httpx.Timeout(settings.ai_import_request_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await self._fetch_validated_source_url(client, url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AIImportError(
                f'Unable to fetch the provided URL (HTTP {exc.response.status_code})',
                code='source_extraction_failed',
            ) from None
        except httpx.HTTPError:
            raise AIImportError('Unable to fetch the provided URL', code='source_extraction_failed') from None

        content_type = (response.headers.get('content-type') or '').split(';', 1)[0].strip().lower()
        filename = Path(urlparse(str(response.url)).path).name or 'url-import'
        if content_type == 'text/html' or not content_type:
            text = self._extract_html_text(response.text)
            extracted = ExtractedSource(
                source_kind='url',
                source_name=filename,
                content_type=content_type or 'text/html',
                text=text,
                source_url=str(response.url),
                warnings=[],
            )
            return self._finalize_extracted_source(extracted)
        return self._extract_from_bytes(
            response.content,
            filename=filename,
            content_type=content_type,
            source_kind='url',
            source_name=filename,
            source_url=str(response.url),
        )

    def _extract_from_bytes(
        self,
        payload: bytes,
        *,
        filename: str,
        content_type: str,
        source_kind: str,
        source_name: str,
        source_url: str | None = None,
    ) -> ExtractedSource:
        if not payload:
            raise AIImportError('The provided document is empty')
        normalized_type = self._detect_content_type(filename=filename, content_type=content_type)
        if normalized_type not in SUPPORTED_FILE_TYPES:
            supported = ', '.join(sorted(SUPPORTED_FILE_TYPES))
            raise AIImportError(f'Unsupported document type for AI import. Supported types: {supported}')
        if normalized_type == 'text/plain':
            text = self._decode_text(payload)
        elif normalized_type == 'application/pdf':
            text = self._extract_pdf_text(payload)
        else:
            text = self._extract_docx_text(payload)
        extracted = ExtractedSource(
            source_kind=source_kind,
            source_name=source_name,
            content_type=normalized_type,
            text=text,
            source_url=source_url,
            warnings=[],
        )
        return self._finalize_extracted_source(extracted)

    def _finalize_extracted_source(self, extracted: ExtractedSource) -> ExtractedSource:
        normalized_text = ' '.join((extracted.text or '').split())
        if not normalized_text:
            raise AIImportError('The document did not contain readable text for AI import')
        warnings = list(extracted.warnings or [])
        if len(normalized_text) > settings.ai_import_max_input_chars:
            normalized_text = normalized_text[: settings.ai_import_max_input_chars].rstrip()
            warnings.append('Source text was truncated before sending it to the AI parser.')
        extracted.text = normalized_text
        extracted.warnings = warnings
        return extracted

    def _detect_content_type(self, *, filename: str, content_type: str) -> str:
        normalized = (content_type or '').split(';', 1)[0].strip().lower()
        if normalized in SUPPORTED_FILE_TYPES:
            return normalized
        guessed, _ = mimetypes.guess_type(filename)
        guessed = (guessed or '').lower()
        if guessed in SUPPORTED_FILE_TYPES:
            return guessed
        suffix = Path(filename).suffix.lower()
        if suffix == '.txt':
            return 'text/plain'
        if suffix == '.pdf':
            return 'application/pdf'
        if suffix == '.docx':
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        return normalized

    def _decode_text(self, payload: bytes) -> str:
        for encoding in ('utf-8', 'utf-8-sig', 'latin-1'):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise AIImportError('The text document could not be decoded')

    def _extract_pdf_text(self, payload: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(payload))
        except Exception:  # noqa: BLE001
            raise AIImportError('Unable to read PDF document', code='source_extraction_failed') from None
        text_parts: list[str] = []
        for page in reader.pages:
            try:
                text_parts.append(page.extract_text() or '')
            except Exception:  # noqa: BLE001
                continue
        return '\n'.join(part for part in text_parts if part.strip())

    def _extract_docx_text(self, payload: bytes) -> str:
        try:
            document = DocxDocument(BytesIO(payload))
        except Exception:  # noqa: BLE001
            raise AIImportError('Unable to read DOCX document', code='source_extraction_failed') from None
        return '\n'.join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())

    def _extract_html_text(self, html: str) -> str:
        parser = _HTMLTextExtractor()
        parser.feed(html)
        return unescape(parser.text())

    async def _fetch_validated_source_url(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        current_url = url
        for redirect_count in range(MAX_SOURCE_FETCH_REDIRECTS + 1):
            validated_source_url = self._validate_public_source_url(
                current_url,
                error_message='AI import URL must be a valid http or https URL',
            )
            # Reconstruct URL from parsed components to break CodeQL taint chain.
            # The validation above already confirmed scheme, netloc, hostname are safe.
            parsed = urlparse(validated_source_url)
            safe_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
            response = await client.get(safe_url)
            if not response.is_redirect:
                return response

            redirect_target = response.headers.get('location')
            if not redirect_target:
                return response
            if redirect_count >= MAX_SOURCE_FETCH_REDIRECTS:
                break
            current_url = urljoin(str(response.url), redirect_target)

        raise AIImportError('AI import URL exceeded the maximum allowed redirects')

    def _validate_public_source_url(self, url: str, *, error_message: str) -> str:
        normalized_url, parsed = self._parse_http_url(url, error_message=error_message)
        self._ensure_public_hostname(parsed.hostname or '')
        return normalized_url

    def _parse_http_url(self, url: str, *, error_message: str) -> tuple[str, Any]:
        normalized_url = (url or '').strip()
        parsed = urlparse(normalized_url)
        if parsed.scheme not in ALLOWED_HTTP_SCHEMES or not parsed.netloc or not parsed.hostname:
            raise AIImportError(error_message)
        return normalized_url, parsed

    def _ensure_public_hostname(self, hostname: str) -> None:
        resolved_addresses = self._resolve_hostname_addresses(hostname)
        if any(self._is_disallowed_network_address(address) for address in resolved_addresses):
            raise AIImportError('AI import URL must resolve to a public host')

    def _resolve_hostname_addresses(self, hostname: str) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        try:
            return {ipaddress.ip_address(hostname)}
        except ValueError:
            pass

        try:
            addrinfo = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise AIImportError('AI import URL must include a resolvable hostname') from exc

        resolved_addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
        for _family, _socktype, _proto, _canonname, sockaddr in addrinfo:
            try:
                resolved_addresses.add(ipaddress.ip_address(sockaddr[0]))
            except ValueError:
                continue
        if not resolved_addresses:
            raise AIImportError('AI import URL must include a resolvable hostname')
        return resolved_addresses

    def _is_disallowed_network_address(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        )

    async def _build_draft(self, extracted: ExtractedSource) -> tuple[CurriculumImportDocument, ExtractedSource]:
        payload = await self._call_ai_parser(extracted)
        payload = self._apply_source_defaults(payload, extracted)
        try:
            document = CurriculumImportDocument.model_validate(payload)
        except ValidationError as exc:
            summary = _summarize_validation_error(exc)
            log_action(
                logger,
                logging.WARNING,
                'AI curriculum draft failed schema validation.',
                action='curriculum_ai_import.draft_invalid',
                details={'error_count': exc.error_count(), 'errors': summary},
            )
            raise AIImportError(
                f'AI returned a curriculum draft that does not match the import schema ({exc.error_count()} validation error(s)).',
                code='ai_response_invalid',
            ) from None
        except ValueError:
            raise AIImportError('AI returned an invalid curriculum draft.', code='ai_response_invalid') from None
        return document, extracted

    def _apply_source_defaults(self, payload: dict[str, Any], extracted: ExtractedSource) -> dict[str, Any]:
        draft = dict(payload)
        metadata = draft.get('metadata') if isinstance(draft.get('metadata'), dict) else {}
        external_source = metadata.get('external_source') if isinstance(metadata.get('external_source'), dict) else {}
        if extracted.source_url and 'url' not in external_source:
            external_source['url'] = extracted.source_url
        external_source.setdefault('source_name', extracted.source_name)
        external_source.setdefault('source_kind', extracted.source_kind)
        metadata['external_source'] = external_source
        draft['metadata'] = metadata
        draft['source'] = 'ai-import'
        draft['schema_version'] = AI_IMPORT_SCHEMA_VERSION
        draft.setdefault('name', extracted.source_name)
        return draft

    async def _call_ai_parser(self, extracted: ExtractedSource) -> dict[str, Any]:
        if settings.ai_local_only:
            # Local-only mode always uses the native Ollama chat API; there is never a cloud fallback.
            provider = 'ollama'
            request_url = f'{settings.ollama_host.rstrip("/")}/api/chat'
            request_params: dict[str, str] | None = None
            headers = {'Content-Type': 'application/json'}
            payload = self._build_ollama_payload(extracted)
            parse_response = self._parse_ollama_response
        else:
            provider = 'remote'
            endpoint = settings.ai_import_endpoint.strip()
            _, parsed_endpoint = self._parse_http_url(
                endpoint,
                error_message='AI import endpoint must be a valid http or https URL',
            )
            if self._is_azure_openai_endpoint(parsed_endpoint):
                request_url = self._azure_chat_completions_url(endpoint, parsed_endpoint)
                request_params = {'api-version': settings.ai_import_api_version}
            else:
                request_url = endpoint
                request_params = None
            headers = self._build_headers(endpoint)
            payload = self._build_request_payload(extracted)
            parse_response = self._parse_ai_response
        body = await self._post_with_transport_retries(
            request_url,
            headers=headers,
            params=request_params,
            payload=payload,
            provider=provider,
        )
        try:
            parsed = parse_response(body)
        except AIImportError as exc:
            log_action(
                logger,
                logging.WARNING,
                'AI curriculum import response could not be parsed.',
                action='curriculum_ai_import.response_invalid',
                details={'provider': provider, 'code': exc.code},
            )
            raise
        return self._coerce_stringified_lists(parsed, _curriculum_import_schema())

    async def _post_with_transport_retries(
        self,
        request_url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None,
        payload: dict[str, Any],
        provider: str,
    ) -> Any:
        """POST to the provider, retrying only transient transport failures (never parse/schema errors)."""
        timeout = httpx.Timeout(settings.ai_import_request_timeout_seconds)
        backoff = max(settings.ai_import_retry_backoff_seconds, 0.0)
        attempts = max(settings.ai_import_retry_attempts, 1)
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            failure_kind: str
            status_code: int | None = None
            try:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=True,
                    trust_env=not settings.ai_local_only,
                ) as client:
                    response = await client.post(request_url, headers=headers, params=params, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code not in RETRYABLE_PROVIDER_STATUS_CODES:
                    self._log_provider_attempt(provider, attempt, started, outcome='http_error', status_code=status_code)
                    raise AIImportError(
                        f'The AI provider rejected the curriculum import request (HTTP {status_code}).',
                        code='ai_provider_error',
                    ) from None
                failure_kind = 'retryable_http_error'
            except httpx.TimeoutException:
                failure_kind = 'timeout'
            except httpx.TransportError:
                failure_kind = 'transport_error'
            else:
                self._log_provider_attempt(provider, attempt, started, outcome='ok', status_code=response.status_code)
                try:
                    return response.json()
                except ValueError:
                    raise AIImportError(
                        'The AI provider returned a response that was not valid JSON.',
                        code='ai_response_invalid',
                    ) from None
            self._log_provider_attempt(provider, attempt, started, outcome=failure_kind, status_code=status_code)
            if attempt < attempts:
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
        if failure_kind == 'timeout':
            raise AIImportError('The AI provider timed out while drafting the curriculum.', code='ai_provider_timeout')
        raise AIImportError('The AI provider could not be reached to draft the curriculum.', code='ai_provider_error')

    def _log_provider_attempt(
        self,
        provider: str,
        attempt: int,
        started: float,
        *,
        outcome: str,
        status_code: int | None,
    ) -> None:
        log_action(
            logger,
            logging.INFO if outcome == 'ok' else logging.WARNING,
            'AI curriculum import provider call finished.',
            action='curriculum_ai_import.provider_call',
            details={
                'provider': provider,
                'attempt': attempt,
                'outcome': outcome,
                'status_code': status_code,
                'duration_ms': int((time.monotonic() - started) * 1000),
            },
        )

    def _build_ollama_payload(self, extracted: ExtractedSource) -> dict[str, Any]:
        return {
            'model': settings.ollama_model,
            'messages': [
                {'role': 'system', 'content': AI_IMPORT_SYSTEM_PROMPT + OLLAMA_JSON_INSTRUCTION},
                {'role': 'user', 'content': self._build_user_prompt(extracted)},
            ],
            'format': _curriculum_import_schema(),
            'stream': False,
            'options': {'temperature': 0},
        }

    def _build_user_prompt(self, extracted: ExtractedSource) -> str:
        return (
            f'Source type: {extracted.source_kind}\n'
            f'Source name: {extracted.source_name}\n'
            f'Content type: {extracted.content_type}\n'
            f'Source URL: {extracted.source_url or "N/A"}\n\n'
            'Document text:\n'
            f'{extracted.text}'
        )

    def _parse_ollama_response(self, body: Any) -> dict[str, Any]:
        message = body.get('message') if isinstance(body, dict) else None
        content = message.get('content') if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise AIImportError('The AI provider returned an empty curriculum draft.', code='ai_response_invalid')
        return _decode_json_object(content)

    def _coerce_stringified_lists(self, value: Any, schema: dict[str, Any]) -> Any:
        """Decode list fields that a model returned as JSON strings, guided by the import schema.

        A string is replaced only when it decodes to a JSON list; anything else is left untouched
        so schema validation still rejects it.
        """
        if isinstance(value, str) and _schema_allows(schema, 'array') and not _schema_allows(schema, 'string'):
            decoded = _try_decode_json(value)
            if isinstance(decoded, list):
                value = decoded
        if isinstance(value, dict):
            properties = _schema_properties(schema)
            return {
                key: self._coerce_stringified_lists(item, properties[key]) if key in properties else item
                for key, item in value.items()
            }
        if isinstance(value, list):
            item_schema = _schema_items(schema)
            if item_schema is None:
                return value
            return [self._coerce_stringified_lists(item, item_schema) for item in value]
        return value

    def _build_headers(self, endpoint: str) -> dict[str, str]:
        _, parsed_endpoint = self._parse_http_url(
            endpoint,
            error_message='AI import endpoint must be a valid http or https URL',
        )
        api_key = (settings.ai_import_api_key or '').strip()
        if self._is_azure_openai_endpoint(parsed_endpoint):
            headers = {'Content-Type': 'application/json'}
            if api_key:
                headers['api-key'] = api_key
            else:
                headers['Authorization'] = 'Bearer ' + self._azure_ad_token()
            return headers
        return {
            'Authorization': f'Bearer {settings.ai_import_api_key.strip()}',
            'Content-Type': 'application/json',
        }

    def _build_request_payload(self, extracted: ExtractedSource, *, model: str | None = None) -> dict[str, Any]:
        prompt = self._build_user_prompt(extracted)
        payload: dict[str, Any] = {
            'temperature': 0,
            'messages': [
                {'role': 'system', 'content': AI_IMPORT_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            'tools': [
                {
                    'type': 'function',
                    'function': {
                        'name': AI_IMPORT_TOOL_NAME,
                        'description': 'Return a homeschool curriculum import document.',
                        'parameters': inline_json_schema_refs(CurriculumImportDocument.model_json_schema()),
                    },
                }
            ],
            'tool_choice': {'type': 'function', 'function': {'name': AI_IMPORT_TOOL_NAME}},
        }
        if model is not None:
            payload['model'] = model
        elif not settings.ai_local_only:
            endpoint = settings.ai_import_endpoint.strip()
            _, parsed_endpoint = self._parse_http_url(
                endpoint,
                error_message='AI import endpoint must be a valid http or https URL',
            )
            if not self._is_azure_openai_endpoint(parsed_endpoint):
                payload['model'] = settings.ai_import_model
        return payload

    def _is_azure_openai_endpoint(self, parsed_endpoint: Any) -> bool:
        host = (parsed_endpoint.hostname or '').lower()
        return any(host == azure_host or host.endswith(f'.{azure_host}') for azure_host in AZURE_OPENAI_HOSTS)

    def _azure_chat_completions_url(self, endpoint: str, parsed_endpoint: Any) -> str:
        if parsed_endpoint.path.startswith(AZURE_DEPLOYMENTS_PATH_PREFIX):
            return endpoint
        # Fall back to the grader's deployment when a dedicated import deployment isn't configured.
        deployment = (settings.ai_import_deployment or settings.azure_openai_deployment or '').strip()
        if not deployment:
            raise AIImportUnavailable(
                'AI curriculum import is not configured. '
                'Set AI_IMPORT_DEPLOYMENT (or AZURE_OPENAI_DEPLOYMENT) for the Azure OpenAI endpoint.'
            )
        base = endpoint.rstrip('/')
        return f'{base}{AZURE_DEPLOYMENTS_PATH_PREFIX}{deployment}/chat/completions'

    def _azure_ad_token(self) -> str:
        try:
            return ai_grader._get_azure_ad_token()
        except ai_grader.AIServiceUnavailable as exc:
            raise AIImportUnavailable(f'AI curriculum import managed-identity auth failed: {exc}') from exc

    def _parse_ai_response(self, body: dict[str, Any]) -> dict[str, Any]:
        choices = body.get('choices') if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            raise AIImportError('AI response did not include any choices', code='ai_response_invalid')
        message = (choices[0].get('message') if isinstance(choices[0], dict) else None) or {}
        tool_calls = message.get('tool_calls') if isinstance(message, dict) else None
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                function = tool_call.get('function') if isinstance(tool_call, dict) else None
                if not isinstance(function, dict):
                    continue
                if function.get('name') != AI_IMPORT_TOOL_NAME:
                    continue
                arguments = function.get('arguments') or '{}'
                if isinstance(arguments, dict):
                    return arguments
                return _decode_json_object(arguments)
        content = message.get('content') if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return _decode_json_object(content)
        raise AIImportError('AI response did not include a curriculum tool call', code='ai_response_invalid')


def _curriculum_import_schema() -> dict[str, Any]:
    return inline_json_schema_refs(CurriculumImportDocument.model_json_schema())


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _FENCED_JSON_PATTERN.match(stripped)
    return match.group(1).strip() if match else stripped


def _try_decode_json(text: str) -> Any:
    try:
        return json.loads(_strip_code_fence(text))
    except (TypeError, ValueError):
        return None


def _decode_json_object(text: str) -> dict[str, Any]:
    """Decode a JSON object, accepting a single surrounding Markdown code fence."""
    try:
        parsed = json.loads(_strip_code_fence(text))
    except (TypeError, ValueError):
        raise AIImportError('The AI provider returned a curriculum draft that was not valid JSON.', code='ai_response_invalid') from None
    if not isinstance(parsed, dict):
        raise AIImportError('The AI provider returned a curriculum draft that was not a JSON object.', code='ai_response_invalid')
    return parsed


def _schema_variants(schema: dict[str, Any]) -> list[dict[str, Any]]:
    variants = [schema]
    for key in ('anyOf', 'oneOf', 'allOf'):
        options = schema.get(key)
        if isinstance(options, list):
            variants.extend(option for option in options if isinstance(option, dict))
    return variants


def _schema_allows(schema: dict[str, Any], json_type: str) -> bool:
    for variant in _schema_variants(schema):
        declared = variant.get('type')
        if declared == json_type or (isinstance(declared, list) and json_type in declared):
            return True
    return False


def _schema_properties(schema: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for variant in _schema_variants(schema):
        if isinstance(variant.get('properties'), dict):
            properties.update(variant['properties'])
    return properties


def _schema_items(schema: dict[str, Any]) -> dict[str, Any] | None:
    for variant in _schema_variants(schema):
        if isinstance(variant.get('items'), dict):
            return variant['items']
    return None


def _summarize_validation_error(exc: ValidationError) -> list[dict[str, str]]:
    """Summarize validation failures by location and type only; never include input values."""
    return [
        {'loc': '.'.join(str(part) for part in error.get('loc', ())), 'type': str(error.get('type', ''))}
        for error in exc.errors(include_url=False, include_context=False, include_input=False)[:MAX_VALIDATION_ERROR_SUMMARY]
    ]


_service: AICurriculumImportService | None = None


def get_ai_curriculum_import_service() -> AICurriculumImportService:
    global _service
    if _service is None:
        _service = AICurriculumImportService()
    return _service
