from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.models.calendar import CalendarEventType, TermType

DATA_PATH = Path(__file__).resolve().parents[1] / 'app' / 'data' / 'holidays.json'

TERM_STRUCTURE_CONFIG: dict[str, dict[str, Any]] = {
    'semesters': {
        'count': 2,
        'names': ['Fall Semester', 'Spring Semester'],
        'term_type': TermType.semester,
    },
    'quarters': {
        'count': 4,
        'names': ['Q1', 'Q2', 'Q3', 'Q4'],
        'term_type': TermType.quarter,
    },
    'trimesters': {
        'count': 3,
        'names': ['Trimester 1', 'Trimester 2', 'Trimester 3'],
        'term_type': TermType.trimester,
    },
    'custom': {
        'count': 1,
        'names': ['Custom Term'],
        'term_type': TermType.custom,
    },
}

SCHOOL_YEAR_TEMPLATES: list[dict[str, Any]] = [
    {
        'key': 'traditional_aug_may',
        'name': 'Traditional August to May',
        'description': 'A common US schedule with a late-summer start and late-spring finish.',
        'suggested_start_date': '08-15',
        'suggested_end_date': '05-30',
        'default_term_structure': 'semesters',
    },
    {
        'key': 'traditional_sep_jun',
        'name': 'Traditional September to June',
        'description': 'A northern-region pattern that starts after Labor Day and runs into June.',
        'suggested_start_date': '09-01',
        'suggested_end_date': '06-15',
        'default_term_structure': 'quarters',
    },
    {
        'key': 'year_round_balanced',
        'name': 'Year-Round Balanced',
        'description': 'A balanced calendar with shorter terms and more frequent breaks across the full year.',
        'suggested_start_date': '07-15',
        'suggested_end_date': '06-30',
        'default_term_structure': 'quarters',
    },
    {
        'key': 'trimester_focus',
        'name': 'Trimester Focused',
        'description': 'Three evenly sized academic blocks for families that prefer trimester reporting.',
        'suggested_start_date': '08-10',
        'suggested_end_date': '05-28',
        'default_term_structure': 'trimesters',
    },
]


@lru_cache(maxsize=1)
def load_holiday_entries() -> dict[str, dict[str, Any]]:
    entries = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    return {entry['key']: entry for entry in entries}


def get_school_year_templates() -> list[dict[str, Any]]:
    return [template.copy() for template in SCHOOL_YEAR_TEMPLATES]


def get_selectable_holiday_presets(year: int) -> list[dict[str, Any]]:
    academic_start = date(year, 8, 1)
    academic_end = date(year + 1, 7, 31)
    entries = load_holiday_entries()
    selectable = [entry for entry in entries.values() if entry.get('selectable')]
    order = {'federal': 0, 'religious': 1, 'school_break': 2}
    result: list[dict[str, Any]] = []
    for entry in sorted(selectable, key=lambda item: (order.get(item['type'], 99), item['name'])):
        events = resolve_holiday_selection(entry['key'], academic_start, academic_end)
        result.append(_build_holiday_preview(entry, events))
    return result


def generate_terms(*, start_date: date, end_date: date, term_structure: str) -> list[dict[str, Any]]:
    config = TERM_STRUCTURE_CONFIG[term_structure]
    total_days = (end_date - start_date).days + 1
    base_days, remainder = divmod(total_days, config['count'])
    current_start = start_date
    generated: list[dict[str, Any]] = []
    for index, name in enumerate(config['names']):
        segment_days = base_days + (1 if index < remainder else 0)
        current_end = current_start + timedelta(days=segment_days - 1)
        generated.append(
            {
                'name': name,
                'start_date': current_start,
                'end_date': current_end,
                'term_type': config['term_type'],
            }
        )
        current_start = current_end + timedelta(days=1)
    return generated


