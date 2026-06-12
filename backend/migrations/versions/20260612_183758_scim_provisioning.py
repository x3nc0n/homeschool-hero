"""scim provisioning support

Revision ID: 20260612_183758
Revises: 20260612_174845
Create Date: 2026-06-12T18:37:58.792-05:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260612_183758'
down_revision: Union[str, Sequence[str], None] = '20260612_174845'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

family_role = postgresql.ENUM('parent', 'co-parent', 'tutor', 'student_viewer', name='family_role', create_type=False)


ROLLBACK_NOTES = """
- downgrade() drops the scim_groups table and removes users.scim_external_id.
- Existing users remain intact, but their Entra provisioning linkage is removed.
"""



def upgrade() -> None:
    bind = op.get_bind()
    family_role.create(bind, checkfirst=True)

    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('scim_external_id', sa.String(length=255), nullable=True))
        batch.create_unique_constraint('uq_users_scim_external_id', ['scim_external_id'])

    op.create_table(
        'scim_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('display_name', sa.String(length=160), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('role', family_role, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_scim_groups_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_scim_groups')),
        sa.UniqueConstraint('external_id', name=op.f('uq_scim_groups_external_id')),
        sa.UniqueConstraint('family_id', 'role', name='uq_scim_groups_family_role'),
    )
    op.create_index(op.f('ix_scim_groups_id'), 'scim_groups', ['id'], unique=False)
    op.create_index(op.f('ix_scim_groups_family_id'), 'scim_groups', ['family_id'], unique=False)



def downgrade() -> None:
    op.drop_index(op.f('ix_scim_groups_family_id'), table_name='scim_groups')
    op.drop_index(op.f('ix_scim_groups_id'), table_name='scim_groups')
    op.drop_table('scim_groups')

    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('uq_users_scim_external_id', type_='unique')
        batch.drop_column('scim_external_id')
