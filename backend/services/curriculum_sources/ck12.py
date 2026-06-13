from __future__ import annotations

from typing import Any

from backend.schemas.curriculum import (
    CurriculumImportDocument,
    CurriculumImportLessonPayload,
    CurriculumImportMetadata,
    CurriculumImportResource,
    CurriculumImportSubjectPayload,
    CurriculumImportUnitPayload,
)
from backend.services.curriculum_sources.base import CurriculumSource, CurriculumSourceError, CurriculumSourceItem, CurriculumSourceSearchPage
from backend.services.curriculum_sources.utils import paginate_items

CK12_CATALOG: list[dict[str, Any]] = [
    {
        'id': 'ck12-middle-school-math-grade-6',
        'title': 'CK-12 Middle School Math Grade 6',
        'description': 'FlexBook-aligned middle school math curriculum with lessons, practice, and enrichment.',
        'subjects': ['Math'],
        'grade_levels': ['6'],
        'url': 'https://www.ck12.org/book/ck-12-middle-school-math-grade-6/',
    },
    {
        'id': 'ck12-middle-school-math-grade-7',
        'title': 'CK-12 Middle School Math Grade 7',
        'description': 'Grade 7 FlexBook sequence covering ratios, proportional thinking, and geometry.',
        'subjects': ['Math'],
        'grade_levels': ['7'],
        'url': 'https://www.ck12.org/book/ck-12-middle-school-math-grade-7/',
    },
    {
        'id': 'ck12-middle-school-math-grade-8',
        'title': 'CK-12 Middle School Math Grade 8',
        'description': 'Grade 8 FlexBook-aligned math pathways with algebra and geometry foundations.',
        'subjects': ['Math'],
        'grade_levels': ['8'],
        'url': 'https://www.ck12.org/book/ck-12-middle-school-math-grade-8/',
    },
    {
        'id': 'ck12-algebra-1-flexbook-2.0',
        'title': 'CK-12 Algebra I FlexBook 2.0',
        'description': 'Comprehensive Algebra I FlexBook with worked examples, practice, and videos.',
        'subjects': ['Math'],
        'grade_levels': ['8', '9'],
        'url': 'https://www.ck12.org/book/ck-12-algebra-i-flexbook-2.0/',
    },
    {
        'id': 'ck12-biology-flexbook-2.0',
        'title': 'CK-12 Biology FlexBook 2.0',
        'description': 'Biology FlexBook with life science concepts, labs, and real-world applications.',
        'subjects': ['Science', 'Biology'],
        'grade_levels': ['9', '10', '11', '12'],
        'url': 'https://www.ck12.org/book/ck-12-biology-flexbook-2.0/',
    },
    {
        'id': 'ck12-chemistry-flexbook-2.0',
        'title': 'CK-12 Chemistry FlexBook 2.0',
        'description': 'Chemistry FlexBook featuring matter, reactions, stoichiometry, and lab support.',
        'subjects': ['Science', 'Chemistry'],
        'grade_levels': ['9', '10', '11', '12'],
        'url': 'https://www.ck12.org/book/ck-12-chemistry-flexbook-2.0/',
    },
    {
        'id': 'ck12-physics-flexbook-2.0',
        'title': 'CK-12 Physics FlexBook 2.0',
        'description': 'Physics FlexBook covering motion, energy, waves, and engineering applications.',
        'subjects': ['Science', 'Physics'],
        'grade_levels': ['10', '11', '12'],
        'url': 'https://www.ck12.org/book/ck-12-physics-flexbook-2.0/',
    },
    {
        'id': 'ck12-earth-science-flexbook-2.0',
        'title': 'CK-12 Earth Science FlexBook 2.0',
        'description': 'Earth science FlexBook spanning geology, weather, astronomy, and environmental systems.',
        'subjects': ['Science', 'Earth Science'],
        'grade_levels': ['6', '7', '8', '9'],
        'url': 'https://www.ck12.org/book/ck-12-earth-science-flexbook-2.0/',
    },
]


class CK12Source(CurriculumSource):
    source_id = 'ck12'
    display_name = 'CK-12'
    description = 'Curated CK-12 FlexBook catalog mapped into the homeschool curriculum schema.'

    async def search(self, query: str, *, page: int = 1, page_size: int = 10) -> CurriculumSourceSearchPage:
        normalized_query = query.strip().casefold()
        matches: list[CurriculumSourceItem] = []
        for item in CK12_CATALOG:
            haystack = ' '.join(
                [
                    str(item.get('title') or ''),
                    str(item.get('description') or ''),
                    ' '.join(item.get('subjects') or []),
                    ' '.join(item.get('grade_levels') or []),
                ]
            ).casefold()
            if normalized_query and normalized_query not in haystack:
                continue
            matches.append(
                CurriculumSourceItem(
                    id=str(item['id']),
                    title=str(item['title']),
                    description=str(item['description']),
                    subjects=list(item.get('subjects') or []),
                    grade_levels=list(item.get('grade_levels') or []),
                    url=item.get('url'),
                    metadata={'catalog_mode': 'curated'},
                )
            )
        return CurriculumSourceSearchPage(
            source=self.source_id,
            query=query,
            page=page,
            page_size=page_size,
            total_count=len(matches),
            items=paginate_items(matches, page=page, page_size=page_size),
        )

    async def fetch(self, item_id: str) -> dict[str, Any]:
        for item in CK12_CATALOG:
            if item['id'] == item_id:
                return dict(item)
        raise CurriculumSourceError('CK-12 item not found')

    def convert_to_standard_format(self, raw_data: dict[str, Any]) -> CurriculumImportDocument:
        title = str(raw_data.get('title') or 'CK-12 FlexBook')
        description = str(raw_data.get('description') or 'CK-12 FlexBook import')
        subjects = list(raw_data.get('subjects') or ['CK-12'])
        grade_levels = list(raw_data.get('grade_levels') or [])
        primary_subject = subjects[0]
        secondary_subject = subjects[1] if len(subjects) > 1 else primary_subject
        return CurriculumImportDocument(
            name=title,
            description=description,
            source=self.source_id,
            metadata=CurriculumImportMetadata(
                grade_levels=grade_levels,
                external_source={
                    'source_id': raw_data.get('id'),
                    'catalog_mode': 'curated',
                    'url': raw_data.get('url'),
                },
            ),
            subjects=[
                CurriculumImportSubjectPayload(
                    name=primary_subject,
                    description=description,
                    metadata=CurriculumImportMetadata(
                        grade_levels=grade_levels,
                        external_source={'subject': primary_subject},
                    ),
                    units=[
                        CurriculumImportUnitPayload(
                            name=f'{secondary_subject} FlexBook Overview',
                            description='Imported CK-12 FlexBook reference entry for homeschool planning.',
                            lessons=[
                                CurriculumImportLessonPayload(
                                    name=title,
                                    description=description,
                                    estimated_minutes=45,
                                    objectives=[
                                        'Review the CK-12 FlexBook scope and sequence.',
                                        'Adapt lessons and practice sets into the family plan.',
                                    ],
                                    resources=[
                                        CurriculumImportResource(
                                            name='CK-12 FlexBook',
                                            description='Open the CK-12 FlexBook catalog entry.',
                                            resource_type='link',
                                            url=str(raw_data.get('url') or ''),
                                            tags=['ck12', 'flexbook'],
                                        )
                                    ],
                                )
                            ],
                        )
                    ],
                )
            ],
        )
