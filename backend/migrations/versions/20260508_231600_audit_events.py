"""audit events

Revision ID: 20260508_231600
Revises: 20260508_224850
Create Date: 2026-05-08
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260508_231600'
down_revision: Union[str, None] = '20260508_224850'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    audit_action = sa.Enum(
        'login',
        'logout',
        'role_change',
        'grade_create',
        'grade_update',
        'attendance_edit',
        'report_generate',
        'export',
        'restore',
        'config_change',
        'invitation_create',
        'invitation_accept',
        name='audit_action',
    )
    bind = op.get_bind()
    audit_action.create(bind, checkfirst=True)
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=False),
        sa.Column('action', audit_action, nullable=False),
        sa.Column('target_entity_type', sa.String(length=120), nullable=False),
        sa.Column('target_entity_id', sa.String(length=255), nullable=True),
        sa.Column('before_snapshot', sa.JSON(), nullable=True),
        sa.Column('after_snapshot', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_audit_events_actor_user_id_users')),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_audit_events_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events')),
    )
    with op.batch_alter_table('audit_events') as batch:
        batch.create_index(op.f('ix_audit_events_action'), ['action'], unique=False)
        batch.create_index(op.f('ix_audit_events_actor_user_id'), ['actor_user_id'], unique=False)
        batch.create_index(op.f('ix_audit_events_family_id'), ['family_id'], unique=False)
        batch.create_index(op.f('ix_audit_events_id'), ['id'], unique=False)
        batch.create_index(op.f('ix_audit_events_target_entity_id'), ['target_entity_id'], unique=False)
        batch.create_index(op.f('ix_audit_events_target_entity_type'), ['target_entity_type'], unique=False)
        batch.create_index(op.f('ix_audit_events_timestamp'), ['timestamp'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('audit_events') as batch:
        batch.drop_index(op.f('ix_audit_events_timestamp'))
        batch.drop_index(op.f('ix_audit_events_target_entity_type'))
        batch.drop_index(op.f('ix_audit_events_target_entity_id'))
        batch.drop_index(op.f('ix_audit_events_id'))
        batch.drop_index(op.f('ix_audit_events_family_id'))
        batch.drop_index(op.f('ix_audit_events_actor_user_id'))
        batch.drop_index(op.f('ix_audit_events_action'))
    op.drop_table('audit_events')
    sa.Enum(name='audit_action').drop(op.get_bind(), checkfirst=True)
