from __future__ import annotations

from pathlib import Path
from typing import Any

API_PREFIX = '/api'

AUTH = {
    'bootstrap': f'{API_PREFIX}/auth/bootstrap',
    'register': f'{API_PREFIX}/auth/register',
    'login': f'{API_PREFIX}/auth/login',
    'logout': f'{API_PREFIX}/auth/logout',
    'me': f'{API_PREFIX}/auth/me',
    'oidc_login': f'{API_PREFIX}/auth/oidc/login',
    'oidc_callback': f'{API_PREFIX}/auth/oidc/callback',
    'saml_login': f'{API_PREFIX}/auth/saml/login',
    'saml_metadata': f'{API_PREFIX}/auth/saml/metadata',
    'saml_acs': f'{API_PREFIX}/auth/saml/acs',
}

INVITATIONS = {
    'collection': f'{API_PREFIX}/invitations',
    'accept': f'{API_PREFIX}/invitations/{{invitation_id}}/accept',
    'revoke': f'{API_PREFIX}/invitations/{{invitation_id}}/revoke',
}

AUDIT = {
    'collection': f'{API_PREFIX}/audit',
}

SEARCH = {
    'collection': f'{API_PREFIX}/search',
}

STUDENTS = {
    'collection': f'{API_PREFIX}/students',
    'detail': f'{API_PREFIX}/students/{{student_id}}',
}

SUBJECTS = {
    'collection': f'{API_PREFIX}/subjects',
    'detail': f'{API_PREFIX}/subjects/{{subject_id}}',
}

ASSIGNMENTS = {
    'collection': f'{API_PREFIX}/assignments',
    'detail': f'{API_PREFIX}/assignments/{{assignment_id}}',
    'status': f'{API_PREFIX}/assignments/{{assignment_id}}/status',
}

SUBMISSIONS = {
    'collection': f'{API_PREFIX}/submissions',
    'upload': f'{API_PREFIX}/submissions',
    'detail': f'{API_PREFIX}/submissions/{{submission_id}}',
}

PORTFOLIO = {
    'entries': f'{API_PREFIX}/portfolio/{{student_id}}/entries',
    'entry_collection': f'{API_PREFIX}/portfolio/entries',
    'entry_detail': f'{API_PREFIX}/portfolio/entries/{{entry_id}}',
    'entry_attach': f'{API_PREFIX}/portfolio/entries/{{entry_id}}/attach',
    'collections': f'{API_PREFIX}/portfolio/collections',
    'collection_detail': f'{API_PREFIX}/portfolio/collections/{{collection_id}}',
    'collection_share': f'{API_PREFIX}/portfolio/collections/{{collection_id}}/share',
    'public_collection': f'{API_PREFIX}/portfolio/public/{{share_token}}',
}

GRADES = {
    'collection': f'{API_PREFIX}/grades',
    'detail': f'{API_PREFIX}/grades/{{grade_id}}',
    'history': f'{API_PREFIX}/grades/history',
    'student_averages': f'{API_PREFIX}/grades/averages/student/{{student_id}}',
    'subject_averages': f'{API_PREFIX}/grades/averages/subject/{{subject_id}}',
}

GRADEBOOK = {
    'detail': f'{API_PREFIX}/gradebook/{{student_id}}',
    'summary': f'{API_PREFIX}/gradebook/{{student_id}}/summary',
    'trends': f'{API_PREFIX}/gradebook/{{student_id}}/trends',
    'categories': f'{API_PREFIX}/gradebook/categories',
    'scales': f'{API_PREFIX}/gradebook/scales',
    'calculate': f'{API_PREFIX}/gradebook/calculate',
}

QUIZZES = {
    'collection': f'{API_PREFIX}/quizzes',
    'detail': f'{API_PREFIX}/quizzes/{{quiz_id}}',
    'attempts': f'{API_PREFIX}/quizzes/{{quiz_id}}/attempts',
    'attempts_list': f'{API_PREFIX}/quizzes/{{quiz_id}}/attempts',
}

