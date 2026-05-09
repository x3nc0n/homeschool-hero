"""rbac invitation student scope

Revision ID: 20260508_224850
Revises: 20260508_223000
Create Date: 2026-05-08
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260508_224850'
down_revision: Union[str, None] = '20260508_223000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('family_memberships') as batch:
        batch.add_column(sa.Column('student_id', sa.Integer(), nullable=True))
        batch.create_index(op.f('ix_family_memberships_student_id'), ['student_id'], unique=False)
        batch.create_foreign_key(
            op.f('fk_family_memberships_student_id_students'),
            'students',
            ['student_id'],
            ['id'],
            ondelete='SET NULL',
        )

    with op.batch_alter_table('invitations') as batch:
        batch.add_column(sa.Column('student_id', sa.Integer(), nullable=True))
        batch.create_index(op.f('ix_invitations_student_id'), ['student_id'], unique=False)
        batch.create_foreign_key(
            op.f('fk_invitations_student_id_students'),
            'students',
            ['student_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('invitations') as batch:
        batch.drop_constraint(op.f('fk_invitations_student_id_students'), type_='foreignkey')
        batch.drop_index(op.f('ix_invitations_student_id'))
        batch.drop_column('student_id')

    with op.batch_alter_table('family_memberships') as batch:
        batch.drop_constraint(op.f('fk_family_memberships_student_id_students'), type_='foreignkey')
        batch.drop_index(op.f('ix_family_memberships_student_id'))
        batch.drop_column('student_id')
