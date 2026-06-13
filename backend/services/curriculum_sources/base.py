from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from backend.schemas.curriculum import CurriculumImportDocument


class CurriculumSourceError(RuntimeError):
    """Raised when a curriculum source request fails."""


class CurriculumSourceUnavailable(CurriculumSourceError):
    """Raised when a curriculum source is disabled or misconfigured."""


@dataclass(slots=True)
class SourceAvailability:
    enabled: bool
    detail: str | None = None
    configuration_required: bool = False


@dataclass(slots=True)
class CurriculumSourceItem:
    id: str
    title: str
    description: str | None = None
    subjects: list[str] = field(default_factory=list)
    grade_levels: list[str] = field(default_factory=list)
    url: str | None = None
    image_url: str | None = None
    license_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CurriculumSourceSearchPage:
    source: str
    query: str
    page: int
    page_size: int
    total_count: int
    items: list[CurriculumSourceItem]

    @property
    def has_more(self) -> bool:
        return self.page * self.page_size < self.total_count


class CurriculumSource(ABC):
    source_id = ''
    display_name = ''
    description = ''

    def availability(self) -> SourceAvailability:
        return SourceAvailability(enabled=True)

    def require_availability(self) -> None:
        availability = self.availability()
        if availability.enabled:
            return
        message = availability.detail or f'{self.display_name} is unavailable'
        raise CurriculumSourceUnavailable(message)

    @abstractmethod
    async def search(self, query: str, *, page: int = 1, page_size: int = 10) -> CurriculumSourceSearchPage:
        raise NotImplementedError

    @abstractmethod
    async def fetch(self, item_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def convert_to_standard_format(self, raw_data: dict[str, Any]) -> CurriculumImportDocument:
        raise NotImplementedError
