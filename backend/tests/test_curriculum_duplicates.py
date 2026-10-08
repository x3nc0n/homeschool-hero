from __future__ import annotations

import copy

import pytest

from backend.schemas.curriculum import CurriculumImportDocument
from backend.services.curriculum_duplicates import (
    find_internal_duplicate_paths,
    is_generic_lesson,
    normalize_name,
)
from tests.contracts import CURRICULUM
from tests.helpers import response_id, sync_csrf_header

def _draft(
    name: str = 'Saxon Math 5/4',
    *,
    subject: str = 'Mathematics',
    unit: str = 'Fractions',
    lessons: tuple[str, ...] = ('Adding Fractions', 'Subtracting Fractions', 'Comparing Fractions'),
    grade_levels: list[str] | None = None,
    edition: str | None = None,
    source: str = 'manual',
) -> dict:
    metadata: dict = {'grade_levels': grade_levels or ['4']}
    if edition is not None:
        metadata['edition'] = edition
    return {
        'name': name,
        'source': source,
        'metadata': metadata,
        'subjects': [
            {
                'name': subject,
                'units': [{'name': unit, 'lessons': [{'name': lesson} for lesson in lessons]}],
            }
        ],
    }


async def _create(client, draft: dict, **extra) -> int:
    response = await client.post(CURRICULUM['import_confirm'], json={'draft': draft, **extra})
    assert response.status_code == 201, response.text
    return response_id(response.json())


async def _check(client, draft: dict) -> list[dict]:
    response = await client.post(CURRICULUM['import_duplicate_check'], json={'draft': draft})
    assert response.status_code == 200, response.text
    return response.json()['matches']


def _error(response) -> dict:
    body = response.json()
    assert 'detail' in body
    return body['error']


def test_normalize_name_ignores_cosmetic_differences():
    assert normalize_name('  Adding   Fractions ') == normalize_name('adding fractions')
    assert normalize_name('Adding-Fractions!') == normalize_name('Adding Fractions')
    assert normalize_name('Ｍａｔｈ') == 'math'
    assert normalize_name("Student\u2019s Guide") == normalize_name("Students Guide")
    assert normalize_name('STRASSE') == normalize_name('straße')
    assert normalize_name('Adding Fractions') != normalize_name('Adding Decimals')


def test_generic_lessons_detected():
    for name in ('Lesson 1', 'lesson 12', 'Week 3', 'Introduction', 'Unit Review', 'chapter iv', 'Quiz'):
        assert is_generic_lesson(normalize_name(name)), name
    assert not is_generic_lesson(normalize_name('Adding Fractions'))


def test_internal_duplicate_paths_use_exact_constraint_names():
    document = CurriculumImportDocument.model_validate(
        {
            'name': 'Sibling Names',
            'subjects': [
                {'name': 'Math', 'units': [{'name': 'U', 'lessons': [{'name': 'A'}, {'name': 'A'}, {'name': 'a'}]}]},
                {'name': 'Math', 'units': [{'name': 'U', 'lessons': [{'name': 'B'}]}, {'name': 'U', 'lessons': [{'name': 'C'}]}]},
            ],
        }
    )
    assert find_internal_duplicate_paths(document) == [
        'subjects[0].units[0].lessons[1].name',
        'subjects[1].name',
        'subjects[1].units[1].name',
    ]


