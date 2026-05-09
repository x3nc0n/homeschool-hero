"""lesson plans and pacing

Revision ID: 20260510_001500
Revises: 20260510_000100
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_001500'
down_revision: Union[str, Sequence[str], None] = '20260510_000100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

lesson_plan_status = sa.Enum(
    'planned',
    'in_progress',
    'completed',
    'skipped',
    'rescheduled',
    name='lesson_plan_status',
)


def upgrade() -> None:
    bind = op.get_bind()
    lesson_plan_status.create(bind, checkfirst=True)

    op.create_table(
        'lesson_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('curriculum_lesson_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('status', lesson_plan_status, nullable=False, server_default='planned'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['curriculum_lesson_id'], ['curriculum_lessons.id'], name=op.f('fk_lesson_plans_curriculum_lesson_id_curriculum_lessons'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_lesson_plans_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], name=op.f('fk_lesson_plans_school_year_id_school_years'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_lesson_plans_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lesson_plans')),
        sa.UniqueConstraint('student_id', 'curriculum_lesson_id', name='uq_lesson_plans_student_id_curriculum_lesson_id'),
    )
    op.create_index(op.f('ix_lesson_plans_id'), 'lesson_plans', ['id'], unique=False)
    op.create_index(op.f('ix_lesson_plans_family_id'), 'lesson_plans', ['family_id'], unique=False)
    op.create_index(op.f('ix_lesson_plans_curriculum_lesson_id'), 'lesson_plans', ['curriculum_lesson_id'], unique=False)
    op.create_index(op.f('ix_lesson_plans_student_id'), 'lesson_plans', ['student_id'], unique=False)
    op.create_index(op.f('ix_lesson_plans_school_year_id'), 'lesson_plans', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_lesson_plans_target_date'), 'lesson_plans', ['target_date'], unique=False)
    op.create_index(op.f('ix_lesson_plans_status'), 'lesson_plans', ['status'], unique=False)

    op.create_table(
        'pacing_targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('curriculum_unit_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('target_start_date', sa.Date(), nullable=False),
        sa.Column('target_end_date', sa.Date(), nullable=False),
        sa.Column('actual_completion_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['curriculum_unit_id'], ['curriculum_units.id'], name=op.f('fk_pacing_targets_curriculum_unit_id_curriculum_units'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_pacing_targets_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_pacing_targets_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pacing_targets')),
        sa.UniqueConstraint('student_id', 'curriculum_unit_id', name='uq_pacing_targets_student_id_curriculum_unit_id'),
    )
    op.create_index(op.f('ix_pacing_targets_id'), 'pacing_targets', ['id'], unique=False)
    op.create_index(op.f('ix_pacing_targets_family_id'), 'pacing_targets', ['family_id'], unique=False)
    op.create_index(op.f('ix_pacing_targets_curriculum_unit_id'), 'pacing_targets', ['curriculum_unit_id'], unique=False)
    op.create_index(op.f('ix_pacing_targets_student_id'), 'pacing_targets', ['student_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pacing_targets_student_id'), table_name='pacing_targets')
    op.drop_index(op.f('ix_pacing_targets_curriculum_unit_id'), table_name='pacing_targets')
    op.drop_index(op.f('ix_pacing_targets_family_id'), table_name='pacing_targets')
    op.drop_index(op.f('ix_pacing_targets_id'), table_name='pacing_targets')
    op.drop_table('pacing_targets')

    op.drop_index(op.f('ix_lesson_plans_status'), table_name='lesson_plans')
    op.drop_index(op.f('ix_lesson_plans_target_date'), table_name='lesson_plans')
    op.drop_index(op.f('ix_lesson_plans_school_year_id'), table_name='lesson_plans')
    op.drop_index(op.f('ix_lesson_plans_student_id'), table_name='lesson_plans')
    op.drop_index(op.f('ix_lesson_plans_curriculum_lesson_id'), table_name='lesson_plans')
    op.drop_index(op.f('ix_lesson_plans_family_id'), table_name='lesson_plans')
    op.drop_index(op.f('ix_lesson_plans_id'), table_name='lesson_plans')
    op.drop_table('lesson_plans')

    bind = op.get_bind()
    lesson_plan_status.drop(bind, checkfirst=True)
