"""portfolio and learning journal

Revision ID: 20260510_002000
Revises: 20260510_001540
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_002000'
down_revision: Union[str, Sequence[str], None] = '20260510_001540'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes portfolio entries, collections, and public share tokens.
- Export shared collections before downgrade if families need to preserve public links or curated groupings.
- PostgreSQL audit enum values are left in place on downgrade to avoid destructive enum rewrites against existing audit history.
"""


def _add_postgres_enum_values() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    for value in (
        'portfolio_entry_create',
        'portfolio_entry_update',
        'portfolio_entry_delete',
        'portfolio_collection_create',
        'portfolio_collection_update',
        'portfolio_collection_delete',
        'portfolio_share',
    ):
        op.execute(sa.text(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'"))


def upgrade() -> None:
    _add_postgres_enum_values()

    portfolio_entry_type = postgresql.ENUM(
        'work_sample',
        'journal',
        'milestone',
        'photo',
        'note',
        name='portfolio_entry_type',
    create_type=False,
)
    portfolio_entry_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'portfolio_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('entry_type', portfolio_entry_type, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=True),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('submission_id', sa.Integer(), nullable=True),
        sa.Column('attachments', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], name=op.f('fk_portfolio_entries_assignment_id_assignments'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_portfolio_entries_created_by_user_id_users')),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_portfolio_entries_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_portfolio_entries_student_id_students'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_portfolio_entries_subject_id_subjects'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], name=op.f('fk_portfolio_entries_submission_id_submissions'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_portfolio_entries')),
    )
    with op.batch_alter_table('portfolio_entries') as batch:
        batch.create_index(op.f('ix_portfolio_entries_id'), ['id'], unique=False)
        batch.create_index(op.f('ix_portfolio_entries_family_id'), ['family_id'], unique=False)
        batch.create_index(op.f('ix_portfolio_entries_student_id'), ['student_id'], unique=False)
        batch.create_index(op.f('ix_portfolio_entries_entry_type'), ['entry_type'], unique=False)
        batch.create_index(op.f('ix_portfolio_entries_date'), ['date'], unique=False)
        batch.create_index(op.f('ix_portfolio_entries_subject_id'), ['subject_id'], unique=False)
        batch.create_index(op.f('ix_portfolio_entries_assignment_id'), ['assignment_id'], unique=False)
        batch.create_index(op.f('ix_portfolio_entries_submission_id'), ['submission_id'], unique=False)
        batch.create_index(op.f('ix_portfolio_entries_created_by_user_id'), ['created_by_user_id'], unique=False)

    op.create_table(
        'portfolio_collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('entry_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('share_token', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_portfolio_collections_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_portfolio_collections_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_portfolio_collections')),
    )
    with op.batch_alter_table('portfolio_collections') as batch:
        batch.create_index(op.f('ix_portfolio_collections_id'), ['id'], unique=False)
        batch.create_index(op.f('ix_portfolio_collections_family_id'), ['family_id'], unique=False)
        batch.create_index(op.f('ix_portfolio_collections_student_id'), ['student_id'], unique=False)
        batch.create_index(op.f('ix_portfolio_collections_share_token'), ['share_token'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('portfolio_collections') as batch:
        batch.drop_index(op.f('ix_portfolio_collections_share_token'))
        batch.drop_index(op.f('ix_portfolio_collections_student_id'))
        batch.drop_index(op.f('ix_portfolio_collections_family_id'))
        batch.drop_index(op.f('ix_portfolio_collections_id'))
    op.drop_table('portfolio_collections')

    with op.batch_alter_table('portfolio_entries') as batch:
        batch.drop_index(op.f('ix_portfolio_entries_created_by_user_id'))
        batch.drop_index(op.f('ix_portfolio_entries_submission_id'))
        batch.drop_index(op.f('ix_portfolio_entries_assignment_id'))
        batch.drop_index(op.f('ix_portfolio_entries_subject_id'))
        batch.drop_index(op.f('ix_portfolio_entries_date'))
        batch.drop_index(op.f('ix_portfolio_entries_entry_type'))
        batch.drop_index(op.f('ix_portfolio_entries_student_id'))
        batch.drop_index(op.f('ix_portfolio_entries_family_id'))
        batch.drop_index(op.f('ix_portfolio_entries_id'))
    op.drop_table('portfolio_entries')

    sa.Enum(name='portfolio_entry_type').drop(op.get_bind(), checkfirst=True)
