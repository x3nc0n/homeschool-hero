from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from typing import Any, Awaitable, Callable

from fastapi import Request

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CacheEntry:
    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    etag: str


class MemoryTTLCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _purge_expired(self) -> None:
        now = self._now()
        expired_keys = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired_keys:
            self._entries.pop(key, None)

    def _build_etag(self, value: Any) -> str:
        payload = json.dumps(value, default=str, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        return f'W/"{digest}"'

    async def get_or_set(
        self,
        key: str,
        *,
        ttl: timedelta,
        factory: Callable[[], Awaitable[Any]],
    ) -> CacheEntry:
        self._purge_expired()
        now = self._now()
        entry = self._entries.get(key)
        if entry is not None and entry.expires_at > now:
            logger.info('cache_hit key=%s', key)
            return entry

        logger.info('cache_miss key=%s', key)
        value = await factory()
        created_at = self._now()
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=created_at,
            expires_at=created_at + ttl,
            etag=self._build_etag(value),
        )
        self._entries[key] = entry
        return entry

    def invalidate_prefix(self, prefix: str) -> int:
        keys = [key for key in self._entries if key.startswith(prefix)]
        for key in keys:
            self._entries.pop(key, None)
        logger.info('cache_invalidate prefix=%s count=%s', prefix, len(keys))
        return len(keys)

    def clear(self) -> None:
        count = len(self._entries)
        self._entries.clear()
        logger.info('cache_clear count=%s', count)


_cache = MemoryTTLCache()


def get_cache() -> MemoryTTLCache:
    return _cache


def cache_headers(entry: CacheEntry, *, max_age_seconds: int) -> dict[str, str]:
    return {
        'ETag': entry.etag,
        'Last-Modified': format_datetime(entry.created_at, usegmt=True),
        'Cache-Control': f'private, max-age={max_age_seconds}',
    }


def is_not_modified(request: Request, entry: CacheEntry) -> bool:
    if_none_match = request.headers.get('if-none-match')
    if if_none_match and if_none_match.strip() == entry.etag:
        return True

    if_modified_since = request.headers.get('if-modified-since')
    if not if_modified_since:
        return False
    try:
        parsed = parsedate_to_datetime(if_modified_since)
    except (TypeError, ValueError, IndexError):
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed >= entry.created_at


def invalidate_gradebook_cache(*, family_id: int, student_id: int | None = None) -> int:
    prefix = f'gradebook:{family_id}:'
    if student_id is not None:
        prefix = f'{prefix}{student_id}:'
    return get_cache().invalidate_prefix(prefix)


def invalidate_compliance_cache(*, family_id: int, student_id: int | None = None) -> int:
    prefix = f'compliance:{family_id}:'
    if student_id is not None:
        prefix = f'{prefix}{student_id}:'
    return get_cache().invalidate_prefix(prefix)


def invalidate_pacing_cache(*, family_id: int, student_id: int | None = None) -> int:
    prefix = f'pacing:{family_id}:'
    if student_id is not None:
        prefix = f'{prefix}{student_id}:'
    return get_cache().invalidate_prefix(prefix)
