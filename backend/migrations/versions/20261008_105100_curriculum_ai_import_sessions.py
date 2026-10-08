"""curriculum ai import sessions

Revision ID: 20261008_105100
Revises: 20261006_172835
Create Date: 2026-10-08T10:51:00-05:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = '20261008_105100'
down_revision: Union[str, Sequence[str], None] = '20261006_172835'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops all background curriculum AI import drafts (processing, ready, failed, expired, and confirmed history).
- Curricula already created from confirmed drafts remain in the imported curriculum tables.
- Source text is never persisted, so no source content is lost.
"""

TABLE = 'curriculum_ai_import_sessions'


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('processing', 'ready', 'failed', 'expired', 'confirmed', name='curriculum_ai_import_session_status'),
            server_default='processing',
            nullable=False,
        ),
        sa.Column('source_kind', sa.String(length=16), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('warnings', sa.JSON(), nullable=False),
        sa.Column('draft_payload', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('revision', sa.Integer(), server_default='1', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_curriculum_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'],
            ['users.id'],
            name=op.f('fk_curriculum_ai_import_sessions_created_by_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['family_id'],
            ['families.id'],
            name=op.f('fk_curriculum_ai_import_sessions_family_id_families'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['confirmed_curriculum_id'],
            ['imported_curricula.id'],
            name=op.f('fk_curriculum_ai_import_sessions_confirmed_curriculum_id_imported_curricula'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_curriculum_ai_import_sessions')),
    )
    op.create_index(op.f('ix_curriculum_ai_import_sessions_id'), TABLE, ['id'], unique=False)
    op.create_index(op.f('ix_curriculum_ai_import_sessions_family_id'), TABLE, ['family_id'], unique=False)
    op.create_index(op.f('ix_curriculum_ai_import_sessions_created_by_user_id'), TABLE, ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_curriculum_ai_import_sessions_status'), TABLE, ['status'], unique=False)
    op.create_index(op.f('ix_curriculum_ai_import_sessions_confirmed_curriculum_id'), TABLE, ['confirmed_curriculum_id'], unique=False)
    op.create_index('ix_curriculum_ai_import_sessions_expires_at', TABLE, ['expires_at'], unique=False)
    op.create_index('ix_curriculum_ai_import_sessions_family_status', TABLE, ['family_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_curriculum_ai_import_sessions_family_status', table_name=TABLE)
    op.drop_index('ix_curriculum_ai_import_sessions_expires_at', table_name=TABLE)
    op.drop_index(op.f('ix_curriculum_ai_import_sessions_confirmed_curriculum_id'), table_name=TABLE)
    op.drop_index(op.f('ix_curriculum_ai_import_sessions_status'), table_name=TABLE)
    op.drop_index(op.f('ix_curriculum_ai_import_sessions_created_by_user_id'), table_name=TABLE)
    op.drop_index(op.f('ix_curriculum_ai_import_sessions_family_id'), table_name=TABLE)
    op.drop_index(op.f('ix_curriculum_ai_import_sessions_id'), table_name=TABLE)
    op.drop_table(TABLE)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS curriculum_ai_import_session_status')