GRADING = {
    'review_queue': f'{API_PREFIX}/grading/review-queue',
    'approve': f'{API_PREFIX}/grading/review-queue/{{job_id}}/approve',
    'reject': f'{API_PREFIX}/grading/review-queue/{{job_id}}/reject',
}

NOTIFICATIONS = {
    'collection': f'{API_PREFIX}/notifications',
    'detail_read': f'{API_PREFIX}/notifications/{{notification_id}}/read',
    'read_all': f'{API_PREFIX}/notifications/read-all',
    'preferences': f'{API_PREFIX}/notifications/preferences',
}

CALENDAR = {
    'school_years': f'{API_PREFIX}/calendar/school-years',
    'school_year_detail': f'{API_PREFIX}/calendar/school-years/{{school_year_id}}',
    'terms': f'{API_PREFIX}/calendar/terms',
    'term_detail': f'{API_PREFIX}/calendar/terms/{{term_id}}',
    'grading_periods': f'{API_PREFIX}/calendar/grading-periods',
    'grading_period_detail': f'{API_PREFIX}/calendar/grading-periods/{{grading_period_id}}',
    'events': f'{API_PREFIX}/calendar/events',
    'event_detail': f'{API_PREFIX}/calendar/events/{{event_id}}',
    'active': f'{API_PREFIX}/calendar/active',
    'days': f'{API_PREFIX}/calendar/{{school_year_id}}/days',
}

ATTENDANCE = {
    'collection': f'{API_PREFIX}/attendance',
    'daily': f'{API_PREFIX}/attendance/daily',
    'hours': f'{API_PREFIX}/attendance/hours',
    'summary': f'{API_PREFIX}/attendance/summary',
    'excuses': f'{API_PREFIX}/attendance/excuses',
    'excuse_approve': f'{API_PREFIX}/attendance/excuses/{{excuse_id}}/approve',
}

REPORT_CARDS = {
    'collection': f'{API_PREFIX}/report-cards',
    'generate': f'{API_PREFIX}/report-cards/generate',
    'detail': f'{API_PREFIX}/report-cards/{{report_card_id}}',
    'finalize': f'{API_PREFIX}/report-cards/{{report_card_id}}/finalize',
    'pdf': f'{API_PREFIX}/report-cards/{{report_card_id}}/pdf',
}

SCHEDULE = {
    'collection': f'{API_PREFIX}/schedule',
    'detail': f'{API_PREFIX}/schedule/{{schedule_id}}',
    'blocks': f'{API_PREFIX}/schedule/{{schedule_id}}/blocks',
    'block_detail': f'{API_PREFIX}/schedule/blocks/{{block_id}}',
    'override_create': f'{API_PREFIX}/schedule/override',
    'override_detail': f'{API_PREFIX}/schedule/override/{{override_id}}',
    'agenda': f'{API_PREFIX}/schedule/{{student_id}}/agenda',
    'week': f'{API_PREFIX}/schedule/{{student_id}}/week',
}

LESSON_PLANS = {
    'collection': f'{API_PREFIX}/lesson-plans',
    'detail': f'{API_PREFIX}/lesson-plans/{{lesson_plan_id}}',
    'generate': f'{API_PREFIX}/lesson-plans/generate',
    'bulk_status': f'{API_PREFIX}/lesson-plans/bulk-status',
    'generate_assignments': f'{API_PREFIX}/lesson-plans/generate-assignments',
    'pacing': f'{API_PREFIX}/pacing/{{student_id}}',
    'pacing_targets': f'{API_PREFIX}/pacing-targets',
    'pacing_target_detail': f'{API_PREFIX}/pacing-targets/{{pacing_target_id}}',
}

