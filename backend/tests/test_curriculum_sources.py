from __future__ import annotations

import pytest

from backend.schemas.curriculum import CurriculumImportDocument
from backend.services.curriculum_sources import CurriculumSourceError, CurriculumSourceUnavailable, SourceAvailability
from backend.services.curriculum_sources.ck12 import CK12Source
from backend.services.curriculum_sources.openstax import OpenStaxSource
from backend.services.curriculum_sources.oer_commons import OERCommonsSource
from tests.contracts import CURRICULUM
from tests.helpers import response_id


class _FakeSource:
    source_id = 'demo-source'
    display_name = 'Demo Source'
    description = 'Fake connector for curriculum source endpoint coverage.'

    def availability(self):
        return SourceAvailability(enabled=True)

    async def search(self, query: str, *, page: int = 1, page_size: int = 10):
        del page, page_size
        return type(
            'SearchPage',
            (),
            {
                'source': self.source_id,
                'query': query,
                'page': 1,
                'page_size': 10,
                'total_count': 1,
                'has_more': False,
                'items': [
                    type(
                        'Item',
                        (),
                        {
                            'id': 'demo-1',
                            'title': 'Demo Connector Curriculum',
                            'description': 'Connector search result.',
                            'subjects': ['Math'],
                            'grade_levels': ['6'],
                            'url': 'https://example.com/demo-1',
                            'image_url': None,
                            'license_name': 'CC BY',
                            'metadata': {'provider': 'demo'},
                        },
                    )()
                ],
            },
        )()

    async def fetch(self, item_id: str):
        assert item_id == 'demo-1'
        return {'title': 'Demo Connector Curriculum'}

    def convert_to_standard_format(self, raw_data):
        return CurriculumImportDocument.model_validate(
            {
                'name': raw_data['title'],
                'description': 'Imported through a fake connector.',
                'source': self.source_id,
                'subjects': [
                    {
                        'name': 'Math',
                        'units': [
                            {
                                'name': 'Unit 1',
                                'lessons': [
                                    {
                                        'name': 'Lesson 1',
                                        'objectives': ['Practice fractions'],
                                        'resources': [
                                            {
                                                'name': 'Demo Link',
                                                'resource_type': 'link',
                                                'url': 'https://example.com/demo-1',
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        )


class _DisabledSource(_FakeSource):
    source_id = 'locked-source'
    display_name = 'Locked Source'

    def availability(self):
        return SourceAvailability(
            enabled=False,
            configuration_required=True,
            detail='Connector requires additional configuration.',
        )

    async def search(self, query: str, *, page: int = 1, page_size: int = 10):
        raise RuntimeError('should not be called')


class _UnavailableSource(_FakeSource):
    source_id = 'unavailable-source'

    async def search(self, query: str, *, page: int = 1, page_size: int = 10):  # noqa: ARG002
        raise CurriculumSourceUnavailable('backend trace host=10.0.0.8')

    async def fetch(self, item_id: str):  # noqa: ARG002
        raise CurriculumSourceUnavailable('backend trace host=10.0.0.8')


class _FailingSource(_FakeSource):
    source_id = 'failing-source'

    async def search(self, query: str, *, page: int = 1, page_size: int = 10):  # noqa: ARG002
        raise CurriculumSourceError('internal connector secret=abc123')

    async def fetch(self, item_id: str):  # noqa: ARG002
        raise CurriculumSourceError('internal connector secret=abc123')


@pytest.mark.asyncio
async def test_curriculum_sources_list_search_and_import(authorized_client, monkeypatch):
    fake_source = _FakeSource()
    disabled_source = _DisabledSource()
    sources = {fake_source.source_id: fake_source, disabled_source.source_id: disabled_source}
    monkeypatch.setattr('backend.routers.curriculum.list_curriculum_sources', lambda: list(sources.values()))
    monkeypatch.setattr('backend.routers.curriculum.get_curriculum_source', lambda source_id: sources.get(source_id))

    listing = await authorized_client.get(CURRICULUM['sources'])
    assert listing.status_code == 200, listing.text
    listing_payload = listing.json()
    assert [item['source'] for item in listing_payload] == ['demo-source', 'locked-source']
    assert listing_payload[1]['configuration_required'] is True

    search = await authorized_client.get(
        CURRICULUM['source_search'].format(source_id='demo-source'),
        params={'q': 'demo'},
    )
    assert search.status_code == 200, search.text
    assert search.json()['items'][0]['item_id'] == 'demo-1'

    disabled_search = await authorized_client.get(
        CURRICULUM['source_search'].format(source_id='locked-source'),
        params={'q': 'demo'},
    )
    assert disabled_search.status_code == 503, disabled_search.text

    imported = await authorized_client.post(CURRICULUM['source_import'].format(source_id='demo-source', item_id='demo-1'))
    assert imported.status_code == 201, imported.text
    imported_payload = imported.json()
    curriculum_id = response_id(imported_payload)
    assert imported_payload['source'] == 'demo-source'
    assert imported_payload['subjects'][0]['units'][0]['lessons'][0]['name'] == 'Lesson 1'

    detail = await authorized_client.get(CURRICULUM['import_detail'].format(curriculum_id=curriculum_id))
    assert detail.status_code == 200, detail.text
    assert detail.json()['payload']['source'] == 'demo-source'


@pytest.mark.asyncio
async def test_curriculum_source_errors_return_generic_messages(authorized_client, monkeypatch):
    unavailable_source = _UnavailableSource()
    failing_source = _FailingSource()
    sources = {
        unavailable_source.source_id: unavailable_source,
        failing_source.source_id: failing_source,
    }
    monkeypatch.setattr('backend.routers.curriculum.get_curriculum_source', lambda source_id: sources.get(source_id))

    unavailable_search = await authorized_client.get(
        CURRICULUM['source_search'].format(source_id='unavailable-source'),
        params={'q': 'demo'},
    )
    assert unavailable_search.status_code == 503, unavailable_search.text
    assert unavailable_search.json()['detail'] == 'Curriculum source is unavailable'
    assert '10.0.0.8' not in unavailable_search.text

    failing_search = await authorized_client.get(
        CURRICULUM['source_search'].format(source_id='failing-source'),
        params={'q': 'demo'},
    )
    assert failing_search.status_code == 502, failing_search.text
    assert 'abc123' not in failing_search.text

    unavailable_import = await authorized_client.post(
        CURRICULUM['source_import'].format(source_id='unavailable-source', item_id='demo-1'),
    )
    assert unavailable_import.status_code == 503, unavailable_import.text
    assert unavailable_import.json()['detail'] == 'Curriculum source is unavailable'

    failing_import = await authorized_client.post(
        CURRICULUM['source_import'].format(source_id='failing-source', item_id='demo-1'),
    )
    assert failing_import.status_code == 502, failing_import.text
    assert 'abc123' not in failing_import.text


def test_openstax_connector_converts_detail_payload_to_standard_document():
    connector = OpenStaxSource()
    document = connector.convert_to_standard_format(
        {
            'title': 'Biology 2e',
            'description': '<p>Comprehensive biology textbook.</p>',
            'meta': {
                'slug': 'biology-2e',
                'html_url': 'https://openstax.org/details/books/biology-2e',
                'detail_url': 'https://openstax.org/apps/cms/api/books/biology-2e/?format=json',
            },
            'book_subjects': [{'subject_name': 'Science'}],
            'book_categories': [{'subject_category': 'Biology'}],
            'book_student_resources': [
                {
                    'resource_heading': 'Study Guide',
                    'resource_description': '<p>Use this guide.</p>',
                    'link_document_url': 'https://example.com/guide.pdf',
                }
            ],
            'high_resolution_pdf_url': 'https://example.com/biology.pdf',
            'webview_rex_link': 'https://openstax.org/books/biology-2e/pages/1-introduction',
            'license_name': 'CC BY',
            'license_version': '4.0',
            'license_url': 'https://creativecommons.org/licenses/by/4.0/',
            'authors': [{'value': 'OpenStax Authors'}],
            'subject_categories': ['Biology'],
            'is_hs': True,
        }
    )

    assert document.source == 'openstax'
    assert document.subjects[0].name == 'Science'
    assert document.subjects[0].units[0].name == 'Biology'
    assert document.subjects[0].units[0].lessons[0].resources[0].url == 'https://openstax.org/books/biology-2e/pages/1-introduction'
    assert document.metadata.external_source['source_id'] == 'biology-2e'


@pytest.mark.asyncio
async def test_ck12_connector_search_paginates_curated_catalog():
    connector = CK12Source()
    first_page = await connector.search('math', page=1, page_size=2)
    second_page = await connector.search('math', page=2, page_size=2)

    assert first_page.total_count >= 4
    assert len(first_page.items) == 2
    assert first_page.has_more is True
    assert len(second_page.items) == 2
    assert second_page.items[0].id != first_page.items[0].id


def test_oer_commons_connector_reports_missing_token(monkeypatch):
    monkeypatch.setattr('backend.config.settings.oer_commons_api_token', None, raising=False)
    connector = OERCommonsSource()
    availability = connector.availability()

    assert availability.enabled is False
    assert availability.configuration_required is True


def test_strip_html_ignores_non_string_values():
    from backend.services.curriculum_sources.utils import strip_html

    assert strip_html(None) is None
    assert strip_html({'value': 'x'}) is None
    assert strip_html(['a', 'b']) is None
    assert strip_html('<p>Hello&amp;bye</p>') == 'Hello&bye'


def test_openstax_build_catalog_item_handles_streamfield_promote_snippet():
    connector = OpenStaxSource()

    # promote_snippet is a StreamField-style list of blocks (current OpenStax API shape),
    # which previously crashed _build_catalog_item with a TypeError -> 500 on search.
    item = connector._build_catalog_item(
        {
            'slug': 'books/biology-2e',
            'title': 'Biology 2e',
            'promote_snippet': [
                {'type': 'content', 'value': {'name': 'Assignable', 'description': '<p>Study anytime.</p>'}},
            ],
            'subjects': ['Science'],
        }
    )

    assert item.id == 'biology-2e'
    assert item.title == 'Biology 2e'
    assert item.description == 'Study anytime.'


@pytest.mark.parametrize('promote_snippet', [[], None, [{'type': 'content', 'value': {}}], 'plain string promo'])
def test_openstax_build_catalog_item_promote_snippet_variants(promote_snippet):
    connector = OpenStaxSource()
    item = connector._build_catalog_item(
        {'slug': 'books/x', 'title': 'X', 'promote_snippet': promote_snippet}
    )
    assert item.title == 'X'
    if promote_snippet == 'plain string promo':
        assert item.description == 'plain string promo'
    else:
        assert item.description is None


def test_import_metadata_folds_unknown_keys_into_extensions():
    from backend.schemas.curriculum import CurriculumImportMetadata

    # AI-generated drafts often emit ad-hoc scheduling fields (e.g. a per-lesson
    # `date`). These must be retained under `extensions` rather than failing the
    # whole import with extra_forbidden.
    metadata = CurriculumImportMetadata.model_validate(
        {'date': '7/6/26', 'week': 3, 'grade_levels': ['3']}
    )

    assert metadata.grade_levels == ['3']
    assert metadata.extensions == {'date': '7/6/26', 'week': 3}


def test_import_metadata_preserves_explicit_extensions_over_unknown_keys():
    from backend.schemas.curriculum import CurriculumImportMetadata

    metadata = CurriculumImportMetadata.model_validate(
        {'date': '7/6/26', 'extensions': {'date': 'original'}}
    )

    # An explicit extensions value wins; the stray top-level key does not clobber it.
    assert metadata.extensions == {'date': 'original'}


def test_import_document_with_lesson_dates_validates():
    document = CurriculumImportDocument.model_validate(
        {
            'name': 'Weekly Plan',
            'subjects': [
                {
                    'name': 'Math',
                    'units': [
                        {
                            'name': 'Unit 1',
                            'lessons': [
                                {'name': 'Lesson 1', 'metadata': {'date': '7/6/26'}},
                                {'name': 'Lesson 2', 'metadata': {'date': '7/13/26'}},
                            ],
                        }
                    ],
                }
            ],
        }
    )

    lessons = document.subjects[0].units[0].lessons
    assert lessons[0].metadata.extensions == {'date': '7/6/26'}
    assert lessons[1].metadata.extensions == {'date': '7/13/26'}

