"""performance indexes and search support

Revision ID: 20260510_003000
Revises: 20260510_002300
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_003000'
down_revision: Union[str, Sequence[str], None] = '20260510_002300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes the composite, partial, and PostgreSQL full-text indexes introduced for assignment, grade, submission, audit, notification, lesson-plan, pacing, and compliance queries.
- Schema tables and data remain intact; only performance-oriented indexes are removed.
"""


def upgrade() -> None:
    op.create_index('ix_assignments_family_subject_grading_period', 'assignments', ['family_id', 'subject_id', 'grading_period_id'], unique=False)
    op.create_index('ix_assignments_family_status_due_date', 'assignments', ['family_id', 'status', 'due_date'], unique=False)
    op.create_index(
        'ix_assignments_family_due_date_active',
        'assignments',
        ['family_id', 'due_date'],
        unique=False,
        sqlite_where=sa.text("status != 'graded'"),
        postgresql_where=sa.text("status <> 'graded'"),
    )
    op.create_index('ix_assignment_targets_student_status', 'assignment_targets', ['student_id', 'status'], unique=False)

    op.create_index('ix_grades_family_student_created_at', 'grades', ['family_id', 'student_id', 'created_at'], unique=False)
    op.create_index('ix_grades_family_student_submission', 'grades', ['family_id', 'student_id', 'submission_id'], unique=False)

    op.create_index(
        'ix_submissions_family_student_current_uploaded_at',
        'submissions',
        ['family_id', 'student_id', 'is_current', 'uploaded_at'],
        unique=False,
    )
    op.create_index('ix_submissions_assignment_student_current', 'submissions', ['assignment_id', 'student_id', 'is_current'], unique=False)
    op.create_index('ix_submissions_parent_current', 'submissions', ['parent_submission_id', 'is_current'], unique=False)

    op.create_index('ix_compliance_rules_family_state_active', 'compliance_rules', ['family_id', 'state_code', 'is_active'], unique=False)
    op.create_index('ix_compliance_rules_state_type_active', 'compliance_rules', ['state_code', 'rule_type', 'is_active'], unique=False)
    op.create_index(
        'ix_compliance_statuses_family_status_school_year',
        'compliance_statuses',
        ['family_id', 'status', 'school_year_id'],
        unique=False,
    )
    op.create_index('ix_compliance_statuses_student_status', 'compliance_statuses', ['student_id', 'status'], unique=False)

    op.create_index('ix_notifications_user_read_created_at', 'notifications', ['user_id', 'read', 'created_at'], unique=False)
    op.create_index('ix_notifications_family_user_read', 'notifications', ['family_id', 'user_id', 'read'], unique=False)
    op.create_index(
        'ix_notifications_unread_created_at',
        'notifications',
        ['user_id', 'created_at'],
        unique=False,
        sqlite_where=sa.text('read = 0'),
        postgresql_where=sa.text('read = false'),
    )

    op.create_index('ix_audit_events_family_action_timestamp', 'audit_events', ['family_id', 'action', 'timestamp'], unique=False)
    op.create_index('ix_audit_events_family_target_entity', 'audit_events', ['family_id', 'target_entity_type', 'target_entity_id'], unique=False)

    op.create_index(
        'ix_lesson_plans_family_student_status_target_date',
        'lesson_plans',
        ['family_id', 'student_id', 'status', 'target_date'],
        unique=False,
    )
    op.create_index('ix_lesson_plans_family_status_target_date', 'lesson_plans', ['family_id', 'status', 'target_date'], unique=False)
    op.create_index(
        'ix_lesson_plans_family_student_active_target_date',
        'lesson_plans',
        ['family_id', 'student_id', 'target_date'],
        unique=False,
        sqlite_where=sa.text("status NOT IN ('completed', 'skipped')"),
        postgresql_where=sa.text("status NOT IN ('completed', 'skipped')"),
    )
    op.create_index(
        'ix_pacing_targets_family_student_window',
        'pacing_targets',
        ['family_id', 'student_id', 'target_start_date', 'target_end_date'],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(
            """
            CREATE INDEX ix_assignments_search_document
            ON assignments
            USING GIN (
              to_tsvector(
                'simple',
                concat_ws(
                  ' ',
                  coalesce(title, ''),
                  coalesce(description, ''),
                  coalesce(rubric_description, '')
                )
              )
            )
            """
        )
        op.execute(
            """
            CREATE INDEX ix_audit_events_search_document
            ON audit_events
            USING GIN (
              to_tsvector(
                'simple',
                concat_ws(
                  ' ',
                  coalesce(target_entity_type, ''),
                  coalesce(target_entity_id, ''),
                  coalesce(cast(before_snapshot as text), ''),
                  coalesce(cast(after_snapshot as text), '')
                )
              )
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP INDEX IF EXISTS ix_audit_events_search_document')
        op.execute('DROP INDEX IF EXISTS ix_assignments_search_document')

    op.drop_index('ix_pacing_targets_family_student_window', table_name='pacing_targets')
    op.drop_index('ix_lesson_plans_family_student_active_target_date', table_name='lesson_plans')
    op.drop_index('ix_lesson_plans_family_status_target_date', table_name='lesson_plans')
    op.drop_index('ix_lesson_plans_family_student_status_target_date', table_name='lesson_plans')
    op.drop_index('ix_audit_events_family_target_entity', table_name='audit_events')
    op.drop_index('ix_audit_events_family_action_timestamp', table_name='audit_events')
    op.drop_index('ix_notifications_unread_created_at', table_name='notifications')
    op.drop_index('ix_notifications_family_user_read', table_name='notifications')
    op.drop_index('ix_notifications_user_read_created_at', table_name='notifications')
    op.drop_index('ix_compliance_statuses_student_status', table_name='compliance_statuses')
    op.drop_index('ix_compliance_statuses_family_status_school_year', table_name='compliance_statuses')
    op.drop_index('ix_compliance_rules_state_type_active', table_name='compliance_rules')
    op.drop_index('ix_compliance_rules_family_state_active', table_name='compliance_rules')
    op.drop_index('ix_submissions_parent_current', table_name='submissions')
    op.drop_index('ix_submissions_assignment_student_current', table_name='submissions')
    op.drop_index('ix_submissions_family_student_current_uploaded_at', table_name='submissions')
    op.drop_index('ix_grades_family_student_submission', table_name='grades')
    op.drop_index('ix_grades_family_student_created_at', table_name='grades')
    op.drop_index('ix_assignment_targets_student_status', table_name='assignment_targets')
    op.drop_index('ix_assignments_family_due_date_active', table_name='assignments')
    op.drop_index('ix_assignments_family_status_due_date', table_name='assignments')
    op.drop_index('ix_assignments_family_subject_grading_period', table_name='assignments')