def resolve_holiday_selection(key: str, start_date: date, end_date: date) -> list[dict[str, Any]]:
    entries = load_holiday_entries()
    entry = entries.get(key)
    if entry is None:
        raise ValueError(f'Unknown holiday preset: {key}')

    calculation_rule = entry.get('calculation_rule') or {}
    if calculation_rule.get('kind') == 'group':
        grouped_events: list[dict[str, Any]] = []
        for member_key in calculation_rule.get('members', []):
            grouped_events.extend(resolve_holiday_selection(member_key, start_date, end_date))
        return _deduplicate_events(grouped_events)

    events: list[dict[str, Any]] = []
    if entry.get('date'):
        raw_date = entry['date']
        resolved_date = date.fromisoformat(raw_date)
        if start_date <= resolved_date <= end_date:
            events.append(_build_event(entry, resolved_date))
    elif entry.get('date_range'):
        events.extend(_resolve_fixed_date_range(entry, start_date, end_date))
    elif calculation_rule:
        events.extend(_resolve_calculation_rule(entry, start_date, end_date))
    return _deduplicate_events(events)


def expand_selected_holidays(keys: list[str], start_date: date, end_date: date) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for key in keys:
        expanded.extend(resolve_holiday_selection(key, start_date, end_date))
    return _deduplicate_events(expanded)


def expand_break(name: str, start_date: date, end_date: date) -> list[dict[str, Any]]:
    event_type = CalendarEventType.closure
    events: list[dict[str, Any]] = []
    current = start_date
    while current <= end_date:
        events.append(
            {
                'date': current,
                'name': name,
                'event_type': event_type,
                'is_instructional_day': False,
                'notes': 'Generated from school year wizard custom break.',
            }
        )
        current += timedelta(days=1)
    return events


def _resolve_fixed_date_range(entry: dict[str, Any], start_date: date, end_date: date) -> list[dict[str, Any]]:
    rule = entry['date_range']
    events: list[dict[str, Any]] = []
    spans_year = bool(rule.get('spans_year'))
    start_month = int(rule['start']['month'])
    start_day = int(rule['start']['day'])
    end_month = int(rule['end']['month'])
    end_day = int(rule['end']['day'])
    year_range = range(start_date.year - 1, end_date.year + 1)
    for year in year_range:
        range_start = date(year, start_month, start_day)
        range_end = date(year + 1, end_month, end_day) if spans_year else date(year, end_month, end_day)
        current_start = max(range_start, start_date)
        current_end = min(range_end, end_date)
        if current_start > current_end:
            continue
        current = current_start
        while current <= current_end:
            events.append(_build_event(entry, current))
            current += timedelta(days=1)
    return events


def _resolve_calculation_rule(entry: dict[str, Any], start_date: date, end_date: date) -> list[dict[str, Any]]:
    rule = entry['calculation_rule']
    kind = rule['kind']
    events: list[dict[str, Any]] = []
    year_range = range(start_date.year, end_date.year + 1)

    if kind == 'fixed_date':
        for year in year_range:
            resolved = date(year, int(rule['month']), int(rule['day']))
            if start_date <= resolved <= end_date:
                events.append(_build_event(entry, resolved))
        return events

    if kind == 'nth_weekday_of_month':
        for year in year_range:
            resolved = _nth_weekday_of_month(year, int(rule['month']), int(rule['weekday']), int(rule['occurrence']))
            if start_date <= resolved <= end_date:
                events.append(_build_event(entry, resolved))
        return events

    if kind == 'last_weekday_of_month':
        for year in year_range:
            resolved = _last_weekday_of_month(year, int(rule['month']), int(rule['weekday']))
            if start_date <= resolved <= end_date:
                events.append(_build_event(entry, resolved))
        return events

    if kind == 'easter_offset':
        for year in year_range:
            resolved = _calculate_easter(year) + timedelta(days=int(rule['offset_days']))
            if start_date <= resolved <= end_date:
                events.append(_build_event(entry, resolved))
        return events

    if kind == 'easter_range':
        for year in year_range:
            easter = _calculate_easter(year)
            range_start = easter + timedelta(days=int(rule['start_offset_days']))
            range_end = easter + timedelta(days=int(rule['end_offset_days']))
            current = max(range_start, start_date)
            current_end = min(range_end, end_date)
            while current <= current_end:
                events.append(_build_event(entry, current))
                current += timedelta(days=1)
        return events

    if kind == 'nth_full_week_of_month':
        for year in year_range:
            week_start = _nth_full_week_of_month_start(
                year,
                int(rule['month']),
                int(rule['week_start_weekday']),
                int(rule['nth']),
            )
            if week_start is None:
                continue
            for offset in range(int(rule.get('length_days', 5))):
                resolved = week_start + timedelta(days=offset)
                if start_date <= resolved <= end_date:
                    events.append(_build_event(entry, resolved))
        return events

    if kind == 'nth_weekday_range':
        for year in year_range:
            period_start = _nth_weekday_of_month(year, int(rule['month']), int(rule['weekday']), int(rule['occurrence']))
            for offset in range(int(rule.get('length_days', 1))):
                resolved = period_start + timedelta(days=offset)
                if start_date <= resolved <= end_date:
                    events.append(_build_event(entry, resolved))
        return events

    raise ValueError(f'Unsupported holiday calculation rule: {kind}')


