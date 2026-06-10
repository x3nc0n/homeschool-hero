from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path

import fitz
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.config import settings
from backend.validation import sanitize_filename

UPLOAD_EXTENSION_MIME_MAP: dict[str, set[str]] = {
    '.pdf': {'application/pdf'},
    '.jpg': {'image/jpeg'},
    '.jpeg': {'image/jpeg'},
    '.png': {'image/png'},
    '.heic': {'image/heic', 'image/heif'},
    '.heif': {'image/heic', 'image/heif'},
    '.tif': {'image/tiff'},
    '.tiff': {'image/tiff'},
    '.webp': {'image/webp'},
}


@dataclass(slots=True)
class StoredUpload:
    original_filename: str
    file_name: str
    content_type: str
    file_size_bytes: int
    relative_path: str
    absolute_path: str
    image_width: int | None = None
    image_height: int | None = None
    page_count: int | None = None


def _upload_root_parts(upload_root: str) -> tuple[str, str]:
    upload_root_real = os.path.realpath(upload_root)
    upload_root_prefix = upload_root_real + os.sep
    return upload_root_real, upload_root_prefix


def normalize_upload_type(filename: str, content_type: str, allowed_mime_types: set[str]) -> tuple[str, str]:
    sanitized_name = sanitize_filename(filename)
    suffix = Path(sanitized_name).suffix.lower()
    expected_types = UPLOAD_EXTENSION_MIME_MAP.get(suffix)
    normalized_content_type = (content_type or '').strip().lower()
    if not expected_types or normalized_content_type not in allowed_mime_types:
        raise ValueError('Unsupported file type')
    if normalized_content_type not in expected_types:
        raise ValueError('Unsupported file type')
    return sanitized_name, normalized_content_type


def build_submission_relative_path(
    *,
    family_id: int,
    student_id: int,
    assignment_id: int,
    submission_id: int,
    file_name: str,
) -> Path:
    return Path(str(family_id), str(student_id), str(assignment_id), str(submission_id), file_name)


def _extract_image_metadata(contents: bytes) -> tuple[int | None, int | None]:
    try:
        with Image.open(BytesIO(contents)) as image:
            normalized = ImageOps.exif_transpose(image)
            width, height = normalized.size
            return int(width), int(height)
    except (UnidentifiedImageError, OSError, SyntaxError):
        return None, None


def _extract_pdf_page_count(contents: bytes) -> int | None:
    try:
        with fitz.open(stream=contents, filetype='pdf') as document:
            return int(document.page_count)
    except Exception:
        return None


def extract_file_metadata(content_type: str, contents: bytes) -> tuple[int | None, int | None, int | None]:
    if content_type == 'application/pdf':
        return None, None, _extract_pdf_page_count(contents)
    if content_type.startswith('image/'):
        width, height = _extract_image_metadata(contents)
        return width, height, None
    return None, None, None


def _resolve_safe_upload_destination(upload_root: str, relative_path: Path) -> tuple[Path, Path]:
    # Use os.path.realpath() to fully resolve symlinks and normalise the root
    upload_root_real, upload_root_prefix = _upload_root_parts(upload_root)

    normalized_relative_path = os.path.normpath(os.fspath(relative_path))
    candidate = Path(normalized_relative_path)
    if normalized_relative_path in {'', '.', os.curdir} or os.path.isabs(normalized_relative_path) or candidate.anchor:
        raise ValueError('Invalid upload path')
    if any(part == '..' for part in candidate.parts):
        raise ValueError('Invalid upload path')

    # Resolve the full destination path, then verify it is strictly inside the upload root.
    # startswith(prefix) with a trailing separator prevents prefix-collision attacks
    # (e.g. /uploads-evil would not match /uploads/).
    destination_real = os.path.realpath(os.path.join(upload_root_real, normalized_relative_path))
    if not (destination_real == upload_root_real or destination_real.startswith(upload_root_prefix)):
        raise ValueError('Path traversal detected')
    return candidate, Path(destination_real)


def resolve_stored_upload_path(upload_root: str, stored_path: str | Path) -> tuple[Path, Path]:
    raw_path = os.fspath(stored_path).strip()
    if not raw_path:
        raise ValueError('Invalid upload path')

    upload_root_real, upload_root_prefix = _upload_root_parts(upload_root)
    if os.path.isabs(raw_path):
        absolute_real = os.path.realpath(raw_path)
        if not (absolute_real == upload_root_real or absolute_real.startswith(upload_root_prefix)):
            raise ValueError('Path traversal detected')
        relative_value = os.path.relpath(absolute_real, upload_root_real)
        relative_path = Path(relative_value)
        if relative_value in {'', '.', os.curdir} or any(part == '..' for part in relative_path.parts):
            raise ValueError('Invalid upload path')
        return relative_path, Path(absolute_real)

    return _resolve_safe_upload_destination(upload_root, Path(raw_path))


def build_authenticated_file_url(stored_path: str | Path) -> str:
    relative_path, _ = resolve_stored_upload_path(settings.upload_dir, stored_path)
    api_prefix = settings.api_prefix.rstrip('/')
    return f'{api_prefix}/files/{relative_path.as_posix()}'


def store_submission_file(
    *,
    upload_root: str,
    family_id: int,
    student_id: int,
    assignment_id: int,
    submission_id: int,
    original_filename: str,
    content_type: str,
    contents: bytes,
) -> StoredUpload:
    sanitized_name = sanitize_filename(original_filename)
    relative_path = build_submission_relative_path(
        family_id=family_id,
        student_id=student_id,
        assignment_id=assignment_id,
        submission_id=submission_id,
        file_name=sanitized_name,
    )
    safe_relative_path, destination = _resolve_safe_upload_destination(upload_root, relative_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)
    image_width, image_height, page_count = extract_file_metadata(content_type, contents)
    return StoredUpload(
        original_filename=original_filename,
        file_name=sanitized_name,
        content_type=content_type,
        file_size_bytes=len(contents),
        relative_path=str(safe_relative_path),
        absolute_path=str(destination),
        image_width=image_width,
        image_height=image_height,
        page_count=page_count,
    )
