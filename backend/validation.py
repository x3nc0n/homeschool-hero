from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, status

from backend.config import settings

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
SAFE_TEXT_RE = re.compile(r'^[^\x00-\x1f\x7f]+$')
SAFE_FILENAME_CHARS_RE = re.compile(r'[^A-Za-z0-9._ -]+')
BCRYPT_PASSWORD_MAX_BYTES = 72


def normalize_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f'{field_name} is required')
    if not SAFE_TEXT_RE.match(normalized):
        raise ValueError(f'{field_name} contains invalid characters')
    return normalized


def normalize_optional_text(value: str | None, *, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValueError(f'{field_name} must be {max_length} characters or fewer')
    if not SAFE_TEXT_RE.match(normalized):
        raise ValueError(f'{field_name} contains invalid characters')
    return normalized


def normalize_email_address(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError('Enter a valid email address')
    return email


def validate_bcrypt_password_length(password: str) -> str:
    if len(password.encode('utf-8')) > BCRYPT_PASSWORD_MAX_BYTES:
        raise ValueError(f'Password must be {BCRYPT_PASSWORD_MAX_BYTES} bytes or fewer')
    return password


def validate_password_policy(password: str) -> str:
    if len(password) < settings.password_min_length:
        raise ValueError(f'Password must be at least {settings.password_min_length} characters long')
    validate_bcrypt_password_length(password)
    if not any(character.isalpha() for character in password):
        raise ValueError('Password must include at least one letter')
    if not any(character.isdigit() for character in password):
        raise ValueError('Password must include at least one number')
    return password


def sanitize_filename(filename: str) -> str:
    candidate = Path(filename.replace('\\', '/')).name.strip()
    candidate = SAFE_FILENAME_CHARS_RE.sub('_', candidate).strip(' .')
    if not candidate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Filename is required')
    return candidate