CURRICULUM = {
    'packages': f'{API_PREFIX}/curriculum/packages',
    'package_detail': f'{API_PREFIX}/curriculum/packages/{{package_id}}',
    'package_clone': f'{API_PREFIX}/curriculum/packages/{{package_id}}/clone',
    'units': f'{API_PREFIX}/curriculum/units',
    'unit_detail': f'{API_PREFIX}/curriculum/units/{{unit_id}}',
    'lessons': f'{API_PREFIX}/curriculum/lessons',
    'lesson_detail': f'{API_PREFIX}/curriculum/lessons/{{lesson_id}}',
    'lesson_resource_detail': f'{API_PREFIX}/curriculum/lessons/{{lesson_id}}/resources/{{resource_id}}',
}

RESOURCES = {
    'collection': f'{API_PREFIX}/resources',
    'detail': f'{API_PREFIX}/resources/{{resource_id}}',
}

IMPORTS = {
    'collection': f'{API_PREFIX}/imports',
    'upload': f'{API_PREFIX}/imports/upload',
    'detail': f'{API_PREFIX}/imports/{{job_id}}/status',
    'validate': f'{API_PREFIX}/imports/{{job_id}}/validate',
    'execute': f'{API_PREFIX}/imports/{{job_id}}/execute',
    'template': f'{API_PREFIX}/imports/templates/{{entity_type}}',
}

SERVICE_CANDIDATES = {
    'ocr': ('extract_text_from_image', 'extract_text', 'perform_ocr'),
    'ai_grade': ('grade_submission_text', 'grade_text', 'grade_submission', 'grade_ocr_text'),
    'worker': ('process_grading_job', 'process_job', 'handle_job'),
}

VALIDATION_STATUS_CODES = {400, 422}

UPLOADS_DIR = Path(__file__).resolve().parents[1] / '.pytest-state' / 'uploads-test'


def bootstrap_payload(
    *,
    family_name: str = 'Test Family',
    display_name: str = 'Parent User',
    email: str = 'owner@example.com',
    password: str = 'strongpass123',
) -> dict[str, Any]:
    return {
        'family_name': family_name,
        'display_name': display_name,
        'email': email,
        'password': password,
        'timezone': 'UTC',
        'grading_scale': 'letter',
    }


def student_payload(name: str = 'Ada Lovelace') -> dict[str, Any]:
    return {'name': name}


def subject_payload(name: str = 'Math', color: str = '#2563eb') -> dict[str, Any]:
    return {'name': name, 'color': color}


def assignment_payload(subject_id: int | str) -> dict[str, Any]:
    return {
        'title': 'Fractions Worksheet',
        'subject_id': subject_id,
        'description': 'Complete problems 1-10 using the answer key.',
        'due_date': '2026-05-15',
        'status': 'pending',
    }


def grade_payload(submission_id: int | str, student_id: int | str) -> dict[str, Any]:
    return {
        'submission_id': submission_id,
        'student_id': student_id,
        'score': 88,
        'max_score': 100,
        'letter_grade': 'B+',
        'notes': 'Strong work with one arithmetic mistake.',
        'graded_by': 'human',
    }


def portfolio_entry_payload(student_id: int | str, **overrides: Any) -> dict[str, Any]:
    payload = {
        'student_id': student_id,
        'entry_type': 'journal',
        'title': 'Field trip reflection',
        'description': '## Highlights\nWe visited the science museum and wrote observations.',
        'date': '2026-05-08',
        'tags': ['science', 'museum'],
    }
    payload.update(overrides)
    return payload


def portfolio_collection_payload(student_id: int | str, entry_ids: list[int | str], **overrides: Any) -> dict[str, Any]:
    payload = {
        'student_id': student_id,
        'name': 'Spring showcase',
        'description': 'A curated set of work for extended family.',
        'entry_ids': entry_ids,
        'is_public': False,
    }
    payload.update(overrides)
    return payload


def quiz_payload(subject_id: int | str) -> dict[str, Any]:
    return {
        'title': 'Fractions Check-In',
        'subject_id': subject_id,
        'questions': [
            {
                'type': 'multiple_choice',
                'prompt': 'What is 1/2 + 1/4?',
                'options': ['1/4', '1/2', '3/4', '1'],
                'correct_answer': '3/4',
            },
            {
                'type': 'short_answer',
                'prompt': 'Simplify 6/8.',
                'correct_answer': '3/4',
            },
        ],
    }


