"""user ui preferences

Revision ID: 20260510_005000
Revises: 20260510_004500
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_005000'
down_revision: Union[str, Sequence[str], None] = '20260510_004500'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops the user_preferences table.
- All stored UI preferences (theme, accent color, font size, etc.) for every user will be permanently lost.
- Users will revert to application defaults after rollback; no other table is affected.
"""


def upgrade() -> None:
    op.create_table(
        'user_preferences',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('theme', sa.String(length=32), nullable=False, server_default='system'),
        sa.Column('accent_color', sa.String(length=16), nullable=False, server_default='#2563eb'),
        sa.Column('font_size', sa.String(length=16), nullable=False, server_default='medium'),
        sa.Column('density', sa.String(length=16), nullable=False, server_default='comfortable'),
        sa.Column('sidebar_position', sa.String(length=16), nullable=False, server_default='left'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_preferences_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', name=op.f('pk_user_preferences')),
    )
    op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_preferences_user_id'), table_name='user_preferences')
    op.drop_table('user_preferences')
