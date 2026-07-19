from __future__ import annotations

from typing import Any

import httpx

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
)
from backend.services.curriculum_sources.utils import coerce_dict, paginate_items, strip_html, unique_strings

OPENSTAX_CATALOG_URL = 'https://openstax.org/apps/cms/api/books/?format=json'
OPENSTAX_DETAIL_URL_TEMPLATE = 'https://openstax.org/apps/cms/api/books/{item_id}/?format=json'
OPENSTAX_TIMEOUT_SECONDS = 20.0


class OpenStaxSource(CurriculumSource):
    source_id = 'openstax'
    display_name = 'OpenStax'
    description = 'Free OpenStax textbooks with structured metadata and download links.'

    async def search(self, query: str, *, page: int = 1, page_size: int = 10) -> CurriculumSourceSearchPage:
        catalog = await self._fetch_catalog()
        normalized_query = query.strip().casefold()
        matches: list[CurriculumSourceItem] = []
        for raw_item in catalog:
            search_terms = ' '.join(
                [
                    str(raw_item.get('title') or ''),
                    ' '.join(raw_item.get('subjects') or []),
                    ' '.join(raw_item.get('subject_categories') or []),
                    ' '.join(raw_item.get('k12subject') or []),
                ]
            ).casefold()
            if normalized_query and normalized_query not in search_terms:
                continue
            matches.append(self._build_catalog_item(raw_item))
        return CurriculumSourceSearchPage(
            source=self.source_id,
            query=query,
            page=page,
            page_size=page_size,
            total_count=len(matches),
            items=paginate_items(matches, page=page, page_size=page_size),
        )

    async def fetch(self, item_id: str) -> dict[str, Any]:
        url = OPENSTAX_DETAIL_URL_TEMPLATE.format(item_id=item_id)
        try:
            async with httpx.AsyncClient(timeout=OPENSTAX_TIMEOUT_SECONDS, follow_redirects=True) as client:
                response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CurriculumSourceError(f'OpenStax fetch failed: {exc}') from exc
        if not isinstance(payload, dict):
            raise CurriculumSourceError('OpenStax returned an invalid detail payload')
        return payload

    def convert_to_standard_format(self, raw_data: dict[str, Any]) -> CurriculumImportDocument:
        metadata = CurriculumImportMetadata(
            grade_levels=self._grade_levels(raw_data),
            external_source={
                'source_id': raw_data.get('meta', {}).get('slug') or raw_data.get('slug'),
                'html_url': raw_data.get('meta', {}).get('html_url'),
                'detail_api_url': raw_data.get('meta', {}).get('detail_url'),
                'pdf_url': raw_data.get('high_resolution_pdf_url'),
                'webview_url': raw_data.get('webview_rex_link') or raw_data.get('webview_link'),
                'license_url': raw_data.get('license_url'),
            },
            extensions={
                'license_name': raw_data.get('license_name'),
                'license_version': raw_data.get('license_version'),
                'authors': unique_strings(item.get('value') or item.get('name') for item in raw_data.get('authors') or []),
                'subject_categories': unique_strings(raw_data.get('subject_categories') or []),
            },
        )
        subject_name = self._subject_name(raw_data)
        unit_name = self._unit_name(raw_data)
        description = strip_html(raw_data.get('description'))
        resources = self._resources(raw_data)
        return CurriculumImportDocument(
            name=str(raw_data.get('title') or 'OpenStax Curriculum'),
            description=description,
            source=self.source_id,
            metadata=metadata,
            subjects=[
                CurriculumImportSubjectPayload(
                    name=subject_name,
                    description=description,
                    metadata=CurriculumImportMetadata(
                        grade_levels=self._grade_levels(raw_data),
                        external_source={'subject': subject_name},
                    ),
                    units=[
                        CurriculumImportUnitPayload(
                            name=unit_name,
                            description='Imported textbook overview and references.',
                            metadata=CurriculumImportMetadata(
                                external_source={'category': unit_name},
                            ),
                            lessons=[
                                CurriculumImportLessonPayload(
                                    name=str(raw_data.get('title') or subject_name),
                                    description=description,
                                    estimated_minutes=60,
                                    objectives=[
                                        'Review the textbook overview and scope.',
                                        'Use the linked text and supporting resources during planning.',
                                    ],
                                    resources=resources,
                                )
                            ],
                        )
                    ],
                )
            ],
        )

    async def _fetch_catalog(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=OPENSTAX_TIMEOUT_SECONDS, follow_redirects=True) as client:
                response = await client.get(OPENSTAX_CATALOG_URL)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CurriculumSourceError(f'OpenStax catalog request failed: {exc}') from exc
        books = payload.get('books') if isinstance(payload, dict) else None
        if not isinstance(books, list):
            raise CurriculumSourceError('OpenStax catalog response did not include books')
        return [coerce_dict(item) for item in books]

    def _build_catalog_item(self, raw_item: dict[str, Any]) -> CurriculumSourceItem:
        slug = str(raw_item.get('slug') or '').replace('books/', '')
        return CurriculumSourceItem(
            id=slug,
            title=str(raw_item.get('title') or slug or 'OpenStax item'),
            description=self._promote_snippet(raw_item),
            subjects=unique_strings((raw_item.get('subjects') or []) + (raw_item.get('k12subject') or [])),
            grade_levels=self._grade_levels(raw_item),
            url=raw_item.get('webview_rex_link') or f'https://openstax.org/details/{raw_item.get("slug") or ""}',
            image_url=raw_item.get('cover_url'),
            license_name='CC BY' if raw_item.get('high_resolution_pdf_url') else None,
            metadata={
                'subject_categories': unique_strings(raw_item.get('subject_categories') or []),
                'is_high_school': bool(raw_item.get('is_hs')),
                'is_ap': bool(raw_item.get('is_ap')),
            },
        )

    def _grade_levels(self, raw_item: dict[str, Any]) -> list[str]:
        if raw_item.get('is_hs') or raw_item.get('is_ap'):
            return ['9', '10', '11', '12']
        return []

    def _promote_snippet(self, raw_item: dict[str, Any]) -> str | None:
        snippet = raw_item.get('promote_snippet')
        if isinstance(snippet, str):
            return strip_html(snippet)
        if isinstance(snippet, list):
            for block in snippet:
                text: Any = block
                if isinstance(block, dict):
                    value = block.get('value')
                    if isinstance(value, dict):
                        text = value.get('description') or value.get('value') or value.get('name')
                    else:
                        text = value
                cleaned = strip_html(text)
                if cleaned:
                    return cleaned
        return None

    def _subject_name(self, raw_data: dict[str, Any]) -> str:
        for collection_key in ('k12book_subjects', 'book_subjects'):
            for item in raw_data.get(collection_key) or []:
                if isinstance(item, dict):
                    for field in ('subject_category', 'subject_name'):
                        value = item.get(field)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
        subjects = unique_strings((raw_data.get('subjects') or []) + (raw_data.get('k12subject') or []))
        return subjects[0] if subjects else 'OpenStax'

    def _unit_name(self, raw_data: dict[str, Any]) -> str:
        categories = unique_strings(raw_data.get('subject_categories') or [])
        return categories[0] if categories else 'Textbook Overview'

    def _resources(self, raw_data: dict[str, Any]) -> list[CurriculumImportResource]:
        resources: list[CurriculumImportResource] = []
        primary_links = [
            ('Open textbook', raw_data.get('webview_rex_link') or raw_data.get('webview_link')),
            ('Download PDF', raw_data.get('high_resolution_pdf_url')),
            ('Book details', raw_data.get('meta', {}).get('html_url')),
        ]
        for resource_name, url in primary_links:
            if not isinstance(url, str) or not url.strip():
                continue
            resources.append(
                CurriculumImportResource(
                    name=resource_name,
                    resource_type='link',
                    url=url.strip(),
                    tags=['openstax'],
                )
            )
        for item in (raw_data.get('book_student_resources') or [])[:8]:
            if not isinstance(item, dict):
                continue
            url = item.get('link_document_url') or item.get('link_external')
            if not isinstance(url, str) or not url.strip():
                continue
            resources.append(
                CurriculumImportResource(
                    name=str(item.get('resource_heading') or 'Student resource'),
                    description=strip_html(item.get('resource_description')),
                    resource_type='link',
                    url=url.strip(),
                    tags=['openstax', 'student-resource'],
                )
            )
        return resources[:20]
