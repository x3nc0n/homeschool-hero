from __future__ import annotations

import csv
import json
from io import StringIO

from backend.services.curriculum_ai_import import AIImportError

STRUCTURED_TEXT_TYPES = {'application/json', 'text/csv', 'text/tab-separated-values'}
MAX_TEXT_CHARS = 200_000
MAX_JSON_DEPTH = 64
MAX_TABLE_ROWS = 10_000
MAX_TABLE_COLUMNS = 512


def _reject_json_constant(value: str) -> None:
    raise ValueError(f'Nonstandard JSON constant: {value}')


def extract_assignment_structured_text(payload: bytes, *, content_type: str, max_input_chars: int) -> str:
    try:
        text = payload.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise AIImportError('Unsupported text encoding. Save JSON, CSV, or TSV as UTF-8 (BOM is supported).') from exc
    if len(text) > min(max_input_chars, MAX_TEXT_CHARS):
        raise AIImportError('Structured text exceeds the AI input character limit. Split the file into smaller files.')
    if not text.strip():
        raise AIImportError('The structured text document is empty')
    if any(ord(char) < 32 and char not in '\t\r\n' for char in text) or '\x7f' in text:
        raise AIImportError('The document contains binary/control characters. Upload readable UTF-8 text.')

    if content_type == 'application/json':
        # Bound nesting before allocating the decoded object; braces inside strings are data.
        depth = 0
        in_string = escaped = False
        for char in text:
            if in_string:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char in '[{':
                depth += 1
                if depth > MAX_JSON_DEPTH:
                    raise AIImportError('JSON exceeds the nesting limit (64 levels). Simplify the document.')
            elif char in ']}':
                depth -= 1
        try:
            json.loads(text, parse_constant=_reject_json_constant)
        except (ValueError, RecursionError) as exc:
            raise AIImportError('Malformed JSON. Upload a valid JSON document.') from exc
    else:
        delimiter = '\t' if content_type == 'text/tab-separated-values' else ','
        try:
            reader = csv.reader(StringIO(text, newline=''), delimiter=delimiter, strict=True)
            for row_number, row in enumerate(reader, start=1):
                if row_number > MAX_TABLE_ROWS or len(row) > MAX_TABLE_COLUMNS:
                    raise AIImportError('CSV/TSV exceeds the table limit (10,000 rows or 512 columns). Split the file.')
        except csv.Error as exc:
            raise AIImportError('Malformed CSV/TSV. Check delimiters and quoted cells, including multiline cells.') from exc
    # Send the original source, not reserialized values, so schema, delimiters and spacing survive.
    return text
