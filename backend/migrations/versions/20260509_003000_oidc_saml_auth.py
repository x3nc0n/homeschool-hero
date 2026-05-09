"""oidc saml auth support

Revision ID: 20260509_003000
Revises: 20260508_231600, 20260509_000100, 20260509_000500
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260509_003000'
down_revision: Union[str, Sequence[str], None] = ('20260508_231600', '20260509_000100', '20260509_000500')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() removes auth_provider and external_id columns from users and drops their index and unique constraint.
- Users who authenticated exclusively via OIDC or SAML will lose their auth link; ensure local passwords are set before rollback.
- No other table is affected.
"""


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('auth_provider', sa.String(length=32), nullable=False, server_default='local'))
        batch.add_column(sa.Column('external_id', sa.String(length=255), nullable=True))
        batch.create_index(op.f('ix_users_external_id'), ['external_id'], unique=False)
        batch.create_unique_constraint('uq_users_auth_provider_external_id', ['auth_provider', 'external_id'])


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('uq_users_auth_provider_external_id', type_='unique')
        batch.drop_index(op.f('ix_users_external_id'))
        batch.drop_column('external_id')
        batch.drop_column('auth_provider')
