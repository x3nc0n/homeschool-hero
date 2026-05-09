"""grading hardening and answer keys

Revision ID: 20260510_001700
Revises: 20260510_001600
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_001700'
down_revision: Union[str, Sequence[str], None] = '20260510_001600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() reverts the grading_jobs status enum from the expanded 8-value set back to the original 5-value set,
  dropping the answer_keys table and all added columns on grading_jobs.
- Status values are mapped back on a best-effort basis; ocr_processing/ocr_complete/ai_complete all collapse to 'processing'.
- answer_keys data and the extra grading_jobs audit columns (ai_response, answer_key_result, etc.) are permanently lost.
- Export answer keys and grading audit data before rolling back.
"""

new_grading_status = sa.Enum(
    'pending',
    'ocr_processing',
    'ocr_complete',
    'ai_grading',
    'ai_complete',
    'review_needed',
    'reviewed',
    'final',
    name='grading_job_status',
)


def _upgrade_status_column() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        replacement = sa.Enum(
            'pending',
            'ocr_processing',
            'ocr_complete',
            'ai_grading',
            'ai_complete',
            'review_needed',
            'reviewed',
            'final',
            name='grading_job_status_new',
        )
        replacement.create(bind, checkfirst=True)
        op.execute(
            """
            ALTER TABLE grading_jobs
            ALTER COLUMN status TYPE grading_job_status_new
            USING (
              CASE status::text
                WHEN 'queued' THEN 'pending'
                WHEN 'processing' THEN 'ai_grading'
                WHEN 'needs_review' THEN 'review_needed'
                WHEN 'complete' THEN 'final'
                WHEN 'failed' THEN 'review_needed'
                ELSE status::text
              END
            )::grading_job_status_new
            """
        )
        op.execute('DROP TYPE grading_job_status')
        op.execute('ALTER TYPE grading_job_status_new RENAME TO grading_job_status')
        return

    with op.batch_alter_table('grading_jobs') as batch:
        batch.add_column(sa.Column('status_v2', sa.String(length=32), nullable=False, server_default='pending'))
    op.execute(
        """
        UPDATE grading_jobs
        SET status_v2 = CASE status
          WHEN 'queued' THEN 'pending'
          WHEN 'processing' THEN 'ai_grading'
          WHEN 'needs_review' THEN 'review_needed'
          WHEN 'complete' THEN 'final'
          WHEN 'failed' THEN 'review_needed'
          ELSE status
        END
        """
    )
    with op.batch_alter_table('grading_jobs') as batch:
        batch.drop_column('status')
        batch.alter_column('status_v2', new_column_name='status', existing_type=sa.String(length=32), type_=new_grading_status, nullable=False)


def _downgrade_status_column() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        replacement = sa.Enum('queued', 'processing', 'needs_review', 'complete', 'failed', name='grading_job_status_old')
        replacement.create(bind, checkfirst=True)
        op.execute(
            """
            ALTER TABLE grading_jobs
            ALTER COLUMN status TYPE grading_job_status_old
            USING (
              CASE status::text
                WHEN 'pending' THEN 'queued'
                WHEN 'ocr_processing' THEN 'processing'
                WHEN 'ocr_complete' THEN 'processing'
                WHEN 'ai_grading' THEN 'processing'
                WHEN 'ai_complete' THEN 'processing'
                WHEN 'review_needed' THEN 'needs_review'
                WHEN 'reviewed' THEN 'complete'
                WHEN 'final' THEN 'complete'
                ELSE 'queued'
              END
            )::grading_job_status_old
            """
        )
        op.execute('DROP TYPE grading_job_status')
        op.execute('ALTER TYPE grading_job_status_old RENAME TO grading_job_status')
        return

    with op.batch_alter_table('grading_jobs') as batch:
        batch.add_column(sa.Column('status_v1', sa.String(length=32), nullable=False, server_default='queued'))
    op.execute(
        """
        UPDATE grading_jobs
        SET status_v1 = CASE status
          WHEN 'pending' THEN 'queued'
          WHEN 'ocr_processing' THEN 'processing'
          WHEN 'ocr_complete' THEN 'processing'
          WHEN 'ai_grading' THEN 'processing'
          WHEN 'ai_complete' THEN 'processing'
          WHEN 'review_needed' THEN 'needs_review'
          WHEN 'reviewed' THEN 'complete'
          WHEN 'final' THEN 'complete'
          ELSE 'queued'
        END
        """
    )
    with op.batch_alter_table('grading_jobs') as batch:
        batch.drop_column('status')
        batch.alter_column('status_v1', new_column_name='status', existing_type=sa.String(length=32), nullable=False)


def upgrade() -> None:
    op.create_table(
        'answer_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('questions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], name=op.f('fk_answer_keys_assignment_id_assignments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_answer_keys_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_answer_keys')),
        sa.UniqueConstraint('assignment_id', name='uq_answer_keys_assignment_id'),
    )
    op.create_index(op.f('ix_answer_keys_id'), 'answer_keys', ['id'], unique=False)
    op.create_index(op.f('ix_answer_keys_assignment_id'), 'answer_keys', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_answer_keys_family_id'), 'answer_keys', ['family_id'], unique=False)

    with op.batch_alter_table('grading_jobs') as batch:
        batch.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('ai_response', sa.Text(), nullable=True))
        batch.add_column(sa.Column('answer_key_result', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('status_history', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column('human_override_details', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('manual_review_reason', sa.Text(), nullable=True))
        batch.add_column(sa.Column('ocr_retry_count', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('ai_retry_count', sa.Integer(), nullable=False, server_default='0'))

    op.execute(
        """
        UPDATE grading_jobs
        SET created_by_user_id = (
          SELECT family_memberships.user_id
          FROM family_memberships
          WHERE family_memberships.family_id = grading_jobs.family_id
          ORDER BY family_memberships.is_owner DESC, family_memberships.user_id ASC
          LIMIT 1
        )
        WHERE created_by_user_id IS NULL
        """
    )
    _upgrade_status_column()
    with op.batch_alter_table('grading_jobs') as batch:
        batch.alter_column('created_by_user_id', existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(op.f('fk_grading_jobs_created_by_user_id_users'), 'users', ['created_by_user_id'], ['id'])
        batch.create_index(op.f('ix_grading_jobs_created_by_user_id'), ['created_by_user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('grading_jobs') as batch:
        batch.drop_index(op.f('ix_grading_jobs_created_by_user_id'))
        batch.drop_constraint(op.f('fk_grading_jobs_created_by_user_id_users'), type_='foreignkey')

    _downgrade_status_column()
    with op.batch_alter_table('grading_jobs') as batch:
        batch.drop_column('ai_retry_count')
        batch.drop_column('ocr_retry_count')
        batch.drop_column('manual_review_reason')
        batch.drop_column('human_override_details')
        batch.drop_column('status_history')
        batch.drop_column('answer_key_result')
        batch.drop_column('ai_response')
        batch.drop_column('created_by_user_id')

    op.drop_index(op.f('ix_answer_keys_family_id'), table_name='answer_keys')
    op.drop_index(op.f('ix_answer_keys_assignment_id'), table_name='answer_keys')
    op.drop_index(op.f('ix_answer_keys_id'), table_name='answer_keys')
    op.drop_table('answer_keys')
