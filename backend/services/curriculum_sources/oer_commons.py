from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings
from backend.schemas.curriculum import (
    CurriculumImportDocument,
    CurriculumImportLessonPayload,
    CurriculumImportMetadata,
    CurriculumImportResource,
    CurriculumImportSubjectPayload,
    CurriculumImportUnitPayload,
)
from backend.services.curriculum_sources.base import (
    CurriculumSource,
    CurriculumSourceError,
    CurriculumSourceItem,
    CurriculumSourceSearchPage,
    SourceAvailability,
)
from backend.services.curriculum_sources.utils import coerce_dict, paginate_items, strip_html, unique_strings

OER_COMMONS_TIMEOUT_SECONDS = 20.0


class OERCommonsSource(CurriculumSource):
    source_id = 'oer-commons'
    display_name = 'OER Commons'
    description = 'OER Commons search connector for open curriculum and lesson collections.'

    def availability(self) -> SourceAvailability:
        if not (settings.oer_commons_api_token or '').strip():
            return SourceAvailability(
                enabled=False,
                detail='Set OER_COMMONS_API_TOKEN to enable live OER Commons search and import.',
                configuration_required=True,
            )
        return SourceAvailability(enabled=True)

    async def search(self, query: str, *, page: int = 1, page_size: int = 10) -> CurriculumSourceSearchPage:
        self.require_availability()
        payload = await self._request(
            'GET',
            '/search',
            params={
                'f.search': query,
                'batch_size': page_size,
                'batch_start': max(page - 1, 0) * page_size,
            },
        )
        raw_items = self._extract_results(payload)
        total_count = self._extract_total(payload, len(raw_items))
        items = [self._build_item(item) for item in raw_items]
        return CurriculumSourceSearchPage(
            source=self.source_id,
            query=query,
            page=page,
            page_size=page_size,
            total_count=total_count,
            items=items,
        )

    async def fetch(self, item_id: str) -> dict[str, Any]:
        self.require_availability()
        try:
            payload = await self._request('GET', f'/materials/{item_id}')
            if payload:
                return payload
        except CurriculumSourceError:
            pass
        payload = await self._request(
            'GET',
            '/search',
            params={
                'f.material_id': item_id,
                'batch_size': 1,
                'batch_start': 0,
            },
        )
        results = self._extract_results(payload)
        if not results:
            raise CurriculumSourceError('OER Commons item not found')
        return results[0]

    def convert_to_standard_format(self, raw_data: dict[str, Any]) -> CurriculumImportDocument:
        title = str(raw_data.get('title') or raw_data.get('material_name') or 'OER Commons resource')
        description = strip_html(raw_data.get('description') or raw_data.get('abstract'))
        subjects = unique_strings(raw_data.get('subject') or raw_data.get('subjects') or [raw_data.get('education_subject')])
        subject_name = subjects[0] if subjects else 'OER Commons'
        grade_levels = unique_strings(raw_data.get('education_levels') or raw_data.get('grade_levels') or [])
        standards = unique_strings(raw_data.get('standards') or raw_data.get('alignment') or [])
        resource_url = raw_data.get('url') or raw_data.get('material_url') or raw_data.get('link')
        return CurriculumImportDocument(
            name=title,
            description=description,
            source=self.source_id,
            metadata=CurriculumImportMetadata(
                grade_levels=grade_levels,
                standards_alignment=standards,
                external_source={
                    'source_id': raw_data.get('id') or raw_data.get('material_id'),
                    'url': resource_url,
                    'provider': raw_data.get('provider') or raw_data.get('author'),
                },
            ),
            subjects=[
                CurriculumImportSubjectPayload(
                    name=subject_name,
                    description=description,
                    metadata=CurriculumImportMetadata(
                        grade_levels=grade_levels,
                        standards_alignment=standards,
                    ),
                    units=[
                        CurriculumImportUnitPayload(
                            name='Imported OER Resource',
                            description='Reference entry imported from OER Commons.',
                            metadata=CurriculumImportMetadata(standards_alignment=standards),
                            lessons=[
                                CurriculumImportLessonPayload(
                                    name=title,
                                    description=description,
                                    estimated_minutes=45,
                                    objectives=[
                                        'Review the OER resource summary.',
                                        'Decide how to sequence this open resource inside the curriculum plan.',
                                    ],
                                    resources=[
                                        CurriculumImportResource(
                                            name='OER Commons resource',
                                            description='Open the original OER Commons listing.',
                                            resource_type='link',
                                            url=str(resource_url or ''),
                                            tags=['oer-commons'],
                                        )
                                    ],
                                    metadata=CurriculumImportMetadata(standards_alignment=standards),
                                )
                            ],
                        )
                    ],
                )
            ],
        )

    async def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        base_url = settings.oer_commons_api_base_url.rstrip('/')
        headers = {'Authorization': f"Bearer {settings.oer_commons_api_token.strip()}"}
        try:
            async with httpx.AsyncClient(timeout=OER_COMMONS_TIMEOUT_SECONDS, follow_redirects=True) as client:
                response = await client.request(method, f'{base_url}{path}', params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CurriculumSourceError(f'OER Commons request failed: {exc}') from exc
        if not isinstance(payload, dict):
            raise CurriculumSourceError('OER Commons returned an invalid response payload')
        return payload

    def _extract_results(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ('results', 'items', 'documents', 'materials'):
            value = payload.get(key)
            if isinstance(value, list):
                return [coerce_dict(item) for item in value]
        if 'title' in payload or 'material_name' in payload:
            return [payload]
        return []

    def _extract_total(self, payload: dict[str, Any], default: int) -> int:
        for key in ('total_count', 'count', 'total', 'num_found'):
            value = payload.get(key)
            if isinstance(value, int):
                return value
        return default

    def _build_item(self, raw_data: dict[str, Any]) -> CurriculumSourceItem:
        return CurriculumSourceItem(
            id=str(raw_data.get('id') or raw_data.get('material_id') or raw_data.get('slug') or ''),
            title=str(raw_data.get('title') or raw_data.get('material_name') or 'OER Commons resource'),
            description=strip_html(raw_data.get('description') or raw_data.get('abstract')),
            subjects=unique_strings(raw_data.get('subject') or raw_data.get('subjects') or [raw_data.get('education_subject')]),
            grade_levels=unique_strings(raw_data.get('education_levels') or raw_data.get('grade_levels') or []),
            url=raw_data.get('url') or raw_data.get('material_url') or raw_data.get('link'),
            image_url=raw_data.get('image_url') or raw_data.get('thumbnail_url'),
            license_name=raw_data.get('license') or raw_data.get('license_name'),
            metadata={
                'provider': raw_data.get('provider') or raw_data.get('author'),
                'material_type': raw_data.get('material_type'),
            },
        )
