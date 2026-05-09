"""maintenance mode scheduling and status

Revision ID: 20260510_004500
Revises: 20260510_004000
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_004500'
down_revision: Union[str, Sequence[str], None] = '20260510_004000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'maintenance_modes',
        sa.Column('id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('message', sa.String(length=500), nullable=False),
        sa.Column('scheduled_start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], name=op.f('fk_maintenance_modes_updated_by_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_maintenance_modes')),
    )
    op.create_index(op.f('ix_maintenance_modes_updated_by_user_id'), 'maintenance_modes', ['updated_by_user_id'], unique=False)
    op.execute(
        sa.text(
            "INSERT INTO maintenance_modes (id, enabled, message) "
            "VALUES (1, false, 'Homeschool Hero is temporarily unavailable while we perform maintenance. Please check back soon.')"
        )
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_maintenance_modes_updated_by_user_id'), table_name='maintenance_modes')
    op.drop_table('maintenance_modes')
