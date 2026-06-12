from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

API_VERSION = '0.1.0'
API_SUMMARY = 'Family-scoped API for homeschool planning, assessment, reporting, and administration.'
API_DESCRIPTION = (
    'Homeschool Hero provides authenticated family workflows for roster management, assignments, '
    'grading, attendance, compliance, notifications, exports, and academic reports. The API supports '
    'either a signed session cookie or an Authorization bearer token for authentication, requires an '
    '`X-CSRF-Token` header on mutating cookie-authenticated requests, and returns a consistent JSON error '
    'envelope for validation and authorization failures.'
)

TAG_METADATA = [
    {
        'name': 'auth',
        'description': 'Bootstrap, local sign-in, optional OIDC/SAML entry points, invitations, and session lifecycle.',
    },
    {
        'name': 'students',
        'description': 'Family roster, subjects, curriculum, calendar, schedule, lesson planning, portfolio, and import flows.',
    },
    {
        'name': 'assignments',
        'description': 'Assignments, submissions, quizzes, grading orchestration, and human review workflows.',
    },
    {
        'name': 'grades',
        'description': 'Grade records, gradebook settings, calculations, summaries, and trends.',
    },
    {
        'name': 'attendance',
        'description': 'Daily attendance, instructional hours, excuses, approvals, and attendance summaries.',
    },
    {
        'name': 'reports',
        'description': 'Report cards, transcripts, compliance reports, compliance status, and export artifacts.',
    },
    {
        'name': 'admin',
        'description': 'Dashboard, notifications, search, audit, metrics, health, and platform management surfaces.',
    },
]

TAG_GROUPS = [
    {'name': 'Core workflows', 'tags': ['auth', 'students', 'assignments', 'grades', 'attendance', 'reports']},
    {'name': 'Operations', 'tags': ['admin']},
]

PUBLIC_OPERATION_PREFIXES = (
    '/api/auth/bootstrap',
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/oidc/login',
    '/api/auth/oidc/callback',
    '/api/auth/saml/login',
    '/api/auth/saml/metadata',
    '/api/auth/saml/acs',
    '/api/health',
    '/api/capabilities',
    '/api/openapi.json',
    '/api/docs',
    '/api/redoc',
)

STANDARD_ERROR_RESPONSES = {
    '400': {'description': 'Bad request'},
    '401': {'description': 'Authentication required'},
    '403': {'description': 'Forbidden'},
    '404': {'description': 'Resource not found'},
    '422': {'description': 'Request validation failed'},
}

ERROR_EXAMPLES = {
    '400': {
        'detail': 'Bad request',
        'error': {'code': 'bad_request', 'message': 'Bad request'},
    },
    '401': {
        'detail': 'Authentication required',
        'error': {'code': 'auth_required', 'message': 'Authentication required'},
    },
    '403': {
        'detail': 'Forbidden',
        'error': {'code': 'forbidden', 'message': 'You do not have permission to perform this action.'},
    },
    '404': {
        'detail': 'Resource not found',
        'error': {'code': 'not_found', 'message': 'The requested resource could not be found.'},
    },
    '422': {
        'detail': 'Invalid request.',
        'error': {
            'code': 'validation_error',
            'message': 'Invalid request.',
            'details': [{'loc': ['body', 'field'], 'msg': 'Field is required', 'type': 'missing'}],
        },
    },
}

AUTH_SUMMARIES: dict[tuple[str, str], str] = {
    ('GET', '/api/auth/bootstrap'): 'Check bootstrap status',
    ('POST', '/api/auth/register'): 'Create owner account',
    ('POST', '/api/auth/login'): 'Sign in locally',
    ('POST', '/api/auth/logout'): 'Sign out current session',
    ('GET', '/api/auth/me'): 'Get current session',
    ('GET', '/api/auth/oidc/login'): 'Start OIDC sign-in',
    ('GET', '/api/auth/oidc/callback'): 'Finish OIDC sign-in',
    ('GET', '/api/auth/saml/login'): 'Start SAML sign-in',
    ('GET', '/api/auth/saml/metadata'): 'Get SAML metadata',
    ('POST', '/api/auth/saml/acs'): 'Consume SAML assertion',
}


