"""export jobs and portability packages

Revision ID: 20260510_003400
Revises: 20260510_003300
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_003400'
down_revision: Union[str, Sequence[str], None] = '20260510_003300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops the export_jobs table and the export_type, export_format, and export_job_status enum types.
- All export job records and file-path references will be permanently lost; the physical export files on disk are not removed.
- Export job metadata should be archived before rolling back if audit trails are required.
"""

export_type = postgresql.ENUM('full', 'incremental', 'entity', name='export_type', create_type=False)
export_format = postgresql.ENUM('json', 'csv', 'zip', name='export_format', create_type=False)
export_job_status = postgresql.ENUM('pending', 'processing', 'complete', 'failed', name='export_job_status', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    export_type.create(bind, checkfirst=True)
    export_format.create(bind, checkfirst=True)
    export_job_status.create(bind, checkfirst=True)

    op.create_table(
        'export_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('export_type', export_type, nullable=False),
        sa.Column('format', export_format, nullable=False),
        sa.Column('status', export_job_status, nullable=False, server_default='pending'),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('entity_types', sa.JSON(), nullable=False),
        sa.Column('date_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_export_jobs_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_export_jobs_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_export_jobs')),
    )
    op.create_index(op.f('ix_export_jobs_id'), 'export_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_export_jobs_family_id'), 'export_jobs', ['family_id'], unique=False)
    op.create_index(op.f('ix_export_jobs_user_id'), 'export_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_export_jobs_export_type'), 'export_jobs', ['export_type'], unique=False)
    op.create_index(op.f('ix_export_jobs_format'), 'export_jobs', ['format'], unique=False)
    op.create_index(op.f('ix_export_jobs_status'), 'export_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_export_jobs_expires_at'), 'export_jobs', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_export_jobs_expires_at'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_status'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_format'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_export_type'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_user_id'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_family_id'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_id'), table_name='export_jobs')
    op.drop_table('export_jobs')

    bind = op.get_bind()
    export_job_status.drop(bind, checkfirst=True)
    export_format.drop(bind, checkfirst=True)
    export_type.drop(bind, checkfirst=True)
