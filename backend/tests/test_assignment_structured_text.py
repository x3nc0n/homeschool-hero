from io import BytesIO

import pytest
from starlette.datastructures import Headers, UploadFile

from backend.services.assignment_structured_text import (
    MAX_TABLE_COLUMNS,
    MAX_TABLE_ROWS,
    extract_assignment_structured_text,
)
from backend.services.bulk_assignment_import import (
    ASSIGNMENT_FILE_MIME_TYPES,
    BulkAssignmentImportError,
    BulkAssignmentImportService,
)
from backend.services.curriculum_ai_import import AIImportError

JSON_TEXT = '{\n  "schema_version": "1.0",\n  "assignments": [{"title": "Café", "student_refs": ["Ada"]}]\n}'
CSV_TEXT = 'Subject,Title,Due date\r\nMath,"Read, then explain\r\nin detail",2026-10-13\r\n'
TSV_TEXT = 'Subject\tTitle\tDue date\nMath\t"Read\nin detail"\t2026-10-13\n'


@pytest.mark.parametrize(
    ('content_type', 'text'),
    [('application/json', JSON_TEXT), ('text/csv', CSV_TEXT), ('text/tab-separated-values', TSV_TEXT)],
)
@pytest.mark.parametrize('bom', [False, True])
def test_preserves_complete_structured_source(content_type, text, bom):
    payload = text.encode('utf-8-sig' if bom else 'utf-8')
    assert extract_assignment_structured_text(payload, content_type=content_type, max_input_chars=50_000) == text


@pytest.mark.parametrize(
    ('content_type', 'payload', 'error'),
    [
        ('application/json', b'{"assignments": [}', 'Malformed JSON'),
        ('application/json', b'{"score": NaN}', 'Malformed JSON'),
        ('application/json', b'{"score": Infinity}', 'Malformed JSON'),
        ('application/json', b'[' * 65 + b'0' + b']' * 65, 'nesting limit'),
        ('text/csv', b'Title\n"unclosed', 'Malformed CSV/TSV'),
        ('text/tab-separated-values', b'Title\n"cell"x', 'Malformed CSV/TSV'),
        ('application/json', b'\xff\xfe{\x00}', 'Unsupported text encoding'),
        ('text/csv', b'Title\nCaf\xe9', 'Unsupported text encoding'),
        ('text/csv', b'Title\n\x00data', 'binary/control'),
        ('text/tab-separated-values', b'PK\x03\x04', 'binary/control'),
        ('application/json', b'\xef\xbb\xbf  \r\n', 'empty'),
        ('text/csv', b'\r\n\t', 'empty'),
        ('text/csv', (',' * MAX_TABLE_COLUMNS).encode(), 'table limit'),
        ('text/tab-separated-values', ('row\n' * (MAX_TABLE_ROWS + 1)).encode(), 'table limit'),
    ],
    ids=[
        'broken-json', 'json-nan', 'json-infinity', 'json-depth', 'csv-unclosed-quote', 'tsv-broken-quote',
        'json-utf16', 'csv-latin1', 'csv-null', 'tsv-binary', 'json-blank-bom', 'csv-blank',
        'csv-column-limit', 'tsv-row-limit',
    ],
)
def test_rejects_invalid_structured_source(content_type, payload, error):
    with pytest.raises(AIImportError, match=error):
        extract_assignment_structured_text(payload, content_type=content_type, max_input_chars=200_000)


def test_json_depth_ignores_braces_and_escaped_quotes_in_strings():
    text = '{"title": "' + '\\"' + '[' * 100 + '"}'
    assert extract_assignment_structured_text(text.encode(), content_type='application/json', max_input_chars=500) == text


@pytest.mark.parametrize(
    ('content_type', 'text'),
    [('application/json', JSON_TEXT), ('text/csv', CSV_TEXT), ('text/tab-separated-values', TSV_TEXT)],
)
def test_text_limit_rejects_instead_of_truncating(content_type, text):
    assert extract_assignment_structured_text(text.encode(), content_type=content_type, max_input_chars=len(text)) == text
    with pytest.raises(AIImportError, match='character limit'):
        extract_assignment_structured_text(text.encode(), content_type=content_type, max_input_chars=len(text) - 1)


def test_absolute_text_limit():
    with pytest.raises(AIImportError, match='character limit'):
        extract_assignment_structured_text(b'x' * 200_001, content_type='text/csv', max_input_chars=1_000_000)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('extension', 'text'),
    [('.json', JSON_TEXT), ('.csv', CSV_TEXT), ('.tsv', TSV_TEXT)],
)
async def test_upload_accepts_common_browser_mime_and_preserves_structure(extension, text):
    service = BulkAssignmentImportService()
    for mime in (*ASSIGNMENT_FILE_MIME_TYPES[extension], '', 'application/octet-stream'):
        upload = UploadFile(
            BytesIO(text.encode('utf-8-sig')), filename=f'Plan{extension.upper()}',
            headers=Headers({'content-type': mime.upper() + '; charset=utf-8'}),
        )
        extracted = await service.extract_upload(upload)
        assert extracted.content_type == ASSIGNMENT_FILE_MIME_TYPES[extension][0]
        assert extracted.extracted.text == text
        assert not extracted.extracted.warnings


@pytest.mark.parametrize('extension', ASSIGNMENT_FILE_MIME_TYPES)
def test_existing_formats_accept_generic_mime(extension):
    service = BulkAssignmentImportService()
    for mime in ('', 'application/octet-stream'):
        assert service._detect_content_type(filename=f'plan{extension}', content_type=mime) == ASSIGNMENT_FILE_MIME_TYPES[extension][0]


@pytest.mark.parametrize(
    ('filename', 'mime'),
    [
        ('plan.exe', 'application/json'),
        ('plan.xml', 'text/plain'),
        ('plan', 'text/csv'),
        ('plan.xls', 'application/vnd.ms-excel'),
        ('plan.json', 'application/pdf'),
        ('plan.csv', 'application/json'),
        ('plan.tsv', 'application/vnd.ms-excel'),
        ('plan.txt', 'application/json'),
        ('plan.xlsx', 'text/csv'),
    ],
)
def test_requires_supported_extension_and_matching_mime(filename, mime):
    with pytest.raises(BulkAssignmentImportError):
        BulkAssignmentImportService()._detect_content_type(filename=filename, content_type=mime)


@pytest.mark.asyncio
@pytest.mark.parametrize('extension', ['.json', '.csv', '.tsv'])
async def test_new_formats_keep_byte_limit(monkeypatch, extension):
    monkeypatch.setattr('backend.config.settings.bulk_assignment_import_max_bytes', 8)
    upload = UploadFile(BytesIO(b'0123456789'), filename=f'plan{extension}')
    with pytest.raises(BulkAssignmentImportError, match='upload limit'):
        await BulkAssignmentImportService().extract_upload(upload)
