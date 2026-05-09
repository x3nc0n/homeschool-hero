"""assignment domain upgrade

Revision ID: 20260509_070500
Revises: 20260509_003000
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260509_070500'
down_revision: Union[str, Sequence[str], None] = '20260509_003000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes assignment_targets plus assignment category/weight/rubric/history metadata columns.
- Export assignment target rows and JSON history first if operators need to preserve per-student assignment tracking.
- lesson_plan_id is a reserved nullable link for future AM-04 work and will be dropped on downgrade.
"""

assignment_category = sa.Enum('homework', 'quiz', 'test', 'project', 'other', name='assignment_category')
assignment_recurrence = sa.Enum('none', 'daily', 'weekly', name='assignment_recurrence')
assignment_target_status = sa.Enum('assigned', 'submitted', 'graded', 'excused', name='assignment_target_status')


def upgrade() -> None:
    bind = op.get_bind()
    assignment_category.create(bind, checkfirst=True)
    assignment_recurrence.create(bind, checkfirst=True)
    assignment_target_status.create(bind, checkfirst=True)

    with op.batch_alter_table('assignments') as batch:
        batch.add_column(
            sa.Column('category', assignment_category, nullable=False, server_default='homework')
        )
        batch.add_column(sa.Column('grading_period_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('weight', sa.Float(), nullable=False, server_default='1'))
        batch.add_column(sa.Column('max_score', sa.Float(), nullable=False, server_default='100'))
        batch.add_column(
            sa.Column('recurrence', assignment_recurrence, nullable=False, server_default='none')
        )
        batch.add_column(sa.Column('recurrence_end_date', sa.Date(), nullable=True))
        batch.add_column(sa.Column('rubric_description', sa.Text(), nullable=True))
        batch.add_column(sa.Column('attachments', sa.JSON(), nullable=False, server_default='[]'))
        batch.add_column(sa.Column('lesson_plan_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('status_history', sa.JSON(), nullable=False, server_default='[]'))
        batch.create_index(op.f('ix_assignments_grading_period_id'), ['grading_period_id'], unique=False)
        batch.create_index(op.f('ix_assignments_lesson_plan_id'), ['lesson_plan_id'], unique=False)
        batch.create_foreign_key(
            op.f('fk_assignments_grading_period_id_grading_periods'),
            'grading_periods',
            ['grading_period_id'],
            ['id'],
            ondelete='SET NULL',
        )

    op.create_table(
        'assignment_targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', assignment_target_status, nullable=False, server_default='assigned'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['assignment_id'],
            ['assignments.id'],
            name=op.f('fk_assignment_targets_assignment_id_assignments'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['student_id'],
            ['students.id'],
            name=op.f('fk_assignment_targets_student_id_students'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_assignment_targets')),
        sa.UniqueConstraint('assignment_id', 'student_id', name='uq_assignment_targets_assignment_id_student_id'),
    )
    op.create_index(op.f('ix_assignment_targets_id'), 'assignment_targets', ['id'], unique=False)
    op.create_index(op.f('ix_assignment_targets_assignment_id'), 'assignment_targets', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_assignment_targets_student_id'), 'assignment_targets', ['student_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_assignment_targets_student_id'), table_name='assignment_targets')
    op.drop_index(op.f('ix_assignment_targets_assignment_id'), table_name='assignment_targets')
    op.drop_index(op.f('ix_assignment_targets_id'), table_name='assignment_targets')
    op.drop_table('assignment_targets')

    with op.batch_alter_table('assignments') as batch:
        batch.drop_constraint(op.f('fk_assignments_grading_period_id_grading_periods'), type_='foreignkey')
        batch.drop_index(op.f('ix_assignments_lesson_plan_id'))
        batch.drop_index(op.f('ix_assignments_grading_period_id'))
        batch.drop_column('status_history')
        batch.drop_column('lesson_plan_id')
        batch.drop_column('attachments')
        batch.drop_column('rubric_description')
        batch.drop_column('recurrence_end_date')
        batch.drop_column('recurrence')
        batch.drop_column('max_score')
        batch.drop_column('weight')
        batch.drop_column('grading_period_id')
        batch.drop_column('category')

    bind = op.get_bind()
    assignment_target_status.drop(bind, checkfirst=True)
    assignment_recurrence.drop(bind, checkfirst=True)
    assignment_category.drop(bind, checkfirst=True)