def configure_openapi(
    app: FastAPI,
    *,
    api_prefix: str,
    session_cookie_name: str,
    csrf_cookie_name: str,
    expose_ui: bool = False,
) -> None:
    openapi_url = f'{api_prefix}/openapi.json'
    docs_url = f'{api_prefix}/docs'
    redoc_url = f'{api_prefix}/redoc'

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
        )
        schema['info']['contact'] = {
            'name': 'Homeschool Hero maintainers',
            'url': 'https://github.com/x3nc0n/homeschool-hero',
            'email': 'support@homeschool-hero.local',
        }
        schema['info']['license'] = {
            'name': 'See repository',
            'url': 'https://github.com/x3nc0n/homeschool-hero',
        }
        schema['tags'] = TAG_METADATA
        schema['x-tagGroups'] = TAG_GROUPS

        components = schema.setdefault('components', {})
        component_schemas = components.setdefault('schemas', {})
        component_schemas.setdefault(
            'ErrorDetail',
            {
                'title': 'ErrorDetail',
                'type': 'object',
                'additionalProperties': True,
                'description': 'Optional machine-readable validation or processing details.',
                'example': {'loc': ['body', 'field'], 'msg': 'Field is required', 'type': 'missing'},
            },
        )
        component_schemas.setdefault(
            'ErrorEnvelope',
            {
                'title': 'ErrorEnvelope',
                'type': 'object',
                'required': ['code', 'message'],
                'properties': {
                    'code': {'type': 'string', 'example': 'validation_error'},
                    'message': {'type': 'string', 'example': 'Invalid request.'},
                    'details': {
                        'oneOf': [
                            {'$ref': '#/components/schemas/ErrorDetail'},
                            {'type': 'array', 'items': {'$ref': '#/components/schemas/ErrorDetail'}},
                        ]
                    },
                },
                'example': {
                    'code': 'validation_error',
                    'message': 'Invalid request.',
                    'details': [{'loc': ['body', 'field'], 'msg': 'Field is required', 'type': 'missing'}],
                },
            },
        )
        component_schemas.setdefault(
            'ErrorResponse',
            {
                'title': 'ErrorResponse',
                'type': 'object',
                'required': ['detail', 'error'],
                'properties': {
                    'detail': {'type': 'string', 'example': 'Invalid request.'},
                    'error': {'$ref': '#/components/schemas/ErrorEnvelope'},
                },
                'example': ERROR_EXAMPLES['422'],
            },
        )
        components.setdefault('securitySchemes', {}).update(
            {
                'SessionCookieAuth': {
                    'type': 'apiKey',
                    'in': 'cookie',
                    'name': session_cookie_name,
                    'description': 'Signed session cookie issued after local, OIDC, or SAML sign-in.',
                },
                'CsrfHeaderAuth': {
                    'type': 'apiKey',
                    'in': 'header',
                    'name': 'X-CSRF-Token',
                    'description': (
                        f'CSRF token header required for POST, PUT, PATCH, and DELETE requests when using '
                        f'the `{csrf_cookie_name}` session cookie path.'
                    ),
                },
                'BearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT',
                    'description': 'Stateless JWT bearer token validated with the configured secret or JWKS endpoint.',
                },
            }
        )

        for name, definition in component_schemas.items():
            if name.startswith('Error') or 'example' in definition:
                continue
            example = _generate_example(definition, component_schemas, field_name=name)
            if example is not None:
                definition['example'] = example

        for path, path_item in schema.get('paths', {}).items():
            for method, operation in path_item.items():
                if method.upper() not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}:
                    continue
                _decorate_operation(
                    path=path,
                    method=method.upper(),
                    operation=operation,
                    component_schemas=component_schemas,
                )

        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    if not expose_ui:
        return

    @app.get(docs_url, include_in_schema=False)
    async def swagger_ui() -> HTMLResponse:
        return HTMLResponse(
            _build_swagger_html(
                title=f'{app.title} - Swagger UI',
                openapi_url=openapi_url,
                session_cookie_name=session_cookie_name,
                csrf_cookie_name=csrf_cookie_name,
            )
        )

    @app.get(redoc_url, include_in_schema=False)
    async def redoc_ui() -> HTMLResponse:
        return get_redoc_html(openapi_url=openapi_url, title=f'{app.title} - ReDoc')