def quiz_attempt_payload(student_id: int | str) -> dict[str, Any]:
    return {
        'student_id': student_id,
        'answers': ['3/4', '3/4'],
    }


def school_year_payload(
    *,
    name: str = '2025-2026',
    start_date: str = '2025-08-18',
    end_date: str = '2026-05-29',
    is_active: bool = True,
) -> dict[str, Any]:
    return {
        'name': name,
        'start_date': start_date,
        'end_date': end_date,
        'is_active': is_active,
    }


def term_payload(
    school_year_id: int | str,
    *,
    name: str = 'Fall Semester',
    start_date: str = '2025-08-18',
    end_date: str = '2025-12-19',
    term_type: str = 'semester',
) -> dict[str, Any]:
    return {
        'school_year_id': school_year_id,
        'name': name,
        'start_date': start_date,
        'end_date': end_date,
        'term_type': term_type,
    }


def grading_period_payload(
    term_id: int | str,
    *,
    name: str = 'Q1',
    start_date: str = '2025-08-18',
    end_date: str = '2025-10-17',
) -> dict[str, Any]:
    return {
        'term_id': term_id,
        'name': name,
        'start_date': start_date,
        'end_date': end_date,
    }


def calendar_event_payload(
    school_year_id: int | str,
    *,
    date: str = '2025-11-27',
    event_type: str = 'holiday',
    name: str = 'Thanksgiving Break',
    is_instructional_day: bool = False,
    notes: str | None = None,
) -> dict[str, Any]:
    payload = {
        'school_year_id': school_year_id,
        'date': date,
        'event_type': event_type,
        'name': name,
        'is_instructional_day': is_instructional_day,
    }
    if notes is not None:
        payload['notes'] = notes
    return payload


def schedule_payload(
    student_id: int | str,
    school_year_id: int | str,
    *,
    name: str = 'Default Schedule',
) -> dict[str, Any]:
    return {
        'student_id': student_id,
        'school_year_id': school_year_id,
        'name': name,
    }


def attendance_daily_payload(
    attendance_date: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        'date': attendance_date,
        'records': records,
    }


def attendance_record_payload(
    student_id: int | str,
    *,
    status: str = 'present',
    instructional_hours: str | float | None = '5.50',
    check_in_time: str | None = None,
    check_out_time: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'student_id': student_id,
        'status': status,
    }
    if instructional_hours is not None:
        payload['instructional_hours'] = instructional_hours
    if check_in_time is not None:
        payload['check_in_time'] = check_in_time
    if check_out_time is not None:
        payload['check_out_time'] = check_out_time
    if notes is not None:
        payload['notes'] = notes
    return payload


def attendance_hours_payload(
    student_id: int | str,
    *,
    attendance_date: str = '2025-09-10',
    instructional_hours: str | float = '4.25',
    check_in_time: str | None = '09:00:00',
    check_out_time: str | None = '13:15:00',
    notes: str | None = 'Independent reading and math drills',
) -> dict[str, Any]:
    return {
        'student_id': student_id,
        'date': attendance_date,
        'instructional_hours': instructional_hours,
        'check_in_time': check_in_time,
        'check_out_time': check_out_time,
        'notes': notes,
    }


def schedule_block_payload(
    subject_id: int | str,
    *,
    day_of_week: int = 0,
    start_time: str = '09:00',
    end_time: str = '10:00',
    location: str | None = 'Dining Room',
    notes: str | None = 'Warm-up and lesson',
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'subject_id': subject_id,
        'day_of_week': day_of_week,
        'start_time': start_time,
        'end_time': end_time,
    }
    if location is not None:
        payload['location'] = location
    if notes is not None:
        payload['notes'] = notes
    return payload


