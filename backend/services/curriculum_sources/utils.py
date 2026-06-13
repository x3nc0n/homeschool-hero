from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from typing import Any, Iterable, TypeVar

T = TypeVar('T')


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._parts.append(data.strip())

    def get_text(self) -> str:
        return ' '.join(self._parts)


def strip_html(value: str | None) -> str | None:
    if value is None:
        return None
    parser = _HTMLTextExtractor()
    parser.feed(value)
    text = ' '.join(parser.get_text().split())
    return unescape(text) if text else None


def unique_strings(values: Iterable[str | None]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        candidate = ' '.join(value.split())
        if not candidate:
            continue
        lowered = candidate.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(candidate)
    return normalized


def paginate_items(items: list[T], *, page: int, page_size: int) -> list[T]:
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return items[start:end]


def coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
