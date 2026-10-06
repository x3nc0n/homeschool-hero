"""add processing status for async assignment imports

Revision ID: 20261006_172835
Revises: 20261006_101308
Create Date: 2026-10-06T17:28:35-05:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = '20261006_172835'
down_revision: Union[str, Sequence[str], None] = '20261006_101308'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() maps any in-flight async bulk assignment imports from processing to failed.
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TYPE bulk_assignment_import_status ADD VALUE IF NOT EXISTS 'processing'")


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        sa.text(
            "UPDATE bulk_assignment_import_sessions "
            "SET status = 'failed' "
            "WHERE status = 'processing'"
        )
    )
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TYPE bulk_assignment_import_status RENAME TO bulk_assignment_import_status_old")
        op.execute(
            "CREATE TYPE bulk_assignment_import_status AS ENUM "
            "('draft', 'needs_clarification', 'ready', 'confirmed', 'expired', 'failed')"
        )
        op.execute(
            "ALTER TABLE bulk_assignment_import_sessions "
            "ALTER COLUMN status DROP DEFAULT, "
            "ALTER COLUMN status TYPE bulk_assignment_import_status "
            "USING status::text::bulk_assignment_import_status, "
            "ALTER COLUMN status SET DEFAULT 'draft'"
        )
        op.execute('DROP TYPE bulk_assignment_import_status_old')