def schedule_override_payload(
    schedule_id: int | str,
    *,
    date: str = '2025-09-15',
    override_type: str = 'add',
    original_block_id: int | str | None = None,
    subject_id: int | str | None = None,
    start_time: str | None = '13:00',
    end_time: str | None = '14:00',
    reason: str = 'Field trip',
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'schedule_id': schedule_id,
        'date': date,
        'override_type': override_type,
        'reason': reason,
    }
    if original_block_id is not None:
        payload['original_block_id'] = original_block_id
    if subject_id is not None:
        payload['subject_id'] = subject_id
    if start_time is not None:
        payload['start_time'] = start_time
    if end_time is not None:
        payload['end_time'] = end_time
    return payload


def curriculum_package_payload(
    school_year_id: int | str,
    subject_id: int | str,
    *,
    name: str = 'Core Math 2025',
    description: str | None = 'Daily spiral review and mastery lessons.',
) -> dict[str, Any]:
    payload = {
        'school_year_id': school_year_id,
        'subject_id': subject_id,
        'name': name,
    }
    if description is not None:
        payload['description'] = description
    return payload


def curriculum_unit_payload(
    package_id: int | str,
    *,
    name: str = 'Unit 1: Number Sense',
    description: str | None = 'Build number fluency.',
    sequence_order: int = 1,
    standards_tags: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        'package_id': package_id,
        'name': name,
        'sequence_order': sequence_order,
        'standards_tags': standards_tags or ['MATH-NS.1'],
    }
    if description is not None:
        payload['description'] = description
    return payload


def curriculum_lesson_payload(
    unit_id: int | str,
    *,
    name: str = 'Lesson 1: Place value warm-up',
    description: str | None = 'Use base-ten blocks and quick checks.',
    sequence_order: int = 1,
    estimated_duration_minutes: int | None = 45,
    standards_tags: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        'unit_id': unit_id,
        'name': name,
        'sequence_order': sequence_order,
        'standards_tags': standards_tags or ['MATH-NS.1'],
    }
    if description is not None:
        payload['description'] = description
    if estimated_duration_minutes is not None:
        payload['estimated_duration_minutes'] = estimated_duration_minutes
    return payload


def resource_payload(
    *,
    name: str = 'Base ten blocks',
    description: str | None = 'Hands-on manipulative guide.',
    resource_type: str = 'link',
    url: str | None = 'https://example.com/base-ten',
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        'name': name,
        'resource_type': resource_type,
        'tags': tags or ['manipulative', 'math'],
        'metadata': metadata or {'format': 'pdf'},
    }
    if description is not None:
        payload['description'] = description
    if url is not None:
        payload['url'] = url
    return payload


def schedule_payload(
    student_id: int | str,
    school_year_id: int | str,
    *,
    name: str = 'Default Schedule',
) -> dict[str, Any]:
    return {
        'student_id': student_id,
        'school_year_id': school_year_id,
        'name': name,
    }


def schedule_block_payload(
    subject_id: int | str,
    *,
    day_of_week: int = 0,
    start_time: str = '09:00',
    end_time: str = '10:00',
    location: str | None = 'Dining Room',
    notes: str | None = 'Warm-up and lesson',
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'subject_id': subject_id,
        'day_of_week': day_of_week,
        'start_time': start_time,
        'end_time': end_time,
    }
    if location is not None:
        payload['location'] = location
    if notes is not None:
        payload['notes'] = notes
    return payload


def schedule_override_payload(
    schedule_id: int | str,
    *,
    date: str = '2025-09-15',
    override_type: str = 'add',
    original_block_id: int | str | None = None,
    subject_id: int | str | None = None,
    start_time: str | None = '13:00',
    end_time: str | None = '14:00',
    reason: str = 'Field trip',
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'schedule_id': schedule_id,
        'date': date,
        'override_type': override_type,
        'reason': reason,
    }
    if original_block_id is not None:
        payload['original_block_id'] = original_block_id
    if subject_id is not None:
        payload['subject_id'] = subject_id
    if start_time is not None:
        payload['start_time'] = start_time
    if end_time is not None:
        payload['end_time'] = end_time
    return payload
