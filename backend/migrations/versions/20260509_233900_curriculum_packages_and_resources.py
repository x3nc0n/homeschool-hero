"""curriculum packages and resources

Revision ID: 20260509_233900
Revises: 20260509_003000
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260509_233900'
down_revision: Union[str, None] = '20260509_003000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() removes curriculum packages, units, lessons, resources, and lesson-resource links.
- File paths stored in the database are removed from the schema but any uploaded files left on disk must be
  cleaned up separately by the operator before or after downgrade.
- Take a backup before downgrade if curriculum planning or resource library data must be preserved.
"""

resource_type = postgresql.ENUM('file', 'link', 'note', name='resource_type', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    resource_type.create(bind, checkfirst=True)

    op.create_table(
        'curriculum_packages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'],
            ['users.id'],
            name=op.f('fk_curriculum_packages_created_by_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['family_id'], ['families.id'], name=op.f('fk_curriculum_packages_family_id_families'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['school_year_id'],
            ['school_years.id'],
            name=op.f('fk_curriculum_packages_school_year_id_school_years'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['subject_id'], ['subjects.id'], name=op.f('fk_curriculum_packages_subject_id_subjects'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_curriculum_packages')),
        sa.UniqueConstraint('family_id', 'school_year_id', 'name', name='uq_curriculum_packages_family_school_year_name'),
    )
    op.create_index(op.f('ix_curriculum_packages_id'), 'curriculum_packages', ['id'], unique=False)
    op.create_index(op.f('ix_curriculum_packages_family_id'), 'curriculum_packages', ['family_id'], unique=False)
    op.create_index(op.f('ix_curriculum_packages_school_year_id'), 'curriculum_packages', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_curriculum_packages_subject_id'), 'curriculum_packages', ['subject_id'], unique=False)
    op.create_index(
        op.f('ix_curriculum_packages_created_by_user_id'),
        'curriculum_packages',
        ['created_by_user_id'],
        unique=False,
    )

    op.create_table(
        'curriculum_units',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('package_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sequence_order', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('standards_tags', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['package_id'],
            ['curriculum_packages.id'],
            name=op.f('fk_curriculum_units_package_id_curriculum_packages'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_curriculum_units')),
        sa.UniqueConstraint('package_id', 'name', name='uq_curriculum_units_package_name'),
    )
    op.create_index(op.f('ix_curriculum_units_id'), 'curriculum_units', ['id'], unique=False)
    op.create_index(op.f('ix_curriculum_units_package_id'), 'curriculum_units', ['package_id'], unique=False)

    op.create_table(
        'curriculum_lessons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unit_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sequence_order', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('standards_tags', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['unit_id'], ['curriculum_units.id'], name=op.f('fk_curriculum_lessons_unit_id_curriculum_units'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_curriculum_lessons')),
        sa.UniqueConstraint('unit_id', 'name', name='uq_curriculum_lessons_unit_name'),
    )
    op.create_index(op.f('ix_curriculum_lessons_id'), 'curriculum_lessons', ['id'], unique=False)
    op.create_index(op.f('ix_curriculum_lessons_unit_id'), 'curriculum_lessons', ['unit_id'], unique=False)

    op.create_table(
        'resources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('resource_type', resource_type, nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('tags', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['users.id'], name=op.f('fk_resources_created_by_user_id_users'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_resources_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_resources')),
        sa.UniqueConstraint('family_id', 'name', name='uq_resources_family_id_name'),
    )
    op.create_index(op.f('ix_resources_id'), 'resources', ['id'], unique=False)
    op.create_index(op.f('ix_resources_family_id'), 'resources', ['family_id'], unique=False)
    op.create_index(op.f('ix_resources_created_by_user_id'), 'resources', ['created_by_user_id'], unique=False)

    op.create_table(
        'lesson_resources',
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['lesson_id'],
            ['curriculum_lessons.id'],
            name=op.f('fk_lesson_resources_lesson_id_curriculum_lessons'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['resource_id'], ['resources.id'], name=op.f('fk_lesson_resources_resource_id_resources'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('lesson_id', 'resource_id', name=op.f('pk_lesson_resources')),
    )
    op.create_index(op.f('ix_lesson_resources_lesson_id'), 'lesson_resources', ['lesson_id'], unique=False)
    op.create_index(op.f('ix_lesson_resources_resource_id'), 'lesson_resources', ['resource_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lesson_resources_resource_id'), table_name='lesson_resources')
    op.drop_index(op.f('ix_lesson_resources_lesson_id'), table_name='lesson_resources')
    op.drop_table('lesson_resources')

    op.drop_index(op.f('ix_resources_created_by_user_id'), table_name='resources')
    op.drop_index(op.f('ix_resources_family_id'), table_name='resources')
    op.drop_index(op.f('ix_resources_id'), table_name='resources')
    op.drop_table('resources')

    op.drop_index(op.f('ix_curriculum_lessons_unit_id'), table_name='curriculum_lessons')
    op.drop_index(op.f('ix_curriculum_lessons_id'), table_name='curriculum_lessons')
    op.drop_table('curriculum_lessons')

    op.drop_index(op.f('ix_curriculum_units_package_id'), table_name='curriculum_units')
    op.drop_index(op.f('ix_curriculum_units_id'), table_name='curriculum_units')
    op.drop_table('curriculum_units')

    op.drop_index(op.f('ix_curriculum_packages_created_by_user_id'), table_name='curriculum_packages')
    op.drop_index(op.f('ix_curriculum_packages_subject_id'), table_name='curriculum_packages')
    op.drop_index(op.f('ix_curriculum_packages_school_year_id'), table_name='curriculum_packages')
    op.drop_index(op.f('ix_curriculum_packages_family_id'), table_name='curriculum_packages')
    op.drop_index(op.f('ix_curriculum_packages_id'), table_name='curriculum_packages')
    op.drop_table('curriculum_packages')

    bind = op.get_bind()
    resource_type.drop(bind, checkfirst=True)
