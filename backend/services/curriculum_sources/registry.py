from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache
from typing import Iterable

from backend.services.curriculum_sources.base import CurriculumSource


def _iter_source_classes() -> Iterable[type[CurriculumSource]]:
    import backend.services.curriculum_sources as sources_package

    for module_info in pkgutil.iter_modules(sources_package.__path__):
        if module_info.name in {'base', 'registry'}:
            continue
        importlib.import_module(f'{sources_package.__name__}.{module_info.name}')

    seen: set[type[CurriculumSource]] = set()
    pending = list(CurriculumSource.__subclasses__())
    while pending:
        candidate = pending.pop()
        if candidate in seen:
            continue
        seen.add(candidate)
        pending.extend(candidate.__subclasses__())
        if candidate.source_id:
            yield candidate


@lru_cache(maxsize=1)
def get_curriculum_source_registry() -> dict[str, CurriculumSource]:
    registry: dict[str, CurriculumSource] = {}
    for source_class in _iter_source_classes():
        instance = source_class()
        registry[instance.source_id] = instance
    return dict(sorted(registry.items()))


def list_curriculum_sources() -> list[CurriculumSource]:
    return list(get_curriculum_source_registry().values())


def get_curriculum_source(source_id: str) -> CurriculumSource | None:
    return get_curriculum_source_registry().get(source_id)