def _decorate_operation(
    *,
    path: str,
    method: str,
    operation: dict[str, Any],
    component_schemas: dict[str, dict[str, Any]],
) -> None:
    tag = _tag_for_path(path)
    operation['tags'] = [tag]
    operation.setdefault('summary', _summary_for_operation(path, method))
    operation.setdefault('description', _description_for_operation(path, method, tag))
    if _is_public_operation(path):
        operation.pop('security', None)
    else:
        if method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            operation['security'] = [{'SessionCookieAuth': [], 'CsrfHeaderAuth': []}, {'BearerAuth': []}]
        else:
            operation['security'] = [{'SessionCookieAuth': []}, {'BearerAuth': []}]

    request_body = operation.get('requestBody', {})
    for media in request_body.get('content', {}).values():
        if 'example' not in media and 'schema' in media:
            example = _generate_example(media['schema'], component_schemas)
            if example is not None:
                media['example'] = example

    for response in operation.get('responses', {}).values():
        for media in response.get('content', {}).values():
            if 'example' in media or 'schema' not in media:
                continue
            example = _generate_example(media['schema'], component_schemas)
            if example is not None:
                media['example'] = example

    responses = operation.setdefault('responses', {})
    for status_code, response in STANDARD_ERROR_RESPONSES.items():
        entry = responses.setdefault(status_code, {'description': response['description']})
        entry.setdefault('description', response['description'])
        content = entry.setdefault('content', {})
        content.setdefault(
            'application/json',
            {
                'schema': {'$ref': '#/components/schemas/ErrorResponse'},
                'example': ERROR_EXAMPLES[status_code],
            },
        )


def _tag_for_path(path: str) -> str:
    tag_map = (
        ('/api/auth', 'auth'),
        ('/api/invitations', 'auth'),
        ('/api/students', 'students'),
        ('/api/subjects', 'students'),
        ('/api/curriculum', 'students'),
        ('/api/calendar', 'students'),
        ('/api/schedule', 'students'),
        ('/api/lesson-plans', 'students'),
        ('/api/portfolio', 'students'),
        ('/api/imports', 'students'),
        ('/api/assignments', 'assignments'),
        ('/api/submissions', 'assignments'),
        ('/api/quizzes', 'assignments'),
        ('/api/grading', 'assignments'),
        ('/api/reviews', 'assignments'),
        ('/api/grades', 'grades'),
        ('/api/gradebook', 'grades'),
        ('/api/attendance', 'attendance'),
        ('/api/report-cards', 'reports'),
        ('/api/transcripts', 'reports'),
        ('/api/compliance-reports', 'reports'),
        ('/api/compliance', 'reports'),
        ('/api/exports', 'reports'),
    )
    for prefix, tag in tag_map:
        if path.startswith(prefix):
            return tag
    return 'admin'


def _is_public_operation(path: str) -> bool:
    if path.startswith('/api/portfolio/public/'):
        return True
    if path.startswith('/api/invitations/') and path.endswith('/accept'):
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_OPERATION_PREFIXES)


def _summary_for_operation(path: str, method: str) -> str:
    if (method, path) in AUTH_SUMMARIES:
        return AUTH_SUMMARIES[(method, path)]

    segments = [segment for segment in path.removeprefix('/api/').split('/') if segment]
    resource_parts = [segment for segment in segments if not segment.startswith('{')]
    resource = resource_parts[-1] if resource_parts else 'resource'

    if resource == 'status':
        resource = resource_parts[-2] if len(resource_parts) >= 2 else resource
        return f'Get {_singularize(resource)} status'
    if resource == 'download':
        resource = resource_parts[-2] if len(resource_parts) >= 2 else resource
        return f'Download {_singularize(resource)} file'
    if resource == 'generate':
        resource = resource_parts[-2] if len(resource_parts) >= 2 else resource
        return f'Generate {_labelize(resource)}'
    if resource == 'read-all':
        return 'Mark all notifications as read'

    has_path_param = any(segment.startswith('{') for segment in segments)
    if method == 'GET':
        return f'Get {_singularize(resource)}' if has_path_param else f'List {_labelize(resource)}'
    if method == 'POST':
        return f'Create {_singularize(resource)}'
    if method in {'PUT', 'PATCH'}:
        return f'Update {_singularize(resource)}'
    if method == 'DELETE':
        return f'Delete {_singularize(resource)}'
    return f'{method.title()} {_labelize(resource)}'


