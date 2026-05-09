"""schedule planner

Revision ID: 20260510_000100
Revises: 20260509_070500, 20260509_233900
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_000100'
down_revision: Union[str, Sequence[str], None] = ('20260509_070500', '20260509_233900')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops schedule_overrides, schedule_blocks, and schedules tables, plus the schedule_override_type enum.
- All schedule and block data will be permanently lost; export before rolling back.
- Tables are removed in reverse dependency order.
"""

schedule_override_type = postgresql.ENUM('cancel', 'reschedule', 'add', name='schedule_override_type', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    schedule_override_type.create(bind, checkfirst=True)

    op.create_table(
        'schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_schedules_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], name=op.f('fk_schedules_school_year_id_school_years'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_schedules_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_schedules')),
        sa.UniqueConstraint('student_id', 'school_year_id', 'name', name='uq_schedules_student_id_school_year_id_name'),
    )
    op.create_index(op.f('ix_schedules_id'), 'schedules', ['id'], unique=False)
    op.create_index(op.f('ix_schedules_family_id'), 'schedules', ['family_id'], unique=False)
    op.create_index(op.f('ix_schedules_student_id'), 'schedules', ['student_id'], unique=False)
    op.create_index(op.f('ix_schedules_school_year_id'), 'schedules', ['school_year_id'], unique=False)

    op.create_table(
        'schedule_blocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('location', sa.String(length=160), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], name=op.f('fk_schedule_blocks_schedule_id_schedules'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_schedule_blocks_subject_id_subjects'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_schedule_blocks')),
    )
    op.create_index(op.f('ix_schedule_blocks_id'), 'schedule_blocks', ['id'], unique=False)
    op.create_index(op.f('ix_schedule_blocks_schedule_id'), 'schedule_blocks', ['schedule_id'], unique=False)
    op.create_index(op.f('ix_schedule_blocks_subject_id'), 'schedule_blocks', ['subject_id'], unique=False)
    op.create_index(op.f('ix_schedule_blocks_day_of_week'), 'schedule_blocks', ['day_of_week'], unique=False)

    op.create_table(
        'schedule_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('original_block_id', sa.Integer(), nullable=True),
        sa.Column('override_type', schedule_override_type, nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=True),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['original_block_id'], ['schedule_blocks.id'], name=op.f('fk_schedule_overrides_original_block_id_schedule_blocks'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], name=op.f('fk_schedule_overrides_schedule_id_schedules'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_schedule_overrides_subject_id_subjects'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_schedule_overrides')),
    )
    op.create_index(op.f('ix_schedule_overrides_id'), 'schedule_overrides', ['id'], unique=False)
    op.create_index(op.f('ix_schedule_overrides_schedule_id'), 'schedule_overrides', ['schedule_id'], unique=False)
    op.create_index(op.f('ix_schedule_overrides_date'), 'schedule_overrides', ['date'], unique=False)
    op.create_index(op.f('ix_schedule_overrides_original_block_id'), 'schedule_overrides', ['original_block_id'], unique=False)
    op.create_index(op.f('ix_schedule_overrides_subject_id'), 'schedule_overrides', ['subject_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_schedule_overrides_subject_id'), table_name='schedule_overrides')
    op.drop_index(op.f('ix_schedule_overrides_original_block_id'), table_name='schedule_overrides')
    op.drop_index(op.f('ix_schedule_overrides_date'), table_name='schedule_overrides')
    op.drop_index(op.f('ix_schedule_overrides_schedule_id'), table_name='schedule_overrides')
    op.drop_index(op.f('ix_schedule_overrides_id'), table_name='schedule_overrides')
    op.drop_table('schedule_overrides')

    op.drop_index(op.f('ix_schedule_blocks_day_of_week'), table_name='schedule_blocks')
    op.drop_index(op.f('ix_schedule_blocks_subject_id'), table_name='schedule_blocks')
    op.drop_index(op.f('ix_schedule_blocks_schedule_id'), table_name='schedule_blocks')
    op.drop_index(op.f('ix_schedule_blocks_id'), table_name='schedule_blocks')
    op.drop_table('schedule_blocks')

    op.drop_index(op.f('ix_schedules_school_year_id'), table_name='schedules')
    op.drop_index(op.f('ix_schedules_student_id'), table_name='schedules')
    op.drop_index(op.f('ix_schedules_family_id'), table_name='schedules')
    op.drop_index(op.f('ix_schedules_id'), table_name='schedules')
    op.drop_table('schedules')

    bind = op.get_bind()
    schedule_override_type.drop(bind, checkfirst=True)
