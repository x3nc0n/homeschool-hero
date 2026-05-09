"""security hardening

Revision ID: 20260509_000100
Revises: 20260508_224850
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260509_000100'
down_revision: Union[str, None] = '20260508_224850'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops failed_login_attempts and locked_until from the users table.
- Any active lockouts will be cleared; ensure no security incident is in progress before rolling back.
- No row data is lost beyond those two columns.
"""


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('locked_until')
        batch.drop_column('failed_login_attempts')
