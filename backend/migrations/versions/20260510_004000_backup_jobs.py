"""backup jobs and NAS scheduling

Revision ID: 20260510_004000
Revises: 20260510_003400
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_004000'
down_revision: Union[str, Sequence[str], None] = '20260510_003400'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops the backup_jobs table and the backup_type, backup_job_status, and backup_destination enum types.
- All backup job history and manifest data will be permanently lost; physical backup files on disk are not affected.
- Record any in-progress or pending backup job details before rolling back.
"""

backup_type = sa.Enum('full', 'incremental', 'manual', name='backup_type')
backup_job_status = sa.Enum('pending', 'running', 'complete', 'failed', name='backup_job_status')
backup_destination = sa.Enum('local', 'smb', 'nfs', name='backup_destination')


def upgrade() -> None:
    bind = op.get_bind()
    backup_type.create(bind, checkfirst=True)
    backup_job_status.create(bind, checkfirst=True)
    backup_destination.create(bind, checkfirst=True)

    op.create_table(
        'backup_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('backup_type', backup_type, nullable=False),
        sa.Column('status', backup_job_status, nullable=False, server_default='pending'),
        sa.Column('destination', backup_destination, nullable=False, server_default='local'),
        sa.Column('file_path', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('file_size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('manifest', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_backup_jobs_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_backup_jobs_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_backup_jobs')),
    )
    op.create_index(op.f('ix_backup_jobs_id'), 'backup_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_backup_jobs_family_id'), 'backup_jobs', ['family_id'], unique=False)
    op.create_index(op.f('ix_backup_jobs_user_id'), 'backup_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_backup_jobs_backup_type'), 'backup_jobs', ['backup_type'], unique=False)
    op.create_index(op.f('ix_backup_jobs_status'), 'backup_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_backup_jobs_destination'), 'backup_jobs', ['destination'], unique=False)
    op.create_index(op.f('ix_backup_jobs_started_at'), 'backup_jobs', ['started_at'], unique=False)
    op.create_index(
        'ix_backup_jobs_family_status_started_at',
        'backup_jobs',
        ['family_id', 'status', 'started_at'],
        unique=False,
    )
    op.create_index(
        'ix_backup_jobs_family_completed_at',
        'backup_jobs',
        ['family_id', 'completed_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_backup_jobs_family_completed_at', table_name='backup_jobs')
    op.drop_index('ix_backup_jobs_family_status_started_at', table_name='backup_jobs')
    op.drop_index(op.f('ix_backup_jobs_started_at'), table_name='backup_jobs')
    op.drop_index(op.f('ix_backup_jobs_destination'), table_name='backup_jobs')
    op.drop_index(op.f('ix_backup_jobs_status'), table_name='backup_jobs')
    op.drop_index(op.f('ix_backup_jobs_backup_type'), table_name='backup_jobs')
    op.drop_index(op.f('ix_backup_jobs_user_id'), table_name='backup_jobs')
    op.drop_index(op.f('ix_backup_jobs_family_id'), table_name='backup_jobs')
    op.drop_index(op.f('ix_backup_jobs_id'), table_name='backup_jobs')
    op.drop_table('backup_jobs')

    bind = op.get_bind()
    backup_destination.drop(bind, checkfirst=True)
    backup_job_status.drop(bind, checkfirst=True)
    backup_type.drop(bind, checkfirst=True)
