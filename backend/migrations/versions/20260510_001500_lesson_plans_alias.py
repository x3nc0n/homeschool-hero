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

ROLLBACK_NOTES = """
- This is a bridge/alias revision that introduces no schema changes.
- downgrade() is a deliberate no-op return; no schema objects are created or destroyed by this revision.
"""


def upgrade() -> None:
    pass


def downgrade() -> None:
    # Bridge migration: no schema changes were introduced; nothing to reverse.
    return
