"""import jobs

Revision ID: 20260510_002100
Revises: 20260510_001700, 20260510_002000
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_002100'
down_revision: Union[str, Sequence[str], None] = ('20260510_001700', '20260510_002000')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops the import_jobs table and the import_entity_type and import_job_status enum types.
- All import job history will be permanently lost; no row data is migrated elsewhere.
- Export pending/failed import records before rolling back if recovery is needed.
"""

import_entity_type = sa.Enum(
    'students',
    'subjects',
    'assignments',
    'grades',
    'attendance',
    'curriculum_packages',
    name='import_entity_type',
)
import_job_status = sa.Enum('pending', 'validating', 'importing', 'complete', 'failed', name='import_job_status')


def upgrade() -> None:
    bind = op.get_bind()
    import_entity_type.create(bind, checkfirst=True)
    import_job_status.create(bind, checkfirst=True)

    op.create_table(
        'import_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('entity_type', import_entity_type, nullable=False),
        sa.Column('status', import_job_status, server_default='pending', nullable=False),
        sa.Column('total_rows', sa.Integer(), server_default='0', nullable=False),
        sa.Column('processed_rows', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('errors', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_import_jobs_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_import_jobs_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_import_jobs')),
    )
    op.create_index(op.f('ix_import_jobs_id'), 'import_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_import_jobs_family_id'), 'import_jobs', ['family_id'], unique=False)
    op.create_index(op.f('ix_import_jobs_user_id'), 'import_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_import_jobs_entity_type'), 'import_jobs', ['entity_type'], unique=False)
    op.create_index(op.f('ix_import_jobs_status'), 'import_jobs', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_import_jobs_status'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_entity_type'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_user_id'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_family_id'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_id'), table_name='import_jobs')
    op.drop_table('import_jobs')

    bind = op.get_bind()
    import_job_status.drop(bind, checkfirst=True)
    import_entity_type.drop(bind, checkfirst=True)