def _description_for_operation(path: str, method: str, tag: str) -> str:
    resource = _labelize(path.removeprefix('/api/').split('/')[-1].strip('{}') or tag)
    if _is_public_operation(path):
        auth_line = (
            'This operation is public so bootstrap, invitation acceptance, health checks, and external identity '
            'provider callbacks can complete before a user session exists.'
        )
    elif method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        auth_line = (
            'This operation requires either a valid Homeschool Hero session cookie plus the current '
            '`X-CSRF-Token` header, or a valid JWT bearer token.'
        )
    else:
        auth_line = 'This operation requires either a valid Homeschool Hero session cookie or a valid JWT bearer token.'

    workflow_notes = {
        'auth': 'Use these endpoints to bootstrap the first owner account, establish sessions, and hand off to OIDC or SAML sign-in when external identity is enabled.',
        'students': 'Responses are family-scoped so roster, planning, and curriculum data stays isolated per household.',
        'assignments': 'Use these endpoints to move work from planning through submission, grading automation, and manual review.',
        'grades': 'Grade and gradebook endpoints expose scoring records, weighting, summaries, and recalculation results for the current family.',
        'attendance': 'Attendance endpoints support day-level tracking, instructional hours, excuses, approvals, and rollup reporting.',
        'reports': 'Reporting endpoints generate official academic artifacts, compliance outputs, and downloadable exports for the active family.',
        'admin': 'Administrative endpoints expose operational health, notifications, audit history, and other account-level support surfaces.',
    }
    return f'{workflow_notes[tag]} {auth_line} The example payloads show a representative `{resource}` request and response shape.'


def _labelize(value: str) -> str:
    return value.replace('-', ' ').replace('_', ' ')


def _singularize(value: str) -> str:
    label = _labelize(value)
    if label.endswith('ies'):
        return f'{label[:-3]}y'
    if label.endswith('sses'):
        return label[:-2]
    if label.endswith('s') and not label.endswith('ss'):
        return label[:-1]
    return label


def _generate_example(
    schema: dict[str, Any] | None,
    component_schemas: dict[str, dict[str, Any]],
    *,
    field_name: str | None = None,
    seen: set[str] | None = None,
) -> Any:
    if not schema:
        return None

    seen = seen or set()

    if 'example' in schema:
        return schema['example']
    if 'examples' in schema and schema['examples']:
        first_key = next(iter(schema['examples']))
        return schema['examples'][first_key]
    if '$ref' in schema:
        ref_name = schema['$ref'].split('/')[-1]
        if ref_name in seen:
            return None
        return _generate_example(component_schemas.get(ref_name), component_schemas, field_name=ref_name, seen=seen | {ref_name})
    if 'allOf' in schema:
        merged: dict[str, Any] = {}
        for part in schema['allOf']:
            part_example = _generate_example(part, component_schemas, field_name=field_name, seen=seen)
            if isinstance(part_example, dict):
                merged.update(part_example)
        return merged or None
    if 'oneOf' in schema:
        return _generate_example(schema['oneOf'][0], component_schemas, field_name=field_name, seen=seen)
    if 'anyOf' in schema:
        return _generate_example(schema['anyOf'][0], component_schemas, field_name=field_name, seen=seen)
    if 'enum' in schema and schema['enum']:
        return schema['enum'][0]
    if 'const' in schema:
        return schema['const']
    if 'default' in schema:
        return schema['default']

    schema_type = schema.get('type')
    if not schema_type and 'properties' in schema:
        schema_type = 'object'

    if schema_type == 'object':
        result: dict[str, Any] = {}
        properties = schema.get('properties', {})
        required = set(schema.get('required', []))
        for name, property_schema in properties.items():
            if property_schema.get('writeOnly') and field_name and field_name.endswith('Response'):
                continue
            if property_schema.get('readOnly') and field_name and field_name.endswith('Request'):
                continue
            if name not in required and len(result) >= max(len(required), 4):
                continue
            value = _generate_example(property_schema, component_schemas, field_name=name, seen=seen)
            if value is not None:
                result[name] = value
        if result:
            return result
        if schema.get('additionalProperties'):
            return {'key': 'value'}
        return None

    if schema_type == 'array':
        item_example = _generate_example(schema.get('items'), component_schemas, field_name=field_name, seen=seen)
        return [] if item_example is None else [item_example]

    if schema_type == 'integer':
        return 1 if (field_name or '').endswith('id') else 100
    if schema_type == 'number':
        return 98.5 if field_name and 'score' in field_name else 0.8
    if schema_type == 'boolean':
        return True
    if schema_type == 'string':
        return _string_example(field_name=field_name, schema=schema)
    return None


