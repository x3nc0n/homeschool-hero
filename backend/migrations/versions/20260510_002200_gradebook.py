"""gradebook categories and scales

Revision ID: 20260510_002203
Revises: 20260510_002100
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_002203'
down_revision: Union[str, Sequence[str], None] = '20260510_002100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes persisted grade scales, grade categories, subject grading modes, and subject-level scale overrides.
- Subject rows using `participation` or `extra_credit` assignment categories are mapped back to `other` on downgrade.
- Export gradebook configuration before rollback if families need to preserve custom weighting rules or alternate GPA scales.
"""

old_assignment_category = postgresql.ENUM('homework', 'quiz', 'test', 'project', 'other', name='assignment_category', create_type=False)
new_assignment_category = postgresql.ENUM(
    'homework',
    'quiz',
    'test',
    'project',
    'participation',
    'extra_credit',
    'other',
    name='assignment_category',
create_type=False,
)
subject_grading_mode = postgresql.ENUM('points', 'percentage', name='subject_grading_mode', create_type=False)


def _upgrade_assignment_category_enum() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TYPE assignment_category ADD VALUE IF NOT EXISTS 'participation'")
        op.execute("ALTER TYPE assignment_category ADD VALUE IF NOT EXISTS 'extra_credit'")
        return

    with op.batch_alter_table('assignments') as batch:
        batch.alter_column(
            'category',
            existing_type=old_assignment_category,
            type_=new_assignment_category,
            existing_nullable=False,
        )


def _downgrade_assignment_category_enum() -> None:
    bind = op.get_bind()
    op.execute("UPDATE assignments SET category = 'other' WHERE category IN ('participation', 'extra_credit')")
    if bind.dialect.name == 'postgresql':
        replacement = postgresql.ENUM('homework', 'quiz', 'test', 'project', 'other', name='assignment_category_old', create_type=False)
        replacement.create(bind, checkfirst=True)
        op.execute(
            """
            ALTER TABLE assignments
            ALTER COLUMN category TYPE assignment_category_old
            USING (
              CASE category::text
                WHEN 'participation' THEN 'other'
                WHEN 'extra_credit' THEN 'other'
                ELSE category::text
              END
            )::assignment_category_old
            """
        )
        op.execute('DROP TYPE assignment_category')
        op.execute('ALTER TYPE assignment_category_old RENAME TO assignment_category')
        return

    with op.batch_alter_table('assignments') as batch:
        batch.alter_column(
            'category',
            existing_type=new_assignment_category,
            type_=old_assignment_category,
            existing_nullable=False,
        )


def _seed_default_grade_scales() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    families = sa.Table('families', metadata, sa.Column('id', sa.Integer()))
    grade_scales = sa.Table(
        'grade_scales',
        metadata,
        sa.Column('id', sa.Integer()),
        sa.Column('family_id', sa.Integer()),
        sa.Column('name', sa.String(120)),
        sa.Column('ranges', sa.JSON()),
        sa.Column('is_default', sa.Boolean()),
    )
    rows = bind.execute(sa.select(families.c.id)).fetchall()
    default_ranges = [
        {'letter': 'A', 'min': 90, 'max': 100, 'gpa_points': 4.0},
        {'letter': 'B', 'min': 80, 'max': 89.99, 'gpa_points': 3.0},
        {'letter': 'C', 'min': 70, 'max': 79.99, 'gpa_points': 2.0},
        {'letter': 'D', 'min': 60, 'max': 69.99, 'gpa_points': 1.0},
        {'letter': 'F', 'min': 0, 'max': 59.99, 'gpa_points': 0.0},
    ]
    for (family_id,) in rows:
        bind.execute(
            grade_scales.insert().values(
                family_id=family_id,
                name='Default 4.0 Scale',
                ranges=default_ranges,
                is_default=True,
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    subject_grading_mode.create(bind, checkfirst=True)
    _upgrade_assignment_category_enum()

    op.create_table(
        'grade_scales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('ranges', sa.JSON(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_grade_scales_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_grade_scales')),
        sa.UniqueConstraint('family_id', 'name', name='uq_grade_scales_family_id_name'),
    )
    op.create_index(op.f('ix_grade_scales_id'), 'grade_scales', ['id'], unique=False)
    op.create_index(op.f('ix_grade_scales_family_id'), 'grade_scales', ['family_id'], unique=False)

    with op.batch_alter_table('subjects') as batch:
        batch.add_column(sa.Column('grading_mode', subject_grading_mode, nullable=False, server_default='points'))
        batch.add_column(sa.Column('grade_scale_id', sa.Integer(), nullable=True))
        batch.create_index(op.f('ix_subjects_grade_scale_id'), ['grade_scale_id'], unique=False)
        batch.create_foreign_key(
            op.f('fk_subjects_grade_scale_id_grade_scales'),
            'grade_scales',
            ['grade_scale_id'],
            ['id'],
            ondelete='SET NULL',
        )

    op.create_table(
        'grade_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False, server_default='0'),
        sa.Column('drop_lowest', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_grade_categories_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_grade_categories_subject_id_subjects'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_grade_categories')),
        sa.UniqueConstraint('subject_id', 'name', name='uq_grade_categories_subject_id_name'),
    )
    op.create_index(op.f('ix_grade_categories_id'), 'grade_categories', ['id'], unique=False)
    op.create_index(op.f('ix_grade_categories_family_id'), 'grade_categories', ['family_id'], unique=False)
    op.create_index(op.f('ix_grade_categories_subject_id'), 'grade_categories', ['subject_id'], unique=False)

    _seed_default_grade_scales()


def downgrade() -> None:
    op.drop_index(op.f('ix_grade_categories_subject_id'), table_name='grade_categories')
    op.drop_index(op.f('ix_grade_categories_family_id'), table_name='grade_categories')
    op.drop_index(op.f('ix_grade_categories_id'), table_name='grade_categories')
    op.drop_table('grade_categories')

    with op.batch_alter_table('subjects') as batch:
        batch.drop_constraint(op.f('fk_subjects_grade_scale_id_grade_scales'), type_='foreignkey')
        batch.drop_index(op.f('ix_subjects_grade_scale_id'))
        batch.drop_column('grade_scale_id')
        batch.drop_column('grading_mode')

    op.drop_index(op.f('ix_grade_scales_family_id'), table_name='grade_scales')
    op.drop_index(op.f('ix_grade_scales_id'), table_name='grade_scales')
    op.drop_table('grade_scales')

    _downgrade_assignment_category_enum()

    bind = op.get_bind()
    subject_grading_mode.drop(bind, checkfirst=True)
