"""add created_at and updated_at to submissions

Revision ID: 20260510_005500
Revises: 20260510_005000
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = '20260510_005500'
down_revision: Union[str, Sequence[str], None] = '20260510_005000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes created_at and updated_at columns from submissions.
- No data loss beyond the timestamp columns themselves.
"""


def upgrade() -> None:
    with op.batch_alter_table('submissions') as batch:
        batch.add_column(
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        batch.add_column(
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )


def downgrade() -> None:
    with op.batch_alter_table('submissions') as batch:
        batch.drop_column('updated_at')
        batch.drop_column('created_at')
