"""curriculum import phase 1

Revision ID: 20260612_174845
Revises: 20260510_006000
Create Date: 2026-06-12T17:48:45.564-05:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = '20260612_174845'
down_revision: Union[str, Sequence[str], None] = '20260510_006000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() removes imported curriculum source documents, nested subjects/units/lessons,
  activation links, and saved activation summaries.
- Activated curriculum packages, internal lessons, resources, and assignments created before
  downgrade are intentionally preserved because they become user-owned planning data.
"""


def upgrade() -> None:
    op.create_table(
        'imported_curricula',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=120), server_default='manual', nullable=False),
        sa.Column('schema_version', sa.String(length=32), server_default='1.0', nullable=False),
        sa.Column('grade_levels', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('standards_alignment', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('estimated_hours', sa.Integer(), nullable=True),
        sa.Column('prerequisites', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('payload', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('last_activation_summary', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('last_activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'],
            ['users.id'],
            name=op.f('fk_imported_curricula_created_by_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['family_id'],
            ['families.id'],
            name=op.f('fk_imported_curricula_family_id_families'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_imported_curricula')),
        sa.UniqueConstraint('family_id', 'name', name='uq_imported_curricula_family_name'),
    )
    op.create_index(op.f('ix_imported_curricula_id'), 'imported_curricula', ['id'], unique=False)
    op.create_index(op.f('ix_imported_curricula_family_id'), 'imported_curricula', ['family_id'], unique=False)
    op.create_index(
        op.f('ix_imported_curricula_created_by_user_id'),
        'imported_curricula',
        ['created_by_user_id'],
        unique=False,
    )

    op.create_table(
        'imported_curriculum_subjects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('curriculum_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sequence_order', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('grade_levels', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('standards_alignment', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('estimated_hours', sa.Integer(), nullable=True),
        sa.Column('prerequisites', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('activated_subject_id', sa.Integer(), nullable=True),
        sa.Column('activated_package_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['activated_package_id'],
            ['curriculum_packages.id'],
            name=op.f('fk_imported_curriculum_subjects_activated_package_id_curriculum_packages'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['activated_subject_id'],
            ['subjects.id'],
            name=op.f('fk_imported_curriculum_subjects_activated_subject_id_subjects'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['curriculum_id'],
            ['imported_curricula.id'],
            name=op.f('fk_imported_curriculum_subjects_curriculum_id_imported_curricula'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_imported_curriculum_subjects')),
        sa.UniqueConstraint('curriculum_id', 'name', name='uq_imported_curriculum_subjects_curriculum_name'),
    )
    op.create_index(op.f('ix_imported_curriculum_subjects_id'), 'imported_curriculum_subjects', ['id'], unique=False)
    op.create_index(
        op.f('ix_imported_curriculum_subjects_curriculum_id'),
        'imported_curriculum_subjects',
        ['curriculum_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_imported_curriculum_subjects_activated_subject_id'),
        'imported_curriculum_subjects',
        ['activated_subject_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_imported_curriculum_subjects_activated_package_id'),
        'imported_curriculum_subjects',
        ['activated_package_id'],
        unique=False,
    )

    op.create_table(
        'imported_curriculum_units',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sequence_order', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('standards_alignment', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('estimated_hours', sa.Integer(), nullable=True),
        sa.Column('prerequisites', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('activated_curriculum_unit_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['activated_curriculum_unit_id'],
            ['curriculum_units.id'],
            name=op.f('fk_imported_curriculum_units_activated_curriculum_unit_id_curriculum_units'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['subject_id'],
            ['imported_curriculum_subjects.id'],
            name=op.f('fk_imported_curriculum_units_subject_id_imported_curriculum_subjects'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_imported_curriculum_units')),
        sa.UniqueConstraint('subject_id', 'name', name='uq_imported_curriculum_units_subject_name'),
    )
    op.create_index(op.f('ix_imported_curriculum_units_id'), 'imported_curriculum_units', ['id'], unique=False)
    op.create_index(op.f('ix_imported_curriculum_units_subject_id'), 'imported_curriculum_units', ['subject_id'], unique=False)
    op.create_index(
        op.f('ix_imported_curriculum_units_activated_curriculum_unit_id'),
        'imported_curriculum_units',
        ['activated_curriculum_unit_id'],
        unique=False,
    )

    op.create_table(
        'imported_curriculum_lessons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unit_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sequence_order', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('estimated_minutes', sa.Integer(), nullable=True),
        sa.Column('objectives', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('resources', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('standards_alignment', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('prerequisites', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('activated_curriculum_lesson_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['activated_curriculum_lesson_id'],
            ['curriculum_lessons.id'],
            name=op.f('fk_imported_curriculum_lessons_activated_curriculum_lesson_id_curriculum_lessons'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['unit_id'],
            ['imported_curriculum_units.id'],
            name=op.f('fk_imported_curriculum_lessons_unit_id_imported_curriculum_units'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_imported_curriculum_lessons')),
        sa.UniqueConstraint('unit_id', 'name', name='uq_imported_curriculum_lessons_unit_name'),
    )
    op.create_index(op.f('ix_imported_curriculum_lessons_id'), 'imported_curriculum_lessons', ['id'], unique=False)
    op.create_index(op.f('ix_imported_curriculum_lessons_unit_id'), 'imported_curriculum_lessons', ['unit_id'], unique=False)
    op.create_index(
        op.f('ix_imported_curriculum_lessons_activated_curriculum_lesson_id'),
        'imported_curriculum_lessons',
        ['activated_curriculum_lesson_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_imported_curriculum_lessons_activated_curriculum_lesson_id'),
        table_name='imported_curriculum_lessons',
    )
    op.drop_index(op.f('ix_imported_curriculum_lessons_unit_id'), table_name='imported_curriculum_lessons')
    op.drop_index(op.f('ix_imported_curriculum_lessons_id'), table_name='imported_curriculum_lessons')
    op.drop_table('imported_curriculum_lessons')

    op.drop_index(
        op.f('ix_imported_curriculum_units_activated_curriculum_unit_id'),
        table_name='imported_curriculum_units',
    )
    op.drop_index(op.f('ix_imported_curriculum_units_subject_id'), table_name='imported_curriculum_units')
    op.drop_index(op.f('ix_imported_curriculum_units_id'), table_name='imported_curriculum_units')
    op.drop_table('imported_curriculum_units')

    op.drop_index(
        op.f('ix_imported_curriculum_subjects_activated_package_id'),
        table_name='imported_curriculum_subjects',
    )
    op.drop_index(
        op.f('ix_imported_curriculum_subjects_activated_subject_id'),
        table_name='imported_curriculum_subjects',
    )
    op.drop_index(op.f('ix_imported_curriculum_subjects_curriculum_id'), table_name='imported_curriculum_subjects')
    op.drop_index(op.f('ix_imported_curriculum_subjects_id'), table_name='imported_curriculum_subjects')
    op.drop_table('imported_curriculum_subjects')

    op.drop_index(op.f('ix_imported_curricula_created_by_user_id'), table_name='imported_curricula')
    op.drop_index(op.f('ix_imported_curricula_family_id'), table_name='imported_curricula')
    op.drop_index(op.f('ix_imported_curricula_id'), table_name='imported_curricula')
    op.drop_table('imported_curricula')
