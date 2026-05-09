"""merge parallel feature heads

Revision ID: 20260510_002300
Revises: 20260510_002201, 20260510_002202, 20260510_002203
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic.
revision: str = '20260510_002300'
down_revision: Union[str, Sequence[str], None] = ('20260510_002201', '20260510_002202', '20260510_002203')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading from this merge revision re-opens the parallel review, compliance, and gradebook feature heads.
- No schema objects are created or dropped directly by this merge revision.
"""


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