def _build_event(entry: dict[str, Any], event_date: date) -> dict[str, Any]:
    event_type = CalendarEventType.closure if entry['type'] == 'school_break' else CalendarEventType.holiday
    notes = f"Generated from school year wizard preset '{entry['key']}'."
    return {
        'date': event_date,
        'name': entry['name'],
        'event_type': event_type,
        'is_instructional_day': False,
        'notes': notes,
    }


def _build_holiday_preview(entry: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    preview = {
        'key': entry['key'],
        'name': entry['name'],
        'type': entry['type'],
        'recurring': bool(entry.get('recurring', False)),
        'calculation_rule': entry.get('calculation_rule'),
        'date': None,
        'date_range': None,
        'events': [{'date': item['date'], 'name': item['name']} for item in events],
    }
    if len(events) == 1:
        preview['date'] = events[0]['date']
    elif _is_contiguous_named_range(events):
        preview['date_range'] = {'start_date': events[0]['date'], 'end_date': events[-1]['date']}
    return preview


def _deduplicate_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[date, str], dict[str, Any]] = {}
    for event in sorted(events, key=lambda item: (item['date'], item['name'])):
        deduped[(event['date'], event['name'])] = event
    return list(deduped.values())


def _is_contiguous_named_range(events: list[dict[str, Any]]) -> bool:
    if len(events) < 2:
        return False
    names = {event['name'] for event in events}
    if len(names) != 1:
        return False
    ordered = sorted(events, key=lambda item: item['date'])
    previous = ordered[0]['date']
    for event in ordered[1:]:
        if event['date'] != previous + timedelta(days=1):
            return False
        previous = event['date']
    return True


def _nth_weekday_of_month(year: int, month: int, weekday: int, occurrence: int) -> date:
    first_day = date(year, month, 1)
    day_offset = (weekday - first_day.weekday()) % 7
    resolved = first_day + timedelta(days=day_offset + (occurrence - 1) * 7)
    if resolved.month != month:
        raise ValueError('Requested weekday occurrence does not exist in month')
    return resolved


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        cursor = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        cursor = date(year, month + 1, 1) - timedelta(days=1)
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    return cursor


def _nth_full_week_of_month_start(year: int, month: int, weekday: int, nth: int) -> date | None:
    first_of_month = date(year, month, 1)
    cursor = first_of_month + timedelta(days=(weekday - first_of_month.weekday()) % 7)
    full_weeks: list[date] = []
    while cursor.month == month:
        if (cursor + timedelta(days=6)).month == month:
            full_weeks.append(cursor)
        cursor += timedelta(days=7)
    if nth < 1 or nth > len(full_weeks):
        return None
    return full_weeks[nth - 1]


def _calculate_easter(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)
