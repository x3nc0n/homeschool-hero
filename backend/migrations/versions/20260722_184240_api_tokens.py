"""api token support for headless automation

Revision ID: 20260722_184240
Revises: 20260612_183758
Create Date: 2026-07-22T18:42:40.909-05:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = '20260722_184240'
down_revision: Union[str, Sequence[str], None] = '20260612_183758'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# Alembic loads these module globals via introspection during migration discovery.
__all__ = ('revision', 'down_revision', 'branch_labels', 'depends_on')

ROLLBACK_NOTES = """
- downgrade() drops the api_tokens table and all token metadata.
- API tokens become invalid immediately after downgrade because registration records are removed.
"""


def upgrade() -> None:
    op.create_table(
        'api_tokens',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('token_digest', sa.String(length=64), nullable=False),
        sa.Column('capabilities', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'],
            ['users.id'],
            name=op.f('fk_api_tokens_created_by_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['family_id'],
            ['families.id'],
            name=op.f('fk_api_tokens_family_id_families'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_api_tokens')),
        sa.UniqueConstraint('family_id', 'name', name='uq_api_tokens_family_name'),
    )
    op.create_index(op.f('ix_api_tokens_id'), 'api_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_api_tokens_family_id'), 'api_tokens', ['family_id'], unique=False)
    op.create_index(op.f('ix_api_tokens_created_by_user_id'), 'api_tokens', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_api_tokens_expires_at'), 'api_tokens', ['expires_at'], unique=False)
    op.create_index(op.f('ix_api_tokens_revoked_at'), 'api_tokens', ['revoked_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_api_tokens_revoked_at'), table_name='api_tokens')
    op.drop_index(op.f('ix_api_tokens_expires_at'), table_name='api_tokens')
    op.drop_index(op.f('ix_api_tokens_created_by_user_id'), table_name='api_tokens')
    op.drop_index(op.f('ix_api_tokens_family_id'), table_name='api_tokens')
    op.drop_index(op.f('ix_api_tokens_id'), table_name='api_tokens')
    op.drop_table('api_tokens')
