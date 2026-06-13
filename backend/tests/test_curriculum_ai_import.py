from __future__ import annotations

from io import BytesIO
import json
import socket

import httpx
import pytest
from docx import Document as DocxDocument
from reportlab.pdfgen import canvas

from backend.services.curriculum_ai_import import AIImportError, AICurriculumImportService, ExtractedSource
from tests.contracts import CURRICULUM
from tests.helpers import response_id


class _FakeAIAsyncClient:
    requests: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        self.requests.append({'url': url, 'headers': headers, 'json': json})
        request = httpx.Request('POST', url)
        body = {
            'choices': [
                {
                    'message': {
                        'tool_calls': [
                            {
                                'function': {
                                    'name': 'create_curriculum_import',
                                    'arguments': json_module.dumps(
                                        {
                                            'name': 'AI Draft Curriculum',
                                            'description': 'Generated from uploaded text.',
                                            'source': 'manual',
                                            'subjects': [
                                                {
                                                    'name': 'Language Arts',
                                                    'units': [
                                                        {
                                                            'name': 'Semester 1',
                                                            'lessons': [
                                                                {
                                                                    'name': 'Lesson 1',
                                                                    'description': 'Read and discuss the source.',
                                                                    'objectives': ['Identify major themes'],
                                                                    'resources': [],
                                                                }
                                                            ],
                                                        }
                                                    ],
                                                }
                                            ],
                                        }
                                    ),
                                }
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=body, request=request)


json_module = json


class _RedirectingURLAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):  # noqa: ARG002
        request = httpx.Request('GET', url)
        if url == 'https://example.com/curriculum.txt':
            return httpx.Response(
                302,
                headers={'location': 'http://127.0.0.1/private.txt'},
                request=request,
            )
        raise AssertionError(f'unexpected fetch url: {url}')


def _build_pdf_bytes(text: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


def _build_docx_bytes(text: str) -> bytes:
    document = DocxDocument()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_ai_import_returns_service_unavailable_when_disabled(authorized_client, monkeypatch):
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', False, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', None, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_api_key', None, raising=False)

    response = await authorized_client.post(CURRICULUM['ai_import'], json={'url': 'https://example.com/curriculum.txt'})

    assert response.status_code == 503, response.text
    assert response.json()['detail'] == 'AI curriculum import is unavailable'


@pytest.mark.asyncio
async def test_ai_import_upload_and_confirm_flow(authorized_client, monkeypatch):
    _FakeAIAsyncClient.requests.clear()
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', 'https://api.openai.com/v1/chat/completions', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_api_key', 'test-key', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_retry_attempts', 1, raising=False)
    monkeypatch.setattr('backend.services.curriculum_ai_import.httpx.AsyncClient', _FakeAIAsyncClient)

    draft_response = await authorized_client.post(
        CURRICULUM['ai_import'],
        files={'file': ('scope.txt', b'Math scope and sequence with lessons and units.', 'text/plain')},
    )
    assert draft_response.status_code == 200, draft_response.text
    draft_payload = draft_response.json()
    assert draft_payload['draft']['name'] == 'AI Draft Curriculum'
    assert draft_payload['draft']['source'] == 'ai-import'
    assert draft_payload['source_kind'] == 'file'
    assert _FakeAIAsyncClient.requests[0]['json']['tools'][0]['function']['name'] == 'create_curriculum_import'

    reviewed_draft = draft_payload['draft']
    reviewed_draft['name'] = 'Reviewed AI Curriculum'
    confirm_response = await authorized_client.post(
        CURRICULUM['ai_import_confirm'],
        json={'draft': reviewed_draft},
    )
    assert confirm_response.status_code == 201, confirm_response.text
    confirm_payload = confirm_response.json()
    curriculum_id = response_id(confirm_payload)
    assert confirm_payload['name'] == 'Reviewed AI Curriculum'
    assert confirm_payload['source'] == 'ai-import'

    detail = await authorized_client.get(CURRICULUM['import_detail'].format(curriculum_id=curriculum_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()['subjects'][0]['units'][0]['lessons'][0]['name'] == 'Lesson 1'


def test_ai_import_service_extracts_pdf_and_docx_text():
    service = AICurriculumImportService()

    pdf_extracted = service._extract_from_bytes(
        _build_pdf_bytes('PDF algebra outline'),
        filename='outline.pdf',
        content_type='application/pdf',
        source_kind='file',
        source_name='outline.pdf',
    )
    docx_extracted = service._extract_from_bytes(
        _build_docx_bytes('DOCX biology syllabus'),
        filename='syllabus.docx',
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        source_kind='file',
        source_name='syllabus.docx',
    )

    assert 'PDF algebra outline' in pdf_extracted.text
    assert 'DOCX biology syllabus' in docx_extracted.text


def test_ai_import_service_rejects_unsupported_file_types():
    service = AICurriculumImportService()

    with pytest.raises(AIImportError):
        service._extract_from_bytes(
            b'<xml></xml>',
            filename='curriculum.xml',
            content_type='application/xml',
            source_kind='file',
            source_name='curriculum.xml',
        )


def test_ai_import_service_rejects_non_public_urls():
    service = AICurriculumImportService()

    with pytest.raises(AIImportError, match='valid http or https URL'):
        service._parse_http_url('file:///etc/passwd', error_message='AI import URL must be a valid http or https URL')

    with pytest.raises(AIImportError, match='public host'):
        service._ensure_public_hostname('127.0.0.1')


def test_ai_import_service_rejects_hostnames_that_resolve_to_private_ips(monkeypatch):
    service = AICurriculumImportService()

    def _fake_getaddrinfo(hostname, port, type=0):  # noqa: ARG001
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.10', 0))]

    monkeypatch.setattr('backend.services.curriculum_ai_import.socket.getaddrinfo', _fake_getaddrinfo)

    with pytest.raises(AIImportError, match='public host'):
        service._ensure_public_hostname('curriculum.example.com')


@pytest.mark.asyncio
async def test_ai_import_service_blocks_redirects_to_private_hosts(monkeypatch):
    service = AICurriculumImportService()
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', 'https://api.openai.com/v1/chat/completions', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_api_key', 'test-key', raising=False)
    monkeypatch.setattr('backend.services.curriculum_ai_import.httpx.AsyncClient', _RedirectingURLAsyncClient)

    with pytest.raises(AIImportError, match='public host'):
        await service.build_draft_from_url('https://example.com/curriculum.txt')


def test_ai_import_service_uses_urlparse_for_endpoint_detection(monkeypatch):
    service = AICurriculumImportService()
    monkeypatch.setattr('backend.config.settings.ai_import_api_key', 'test-key', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', 'https://school.openai.azure.com/openai/deployments/draft/chat/completions', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_model', 'ignored-model', raising=False)

    extracted = ExtractedSource(
        source_kind='url',
        source_name='scope.txt',
        content_type='text/plain',
        text='Algebra scope and sequence',
        source_url='https://example.com/scope.txt',
        warnings=[],
    )

    headers = service._build_headers('https://school.openai.azure.com/openai/deployments/draft/chat/completions')
    payload = service._build_request_payload(extracted)

    assert headers == {'api-key': 'test-key', 'Content-Type': 'application/json'}
    assert 'model' not in payload
