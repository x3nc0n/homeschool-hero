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
    options: dict = {}

    def __init__(self, *args, **kwargs):
        type(self).options = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, params=None, json=None):
        self.requests.append({'url': url, 'headers': headers, 'params': params, 'json': json})
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


def _contains_json_schema_ref(value):
    if isinstance(value, dict):
        if '$ref' in value or '$defs' in value:
            return True
        return any(_contains_json_schema_ref(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_json_schema_ref(item) for item in value)
    return False


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
    monkeypatch.setattr('backend.config.settings.ai_local_only', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_provider', 'ollama', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', None, raising=False)
    monkeypatch.setattr('backend.config.settings.ollama_host', 'http://192.168.50.135:11434', raising=False)
    monkeypatch.setattr('backend.config.settings.ollama_model', 'llama3.1:8b', raising=False)
    monkeypatch.setattr('backend.config.settings.online_curriculum_enabled', False, raising=False)
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
    assert _FakeAIAsyncClient.requests[0]['url'] == 'http://192.168.50.135:11434/v1/chat/completions'
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


@pytest.mark.asyncio
async def test_offline_ai_import_rejects_url_before_fetch(authorized_client, monkeypatch):
    monkeypatch.setattr('backend.config.settings.online_curriculum_enabled', False, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_local_only', False, raising=False)

    def fail_if_fetch_attempted():
        raise AssertionError('offline AI URL import must be rejected before service initialization')

    monkeypatch.setattr(
        'backend.routers.curriculum.get_ai_curriculum_import_service',
        fail_if_fetch_attempted,
    )

    response = await authorized_client.post(
        CURRICULUM['ai_import'],
        json={'url': 'https://example.com/curriculum.txt'},
    )

    assert response.status_code == 503
    assert response.json()['detail'] == 'Online curriculum URL imports are disabled by deployment policy'


@pytest.mark.asyncio
async def test_ai_import_service_rejects_url_when_online_curriculum_disabled(monkeypatch):
    from backend.services.curriculum_ai_import import AIImportUnavailable

    monkeypatch.setattr('backend.config.settings.online_curriculum_enabled', False, raising=False)

    with pytest.raises(AIImportUnavailable, match='Online curriculum URL imports are disabled'):
        await AICurriculumImportService().build_draft_from_url('https://example.com/curriculum.txt')


@pytest.mark.asyncio
async def test_local_only_ai_import_uses_ollama_compatible_endpoint(monkeypatch):
    _FakeAIAsyncClient.requests.clear()
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_local_only', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_provider', 'ollama', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', None, raising=False)
    monkeypatch.setattr('backend.config.settings.ollama_host', 'http://192.168.50.135:11434', raising=False)
    monkeypatch.setattr('backend.config.settings.ollama_model', 'qwen2.5:14b', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_retry_attempts', 1, raising=False)
    monkeypatch.setattr('backend.services.curriculum_ai_import.httpx.AsyncClient', _FakeAIAsyncClient)

    service = AICurriculumImportService()
    service._ensure_configured()
    extracted = ExtractedSource(
        source_kind='file',
        source_name='scope.txt',
        content_type='text/plain',
        text='Algebra scope and sequence',
        warnings=[],
    )

    result = await service._call_ai_parser(extracted)

    request = _FakeAIAsyncClient.requests[0]
    assert request['url'] == 'http://192.168.50.135:11434/v1/chat/completions'
    assert request['headers'] == {'Content-Type': 'application/json'}
    assert request['params'] is None
    assert request['json']['model'] == 'qwen2.5:14b'
    assert request['json']['tools'][0]['function']['name'] == 'create_curriculum_import'
    assert _FakeAIAsyncClient.options['trust_env'] is False
    assert result['name'] == 'AI Draft Curriculum'


def test_ai_import_parses_ollama_tool_arguments_as_object():
    service = AICurriculumImportService()
    parsed = service._parse_ai_response(
        {
            'choices': [
                {
                    'message': {
                        'tool_calls': [
                            {
                                'function': {
                                    'name': 'create_curriculum_import',
                                    'arguments': {'name': 'Local draft'},
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )

    assert parsed == {'name': 'Local draft'}


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


def test_ai_import_tool_schema_inlines_refs():
    service = AICurriculumImportService()
    payload = service._build_request_payload(
        ExtractedSource(
            source_kind='file',
            source_name='scope.txt',
            content_type='text/plain',
            text='Algebra scope and sequence',
            warnings=[],
        ),
        model='llama3.1:8b',
    )
    schema = payload['tools'][0]['function']['parameters']

    assert not _contains_json_schema_ref(schema)


def test_ai_import_azure_base_url_uses_managed_identity(monkeypatch):
    service = AICurriculumImportService()
    base_endpoint = 'https://homeschoolhero-prod-openai.openai.azure.com/'
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', base_endpoint, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_api_key', None, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_deployment', 'curriculum-import', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_api_version', '2024-10-21', raising=False)
    monkeypatch.setattr(
        'backend.services.curriculum_ai_import.ai_grader._get_azure_ad_token',
        lambda: 'managed-identity-token',
    )

    # Managed-identity auth is used when no API key is present on an Azure endpoint.
    service._ensure_configured()
    headers = service._build_headers(base_endpoint)
    assert headers['Content-Type'] == 'application/json'
    assert headers['Authorization'].endswith('managed-identity-token')
    assert 'api-key' not in headers

    # The base URL is expanded into the deployment-scoped chat-completions URL.
    from urllib.parse import urlparse

    request_url = service._azure_chat_completions_url(base_endpoint, urlparse(base_endpoint))
    assert request_url == (
        'https://homeschoolhero-prod-openai.openai.azure.com'
        '/openai/deployments/curriculum-import/chat/completions'
    )


def test_ai_import_azure_base_url_requires_deployment(monkeypatch):
    service = AICurriculumImportService()
    from urllib.parse import urlparse

    from backend.services.curriculum_ai_import import AIImportUnavailable

    base_endpoint = 'https://homeschoolhero-prod-openai.openai.azure.com/'
    monkeypatch.setattr('backend.config.settings.ai_import_deployment', None, raising=False)
    monkeypatch.setattr('backend.config.settings.azure_openai_deployment', None, raising=False)

    with pytest.raises(AIImportUnavailable, match='AI_IMPORT_DEPLOYMENT'):
        service._azure_chat_completions_url(base_endpoint, urlparse(base_endpoint))


def test_ai_import_azure_endpoint_does_not_require_api_key(monkeypatch):
    service = AICurriculumImportService()
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr(
        'backend.config.settings.ai_import_endpoint',
        'https://homeschoolhero-prod-openai.openai.azure.com/',
        raising=False,
    )
    monkeypatch.setattr('backend.config.settings.ai_import_api_key', None, raising=False)

    service._ensure_configured()  # must not raise: Azure uses managed identity


def test_ai_import_azure_deployment_fallback_to_grader_deployment(monkeypatch):
    """AI_IMPORT_DEPLOYMENT absent → falls back to AZURE_OPENAI_DEPLOYMENT (gpt-4o)."""
    service = AICurriculumImportService()
    from urllib.parse import urlparse

    base_endpoint = 'https://homeschoolhero-prod-openai.openai.azure.com/'
    monkeypatch.setattr('backend.config.settings.ai_import_deployment', None, raising=False)
    monkeypatch.setattr('backend.config.settings.azure_openai_deployment', 'gpt-4o', raising=False)

    request_url = service._azure_chat_completions_url(base_endpoint, urlparse(base_endpoint))
    assert request_url == (
        'https://homeschoolhero-prod-openai.openai.azure.com'
        '/openai/deployments/gpt-4o/chat/completions'
    )


def test_ai_import_non_azure_endpoint_uses_bearer_auth(monkeypatch):
    """Non-Azure endpoint with API key sends Authorization: Bearer; never sends api-key header."""
    service = AICurriculumImportService()
    monkeypatch.setattr('backend.config.settings.ai_import_api_key', 'sk-test-key', raising=False)

    headers = service._build_headers('https://api.openai.com/v1/chat/completions')

    assert headers['Authorization'] == 'Bearer sk-test-key'
    assert 'api-key' not in headers


@pytest.mark.asyncio
async def test_ai_import_azure_call_includes_api_version_param(monkeypatch):
    """Azure _call_ai_parser sends api-version as a query param and uses managed-identity auth."""
    _FakeAIAsyncClient.requests.clear()
    base_endpoint = 'https://homeschoolhero-prod-openai.openai.azure.com/'
    monkeypatch.setattr('backend.config.settings.ai_import_enabled', True, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_endpoint', base_endpoint, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_api_key', None, raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_deployment', 'gpt-4o', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_api_version', '2024-10-21', raising=False)
    monkeypatch.setattr('backend.config.settings.ai_import_retry_attempts', 1, raising=False)
    monkeypatch.setattr(
        'backend.services.curriculum_ai_import.ai_grader._get_azure_ad_token',
        lambda: 'managed-identity-token',
    )
    monkeypatch.setattr('backend.services.curriculum_ai_import.httpx.AsyncClient', _FakeAIAsyncClient)

    service = AICurriculumImportService()
    extracted = ExtractedSource(
        source_kind='file',
        source_name='scope.txt',
        content_type='text/plain',
        text='Algebra scope and sequence',
        source_url=None,
        warnings=[],
    )

    await service._call_ai_parser(extracted)

    assert len(_FakeAIAsyncClient.requests) == 1
    req = _FakeAIAsyncClient.requests[0]
    assert req['params'] == {'api-version': '2024-10-21'}
    assert '/openai/deployments/gpt-4o/chat/completions' in req['url']
    assert req['headers']['Authorization'] == 'Bearer managed-identity-token'
    assert 'api-key' not in req['headers']