def _string_example(*, field_name: str | None, schema: dict[str, Any]) -> str:
    field = (field_name or '').lower()
    string_format = schema.get('format')
    if string_format == 'date':
        return '2026-05-09'
    if string_format == 'date-time':
        return '2026-05-09T01:20:00Z'
    if string_format == 'email' or 'email' in field:
        return 'parent@example.com'
    if string_format in {'uri', 'url'} or 'url' in field or 'link' in field:
        return 'https://example.com/resource'
    if string_format == 'uuid':
        return '9f6f3d22-1f8a-4c7b-8e14-d5822f9434b1'
    if string_format == 'binary':
        return 'example-upload.bin'
    if 'timezone' in field:
        return 'UTC'
    if 'password' in field:
        return 'CorrectHorseBatteryStaple123!'
    if field.endswith('name') or field == 'title':
        return 'Example Name'
    if 'description' in field or field == 'message':
        return 'Example description'
    if 'status' in field:
        return 'active'
    if 'role' in field:
        return 'parent'
    if 'state' in field and field.endswith('code'):
        return 'TX'
    if 'provider' in field:
        return 'local'
    if 'path' in field:
        return '/data/uploads/example.pdf'
    if 'mime' in field:
        return 'application/pdf'
    if field.endswith('token'):
        return 'token-value'
    return 'example'


def _build_swagger_html(*, title: str, openapi_url: str, session_cookie_name: str, csrf_cookie_name: str) -> str:
    config = {
        'url': openapi_url,
        'dom_id': '#swagger-ui',
        'deepLinking': True,
        'displayRequestDuration': True,
        'persistAuthorization': True,
        'layout': 'BaseLayout',
        'defaultModelsExpandDepth': 1,
        'defaultModelExpandDepth': 1,
    }
    config_json = json.dumps(config)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    const cookieValue = (name) => {{
      const escaped = name.replace(/([.*+?^=!:${{}}()|[\\]\\/\\\\])/g, "\\\\$1");
      const match = document.cookie.match(new RegExp('(?:^|; )' + escaped + '=([^;]*)'));
      return match ? decodeURIComponent(match[1]) : '';
    }};
    const config = {config_json};
    config.requestInterceptor = (request) => {{
      request.credentials = 'same-origin';
      const csrf = cookieValue('{csrf_cookie_name}');
      const method = (request.method || 'GET').toUpperCase();
      if (csrf && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {{
        request.headers['X-CSRF-Token'] = csrf;
      }}
      return request;
    }};
    config.onComplete = () => {{
      const sessionCookie = cookieValue('{session_cookie_name}');
      const bannerId = 'swagger-auth-banner';
      if (!document.getElementById(bannerId)) {{
        const banner = document.createElement('div');
        banner.id = bannerId;
        banner.style.cssText = 'margin:16px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:12px 16px;font-family:sans-serif;color:#1e3a8a;';
        banner.innerHTML = sessionCookie
          ? 'Authenticated session cookie detected. Swagger UI will send your session cookie and current CSRF token on same-origin requests.'
          : 'Sign in from the app first if you want to call protected endpoints from Swagger UI.';
        document.body.insertBefore(banner, document.getElementById('swagger-ui'));
      }}
    }};
    window.ui = SwaggerUIBundle(config);
  </script>
</body>
</html>"""
