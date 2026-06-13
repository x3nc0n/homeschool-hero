from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from docx import Document as DocxDocument
from pypdf import PdfReader

from backend.config import settings
from backend.schemas.curriculum import CurriculumImportDocument

logger = logging.getLogger(__name__)
AI_IMPORT_TOOL_NAME = 'create_curriculum_import'
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


class AIImportUnavailable(RuntimeError):
    """Raised when AI import is disabled or misconfigured."""


class AIImportError(RuntimeError):
    """Raised when AI import cannot extract or parse a source document."""


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
        self._ensure_configured()
        normalized_url = self._normalize_url(url)
        extracted = await self._extract_from_url(normalized_url)
        return await self._build_draft(extracted)

    def _ensure_configured(self) -> None:
        if not settings.ai_import_enabled:
            raise AIImportUnavailable('AI curriculum import is disabled. Set AI_IMPORT_ENABLED=true to enable it.')
        if not (settings.ai_import_endpoint or '').strip():
            raise AIImportUnavailable('AI curriculum import is not configured. Set AI_IMPORT_ENDPOINT.')
        if not (settings.ai_import_api_key or '').strip():
            raise AIImportUnavailable('AI curriculum import is not configured. Set AI_IMPORT_API_KEY.')

    async def _extract_from_url(self, url: str) -> ExtractedSource:
        timeout = httpx.Timeout(settings.ai_import_request_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIImportError(f'Unable to fetch the provided URL: {exc}') from exc

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
        except Exception as exc:  # noqa: BLE001
            raise AIImportError(f'Unable to read PDF document: {exc}') from exc
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
        except Exception as exc:  # noqa: BLE001
            raise AIImportError(f'Unable to read DOCX document: {exc}') from exc
        return '\n'.join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())

    def _extract_html_text(self, html: str) -> str:
        parser = _HTMLTextExtractor()
        parser.feed(html)
        return unescape(parser.text())

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise AIImportError('AI import URL must be a valid http or https URL')
        return url.strip()

    async def _build_draft(self, extracted: ExtractedSource) -> tuple[CurriculumImportDocument, ExtractedSource]:
        payload = await self._call_ai_parser(extracted)
        payload = self._apply_source_defaults(payload, extracted)
        try:
            document = CurriculumImportDocument.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            raise AIImportError(f'AI returned an invalid curriculum draft: {exc}') from exc
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
        draft.setdefault('name', extracted.source_name)
        return draft

    async def _call_ai_parser(self, extracted: ExtractedSource) -> dict[str, Any]:
        endpoint = settings.ai_import_endpoint.strip()
        headers = self._build_headers(endpoint)
        payload = self._build_request_payload(extracted)
        timeout = httpx.Timeout(settings.ai_import_request_timeout_seconds)
        backoff = max(settings.ai_import_retry_backoff_seconds, 0.0)
        last_error: Exception | None = None
        for attempt in range(1, max(settings.ai_import_retry_attempts, 1) + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
                return self._parse_ai_response(body)
            except (httpx.HTTPError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= max(settings.ai_import_retry_attempts, 1):
                    break
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
        raise AIImportError(f'AI curriculum import failed: {last_error}')

    def _build_headers(self, endpoint: str) -> dict[str, str]:
        if 'openai.azure.com' in endpoint or '/openai/deployments/' in endpoint:
            return {'api-key': settings.ai_import_api_key.strip(), 'Content-Type': 'application/json'}
        return {
            'Authorization': f'Bearer {settings.ai_import_api_key.strip()}',
            'Content-Type': 'application/json',
        }

    def _build_request_payload(self, extracted: ExtractedSource) -> dict[str, Any]:
        prompt = (
            f'Source type: {extracted.source_kind}\n'
            f'Source name: {extracted.source_name}\n'
            f'Content type: {extracted.content_type}\n'
            f'Source URL: {extracted.source_url or "N/A"}\n\n'
            'Document text:\n'
            f'{extracted.text}'
        )
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
                        'parameters': CurriculumImportDocument.model_json_schema(),
                    },
                }
            ],
            'tool_choice': {'type': 'function', 'function': {'name': AI_IMPORT_TOOL_NAME}},
        }
        endpoint = settings.ai_import_endpoint.strip()
        if 'openai.azure.com' not in endpoint and '/openai/deployments/' not in endpoint:
            payload['model'] = settings.ai_import_model
        return payload

    def _parse_ai_response(self, body: dict[str, Any]) -> dict[str, Any]:
        choices = body.get('choices') if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            raise AIImportError('AI response did not include any choices')
        message = choices[0].get('message') or {}
        tool_calls = message.get('tool_calls') if isinstance(message, dict) else None
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                function = tool_call.get('function') if isinstance(tool_call, dict) else None
                if not isinstance(function, dict):
                    continue
                if function.get('name') != AI_IMPORT_TOOL_NAME:
                    continue
                arguments = function.get('arguments') or '{}'
                parsed = json.loads(arguments)
                if isinstance(parsed, dict):
                    return parsed
        content = message.get('content') if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        raise AIImportError('AI response did not include a curriculum tool call')


_service: AICurriculumImportService | None = None


def get_ai_curriculum_import_service() -> AICurriculumImportService:
    global _service
    if _service is None:
        _service = AICurriculumImportService()
    return _service
