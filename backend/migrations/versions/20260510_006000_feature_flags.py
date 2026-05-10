"""add enabled_features to family_settings

Revision ID: 20260510_006000
Revises: 20260510_005500
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = '20260510_006000'
down_revision: Union[str, Sequence[str], None] = '20260510_005500'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes the enabled_features column from family_settings.
- Any saved feature flag overrides for families will be permanently lost.
- Families will fall back to the default behavior where all optional features remain enabled.
"""


def upgrade() -> None:
    op.add_column(
        'family_settings',
        sa.Column('enabled_features', sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column('family_settings', 'enabled_features')
