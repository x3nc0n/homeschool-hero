"""submission versioning and upload metadata

Revision ID: 20260510_001520
Revises: 20260510_000100
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_001520'
down_revision: Union[str, Sequence[str], None] = '20260510_000100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes submission version history metadata and deterministic storage metadata columns.
- Export current submission rows before downgrade if operators need file size/page count/version lineage preserved.
- Legacy submissions remain accessible after downgrade, but only the single-row submission shape survives.
"""


def upgrade() -> None:
    with op.batch_alter_table('submissions') as batch:
        batch.add_column(sa.Column('original_filename', sa.String(length=255), nullable=False, server_default='uploaded-file'))
        batch.add_column(sa.Column('file_name', sa.String(length=255), nullable=False, server_default='uploaded-file'))
        batch.add_column(sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('image_width', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('image_height', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('page_count', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('submission_version', sa.Integer(), nullable=False, server_default='1'))
        batch.add_column(sa.Column('parent_submission_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.create_index(op.f('ix_submissions_parent_submission_id'), ['parent_submission_id'], unique=False)
        batch.create_foreign_key(
            op.f('fk_submissions_parent_submission_id_submissions'),
            'submissions',
            ['parent_submission_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('submissions') as batch:
        batch.drop_constraint(op.f('fk_submissions_parent_submission_id_submissions'), type_='foreignkey')
        batch.drop_index(op.f('ix_submissions_parent_submission_id'))
        batch.drop_column('is_current')
        batch.drop_column('parent_submission_id')
        batch.drop_column('submission_version')
        batch.drop_column('page_count')
        batch.drop_column('image_height')
        batch.drop_column('image_width')
        batch.drop_column('file_size_bytes')
        batch.drop_column('file_name')
        batch.drop_column('original_filename')