@pytest.mark.asyncio
async def test_same_content_different_title_and_file_is_duplicate(authorized_client):
    existing_id = await _create(authorized_client, _draft('Saxon Math 5/4'))

    candidate = _draft('saxon-scope-v2.txt import', source='ai-import')
    candidate['subjects'][0]['name'] = '  MATHEMATICS '
    candidate['subjects'][0]['units'][0]['lessons'][0]['name'] = 'Adding  Fractions.'
    matches = await _check(authorized_client, candidate)

    assert len(matches) == 1
    match = matches[0]
    assert set(match) == {
        'id', 'name', 'grade_levels', 'edition', 'reason', 'matched_subjects', 'matched_units', 'matched_lessons'
    }
    assert match['id'] == existing_id
    assert match['name'] == 'Saxon Math 5/4'
    assert match['reason'] == 'exact_curriculum'
    assert match['grade_levels'] == ['4']
    assert match['edition'] is None
    assert match['matched_subjects'] == ['Mathematics']
    assert match['matched_units'] == ['Fractions']
    assert match['matched_lessons'] == ['Adding Fractions', 'Subtracting Fractions', 'Comparing Fractions']

    rejected = await authorized_client.post(CURRICULUM['import_confirm'], json={'draft': candidate})
    assert rejected.status_code == 409, rejected.text
    error = _error(rejected)
    assert error['code'] == 'curriculum_import_duplicate_conflict'
    assert [item['id'] for item in error['details']['matches']] == [existing_id]

    accepted = await authorized_client.post(
        CURRICULUM['import_confirm'],
        json={'draft': candidate, 'acknowledged_duplicate_ids': [existing_id]},
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()['name'] == 'saxon-scope-v2.txt import'


@pytest.mark.asyncio
async def test_partial_overlap_requires_same_unit_and_two_specific_lessons(authorized_client):
    existing_id = await _create(authorized_client, _draft('Existing Math'))

    one_lesson = _draft('One Shared', lessons=('Adding Fractions', 'Fraction Word Problems'))
    assert await _check(authorized_client, one_lesson) == []

    two_lessons = _draft('Two Shared', lessons=('Adding Fractions', 'Subtracting Fractions', 'Fraction Word Problems'))
    matches = await _check(authorized_client, two_lessons)
    assert [(item['id'], item['reason']) for item in matches] == [(existing_id, 'partial_overlap')]
    assert matches[0]['matched_lessons'] == ['Adding Fractions', 'Subtracting Fractions']
    assert matches[0]['matched_units'] == ['Fractions']

    other_unit = _draft('Other Unit', unit='Fractions Part 2', lessons=('Adding Fractions', 'Subtracting Fractions'))
    assert await _check(authorized_client, other_unit) == []


@pytest.mark.asyncio
async def test_generic_lessons_alone_are_not_flagged(authorized_client):
    generic = ('Lesson 1', 'Lesson 2', 'Unit Review', 'Introduction')
    await _create(authorized_client, _draft('Generic A', lessons=generic))
    assert await _check(authorized_client, _draft('Generic B', lessons=generic)) == []
    mixed = _draft('Generic C', lessons=('Lesson 1', 'Lesson 2', 'Adding Fractions'))
    assert await _check(authorized_client, mixed) == []


@pytest.mark.asyncio
async def test_different_grades_or_editions_are_distinct(authorized_client):
    await _create(authorized_client, _draft('Grade Four', grade_levels=['4th Grade'], edition='3rd Edition'))

    assert await _check(authorized_client, _draft('Grade Five', grade_levels=['5'], edition='3rd Edition')) == []
    assert await _check(authorized_client, _draft('Fourth Ed', grade_levels=['4'], edition='4th Edition')) == []

    same = await _check(authorized_client, _draft('Same', grade_levels=['grade 4'], edition='3rd  edition'))
    assert [item['reason'] for item in same] == ['exact_curriculum']
    assert same[0]['edition'] == '3rd Edition'


@pytest.mark.asyncio
async def test_manual_and_direct_paths_share_duplicate_gate(authorized_client):
    existing_id = await _create(authorized_client, _draft('Original'))

    manual = await authorized_client.post(CURRICULUM['import_create'], json=_draft('Manual Copy'))
    assert manual.status_code == 409, manual.text
    assert _error(manual)['code'] == 'curriculum_import_duplicate_conflict'

    ai_no_ack = await authorized_client.post(CURRICULUM['ai_import_confirm'], json={'draft': _draft('AI Copy')})
    assert ai_no_ack.status_code == 409, ai_no_ack.text
    assert _error(ai_no_ack)['details']['matches'][0]['id'] == existing_id

    ai_ack = await authorized_client.post(
        CURRICULUM['ai_import_confirm'],
        json={'draft': _draft('AI Copy'), 'acknowledged_duplicate_ids': [existing_id]},
    )
    assert ai_ack.status_code == 201, ai_ack.text

    partial_ack = await authorized_client.post(
        CURRICULUM['import_confirm'],
        json={'draft': _draft('Third Copy'), 'acknowledged_duplicate_ids': [existing_id]},
    )
    assert partial_ack.status_code == 409, partial_ack.text
    assert len(_error(partial_ack)['details']['matches']) == 2


@pytest.mark.asyncio
async def test_name_conflict_cannot_be_acknowledged(authorized_client):
    existing_id = await _create(authorized_client, _draft('Same Name'))
    response = await authorized_client.post(
        CURRICULUM['import_confirm'],
        json={'draft': _draft('Same Name', lessons=('Decimals', 'Percents')), 'acknowledged_duplicate_ids': [existing_id]},
    )
    assert response.status_code == 409, response.text
    assert _error(response)['code'] == 'curriculum_import_name_conflict'


@pytest.mark.asyncio
async def test_sibling_duplicate_names_rejected_with_safe_paths(authorized_client):
    draft = _draft('Siblings', lessons=('Adding Fractions', 'Adding Fractions'))
    response = await authorized_client.post(CURRICULUM['import_confirm'], json={'draft': draft})
    assert response.status_code == 422, response.text
    error = _error(response)
    assert error['code'] == 'curriculum_import_duplicate_names'
    assert error['details']['paths'] == ['subjects[0].units[0].lessons[1].name']
    listing = await authorized_client.get(CURRICULUM['imports'])
    assert all(item['name'] != 'Siblings' for item in listing.json())


@pytest.mark.asyncio
async def test_unrelated_or_foreign_acknowledgements_do_not_bypass(authorized_client, secondary_client, create_family_user):
    existing_id = await _create(authorized_client, _draft('Family One'))

    other = await create_family_user(family_name='Other Family', email='dupe-other@example.com', password='other-password')
    login = await secondary_client.post(
        '/api/auth/login',
        json={'email': other['email'], 'password': other['password'], 'family_id': other['family_id']},
    )
    assert login.status_code == 200, login.text
    sync_csrf_header(secondary_client)

    assert await _check(secondary_client, _draft('Family Two')) == []
    foreign_id = await _create(secondary_client, _draft('Family Two'))

    bogus = await authorized_client.post(
        CURRICULUM['import_confirm'],
        json={'draft': _draft('Bypass'), 'acknowledged_duplicate_ids': [foreign_id, existing_id + 999]},
    )
    assert bogus.status_code == 409, bogus.text
    assert [item['id'] for item in _error(bogus)['details']['matches']] == [existing_id]


@pytest.mark.asyncio
async def test_standards_alignment_disjoint_is_distinct(authorized_client):
    draft = _draft('Standards A')
    draft['metadata']['standards_alignment'] = ['CCSS.MATH.4.NF']
    await _create(authorized_client, draft)
    other = copy.deepcopy(draft)
    other['name'] = 'Standards B'
    other['metadata']['standards_alignment'] = ['TEKS.MATH.4.3']
    assert await _check(authorized_client, other) == []