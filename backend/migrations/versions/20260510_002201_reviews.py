"""review workflow and collaboration

Revision ID: 20260510_002201
Revises: 20260510_002100
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_002201'
down_revision: Union[str, Sequence[str], None] = '20260510_002100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes the human review queue, assignment comments, and reviewer assignment history.
- Export or resolve any active review items before rollback because reviewer comments and assignments are deleted.
"""

review_item_status = sa.Enum(
    'pending_review',
    'in_review',
    'approved',
    'rejected',
    'needs_regrade',
    name='review_item_status',
)
review_priority = sa.Enum('low', 'medium', 'high', 'urgent', name='review_priority')


def upgrade() -> None:
    bind = op.get_bind()
    review_item_status.create(bind, checkfirst=True)
    review_priority.create(bind, checkfirst=True)

    op.create_table(
        'review_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('grading_job_id', sa.Integer(), nullable=False),
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('status', review_item_status, server_default='pending_review', nullable=False),
        sa.Column('priority', review_priority, server_default='medium', nullable=False),
        sa.Column('ai_suggested_grade', sa.Float(), nullable=True),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], name=op.f('fk_review_items_assigned_to_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_review_items_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['grading_job_id'], ['grading_jobs.id'], name=op.f('fk_review_items_grading_job_id_grading_jobs'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], name=op.f('fk_review_items_reviewed_by_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], name=op.f('fk_review_items_submission_id_submissions'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_review_items')),
        sa.UniqueConstraint('grading_job_id', name='uq_review_items_grading_job_id'),
        sa.UniqueConstraint('submission_id', name='uq_review_items_submission_id'),
    )
    op.create_index(op.f('ix_review_items_id'), 'review_items', ['id'], unique=False)
    op.create_index(op.f('ix_review_items_family_id'), 'review_items', ['family_id'], unique=False)
    op.create_index(op.f('ix_review_items_submission_id'), 'review_items', ['submission_id'], unique=False)
    op.create_index(op.f('ix_review_items_grading_job_id'), 'review_items', ['grading_job_id'], unique=False)
    op.create_index(op.f('ix_review_items_assigned_to_user_id'), 'review_items', ['assigned_to_user_id'], unique=False)
    op.create_index(op.f('ix_review_items_reviewed_by_user_id'), 'review_items', ['reviewed_by_user_id'], unique=False)
    op.create_index(op.f('ix_review_items_status'), 'review_items', ['status'], unique=False)
    op.create_index(op.f('ix_review_items_priority'), 'review_items', ['priority'], unique=False)
    op.create_index(op.f('ix_review_items_reviewed_at'), 'review_items', ['reviewed_at'], unique=False)

    op.create_table(
        'review_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('review_item_id', sa.Integer(), nullable=False),
        sa.Column('author_user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], name=op.f('fk_review_comments_author_user_id_users'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_review_comments_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['review_item_id'], ['review_items.id'], name=op.f('fk_review_comments_review_item_id_review_items'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_review_comments')),
    )
    op.create_index(op.f('ix_review_comments_id'), 'review_comments', ['id'], unique=False)
    op.create_index(op.f('ix_review_comments_family_id'), 'review_comments', ['family_id'], unique=False)
    op.create_index(op.f('ix_review_comments_review_item_id'), 'review_comments', ['review_item_id'], unique=False)
    op.create_index(op.f('ix_review_comments_author_user_id'), 'review_comments', ['author_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_review_comments_author_user_id'), table_name='review_comments')
    op.drop_index(op.f('ix_review_comments_review_item_id'), table_name='review_comments')
    op.drop_index(op.f('ix_review_comments_family_id'), table_name='review_comments')
    op.drop_index(op.f('ix_review_comments_id'), table_name='review_comments')
    op.drop_table('review_comments')

    op.drop_index(op.f('ix_review_items_reviewed_at'), table_name='review_items')
    op.drop_index(op.f('ix_review_items_priority'), table_name='review_items')
    op.drop_index(op.f('ix_review_items_status'), table_name='review_items')
    op.drop_index(op.f('ix_review_items_reviewed_by_user_id'), table_name='review_items')
    op.drop_index(op.f('ix_review_items_assigned_to_user_id'), table_name='review_items')
    op.drop_index(op.f('ix_review_items_grading_job_id'), table_name='review_items')
    op.drop_index(op.f('ix_review_items_submission_id'), table_name='review_items')
    op.drop_index(op.f('ix_review_items_family_id'), table_name='review_items')
    op.drop_index(op.f('ix_review_items_id'), table_name='review_items')
    op.drop_table('review_items')

    bind = op.get_bind()
    review_priority.drop(bind, checkfirst=True)
    review_item_status.drop(bind, checkfirst=True)
