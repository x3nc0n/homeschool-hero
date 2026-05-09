"""lesson plans alias bridge

Revision ID: 20260510_001500
Revises: 20260510_001600
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic.
revision: str = '20260510_001500'
down_revision: Union[str, Sequence[str], None] = '20260510_001600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
