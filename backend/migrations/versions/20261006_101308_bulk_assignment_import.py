"""bulk assignment import sessions

Revision ID: 20261006_101308
Revises: 20261004_091800
Create Date: 2026-10-06T10:13:08-05:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = '20261006_101308'
down_revision: Union[str, Sequence[str], None] = '20261004_091800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops all unconfirmed bulk assignment import drafts and their clarification state.
- Real assignments created from confirmed drafts remain in the assignments tables.
"""


def upgrade() -> None:
    op.create_table(
        'bulk_assignment_import_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('draft', 'needs_clarification', 'ready', 'confirmed', 'expired', 'failed', name='bulk_assignment_import_status'),
            server_default='draft',
            nullable=False,
        ),
        sa.Column('source_filename', sa.String(length=255), nullable=False),
        sa.Column('source_content_type', sa.String(length=160), nullable=False),
        sa.Column('source_size_bytes', sa.Integer(), nullable=False),
        sa.Column('extracted_text_hash', sa.String(length=64), nullable=False),
        sa.Column('warnings', sa.JSON(), nullable=False),
        sa.Column('draft_payload', sa.JSON(), nullable=False),
        sa.Column('questions', sa.JSON(), nullable=False),
        sa.Column('revision', sa.Integer(), server_default='1', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'],
            ['users.id'],
            name=op.f('fk_bulk_assignment_import_sessions_created_by_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['family_id'],
            ['families.id'],
            name=op.f('fk_bulk_assignment_import_sessions_family_id_families'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_bulk_assignment_import_sessions')),
    )
    op.create_index(op.f('ix_bulk_assignment_import_sessions_id'), 'bulk_assignment_import_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_bulk_assignment_import_sessions_family_id'), 'bulk_assignment_import_sessions', ['family_id'], unique=False)
    op.create_index(
        op.f('ix_bulk_assignment_import_sessions_created_by_user_id'),
        'bulk_assignment_import_sessions',
        ['created_by_user_id'],
        unique=False,
    )
    op.create_index(op.f('ix_bulk_assignment_import_sessions_status'), 'bulk_assignment_import_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_bulk_assignment_import_sessions_expires_at'), 'bulk_assignment_import_sessions', ['expires_at'], unique=False)
    op.create_index(
        'ix_bulk_assignment_import_sessions_family_status',
        'bulk_assignment_import_sessions',
        ['family_id', 'status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_bulk_assignment_import_sessions_family_status', table_name='bulk_assignment_import_sessions')
    op.drop_index(op.f('ix_bulk_assignment_import_sessions_expires_at'), table_name='bulk_assignment_import_sessions')
    op.drop_index(op.f('ix_bulk_assignment_import_sessions_status'), table_name='bulk_assignment_import_sessions')
    op.drop_index(op.f('ix_bulk_assignment_import_sessions_created_by_user_id'), table_name='bulk_assignment_import_sessions')
    op.drop_index(op.f('ix_bulk_assignment_import_sessions_family_id'), table_name='bulk_assignment_import_sessions')
    op.drop_index(op.f('ix_bulk_assignment_import_sessions_id'), table_name='bulk_assignment_import_sessions')
    op.drop_table('bulk_assignment_import_sessions')
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS bulk_assignment_import_status')
