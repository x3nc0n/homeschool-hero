from fastapi.testclient import TestClient

from backend.config import settings


def test_openapi_schema_exposes_metadata_examples_and_security(backend_module, monkeypatch) -> None:
    monkeypatch.setattr(settings, 'public_api_docs', True)
    app = backend_module.create_app()
    with TestClient(app) as client:
        response = client.get('/api/openapi.json')

    assert response.status_code == 200
    payload = response.json()
    assert payload['openapi'].startswith('3.')
    assert payload['info']['version'] == '0.1.0'
    assert payload['info']['contact']['url'].endswith('/homeschool-hero')
    assert payload['info']['license']['name'] == 'See repository'
    assert {'SessionCookieAuth', 'CsrfHeaderAuth', 'BearerAuth'} <= set(payload['components']['securitySchemes'])
    assert payload['components']['schemas']['ErrorResponse']['example']['error']['code'] == 'validation_error'
    assert payload['components']['schemas']['LoginRequest']['example']['email'] == 'parent@example.com'
    assert payload['paths']['/api/students']['get']['tags'] == ['students']
    assert payload['paths']['/api/students']['get']['responses']['401']['content']['application/json']['schema']['$ref'].endswith(
        '/ErrorResponse'
    )
    assert payload['paths']['/api/students']['post']['security'] == [
        {'SessionCookieAuth': [], 'CsrfHeaderAuth': []},
        {'BearerAuth': []},
    ]
    assert payload['paths']['/api/auth/login']['post'].get('security') is None


def test_docs_endpoints_are_disabled_by_default(app) -> None:
    with TestClient(app) as client:
        swagger = client.get('/api/docs')
        redoc = client.get('/api/redoc')

    assert swagger.status_code == 404
    assert redoc.status_code == 404


def test_docs_endpoints_can_be_enabled_for_internal_use(backend_module, monkeypatch) -> None:
    monkeypatch.setattr(settings, 'public_api_docs', True)
    app = backend_module.create_app()
    with TestClient(app) as client:
        swagger = client.get('/api/docs')
        redoc = client.get('/api/redoc')

    assert swagger.status_code == 200
    assert '/api/openapi.json' in swagger.text
    assert 'X-CSRF-Token' in swagger.text
    assert redoc.status_code == 200
    assert '/api/openapi.json' in redoc.text
