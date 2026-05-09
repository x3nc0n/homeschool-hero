from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.models import (
    ComplianceRuleType,
    ComplianceState,
    CurriculumLesson,
    CurriculumPackage,
    CurriculumUnit,
    GradeScale,
    LessonPlan,
    LessonPlanStatus,
    PacingTarget,
    SchoolYear,
    SubjectGradingMode,
)
from backend.routers.lesson_plans import _build_pacing_status
from backend.services.compliance import _derive_status, _school_year_progress
from backend.services.gradebook import build_default_grade_categories, map_percent_to_grade


def test_gradebook_maps_boundaries_and_default_categories():
    scale = GradeScale(
        family_id=1,
        name='Default',
        ranges=[
            {'letter': 'A', 'min': 90, 'max': 100, 'gpa_points': 4.0},
            {'letter': 'B', 'min': 80, 'max': 89.99, 'gpa_points': 3.0},
            {'letter': 'C', 'min': 70, 'max': 79.99, 'gpa_points': 2.0},
        ],
        is_default=True,
    )

    assert map_percent_to_grade(scale, 90.0) == ('A', 4.0)
    assert map_percent_to_grade(scale, 89.99) == ('B', 3.0)
    assert map_percent_to_grade(scale, None) == (None, None)

    categories = build_default_grade_categories(['quiz', 'extra_credit', 'homework'])
    assert [item['name'] for item in categories] == ['homework', 'quiz', 'extra_credit']
    assert sum(item['weight'] for item in categories if item['name'] != 'extra_credit') == 1.0
    assert next(item for item in categories if item['name'] == 'extra_credit')['weight'] == 0.0


def test_compliance_progress_and_status_thresholds():
    school_year = SchoolYear(
        family_id=1,
        name='2026-2027',
        start_date=date(2026, 8, 1),
        end_date=date(2027, 5, 31),
    )

    assert _school_year_progress(school_year, today=date(2026, 8, 1)) == 0.0
    assert _school_year_progress(school_year, today=date(2026, 12, 31)) > 0.4
    assert _school_year_progress(school_year, today=date(2027, 6, 15)) == 1.0

    assert _derive_status(
        rule_type=ComplianceRuleType.attendance_days,
        current_value=Decimal('30'),
        required_value=Decimal('180'),
        school_year_progress=0.3,
    ) == ComplianceState.warning
    assert _derive_status(
        rule_type=ComplianceRuleType.assessment_required,
        current_value=Decimal('0'),
        required_value=Decimal('1'),
        school_year_progress=0.85,
    ) == ComplianceState.warning
    assert _derive_status(
        rule_type=ComplianceRuleType.subjects_required,
        current_value=Decimal('3'),
        required_value=Decimal('5'),
        school_year_progress=0.5,
        missing_items=['grammar', 'citizenship'],
    ) == ComplianceState.warning
    assert _derive_status(
        rule_type=ComplianceRuleType.attendance_days,
        current_value=Decimal('170'),
        required_value=Decimal('180'),
        school_year_progress=1.0,
    ) == ComplianceState.non_compliant


def test_pacing_status_marks_ahead_and_behind_correctly():
    package = CurriculumPackage(
        id=10,
        family_id=1,
        school_year_id=1,
        name='Math Core',
        subject_id=1,
        created_by_user_id=1,
    )
    unit = CurriculumUnit(
        id=20,
        package_id=10,
        package=package,
        name='Fractions',
        sequence_order=1,
        standards_tags=[],
    )
    unit.lessons = [
        CurriculumLesson(id=30, unit_id=20, name='Lesson 1', sequence_order=1, standards_tags=[]),
        CurriculumLesson(id=31, unit_id=20, name='Lesson 2', sequence_order=2, standards_tags=[]),
    ]

    pacing_target = PacingTarget(
        id=40,
        family_id=1,
        curriculum_unit_id=20,
        student_id=1,
        target_start_date=date(2026, 9, 1),
        target_end_date=date(2026, 9, 10),
    )
    pacing_target.curriculum_unit = unit

    completed_plans = [
        LessonPlan(
            family_id=1,
            curriculum_lesson_id=30,
            student_id=1,
            school_year_id=1,
            target_date=date(2026, 9, 2),
            status=LessonPlanStatus.completed,
        ),
        LessonPlan(
            family_id=1,
            curriculum_lesson_id=31,
            student_id=1,
            school_year_id=1,
            target_date=date(2026, 9, 3),
            status=LessonPlanStatus.completed,
        ),
    ]
    pacing_target.actual_completion_date = date(2026, 9, 4)
    ahead = _build_pacing_status(pacing_target, completed_plans, today=date(2026, 9, 5))
    assert ahead.status == 'ahead'
    assert ahead.completed_lessons == 2

    pacing_target.actual_completion_date = None
    behind = _build_pacing_status(
        pacing_target,
        [
            LessonPlan(
                family_id=1,
                curriculum_lesson_id=30,
                student_id=1,
                school_year_id=1,
                target_date=date(2026, 9, 2),
                status=LessonPlanStatus.planned,
            )
        ],
        today=date(2026, 9, 15),
    )
    assert behind.status == 'behind'
    assert behind.remaining_lessons == 2


def test_points_grading_mode_is_available_for_gradebook_calculations():
    assert SubjectGradingMode.points.value == 'points'
    assert SubjectGradingMode.percentage.value == 'percentage'
