"""multi-family identity and tenancy

Revision ID: 20260508_223000
Revises: 20260508_170455
Create Date: 2026-05-08
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Union

import bcrypt
import sqlalchemy as sa
from alembic import op

from backend.config import settings

# revision identifiers, used by Alembic.
revision: str = '20260508_223000'
down_revision: Union[str, None] = '20260508_170455'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

family_role = sa.Enum('parent', 'co-parent', 'tutor', 'student_viewer', name='family_role')


def _hash_legacy_password() -> str:
    if settings.legacy_family_password_hash:
        return settings.legacy_family_password_hash
    return bcrypt.hashpw(settings.legacy_family_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _add_family_column(table_name: str, family_id: int) -> None:
    op.add_column(table_name, sa.Column('family_id', sa.Integer(), nullable=True))
    op.execute(sa.text(f'UPDATE {table_name} SET family_id = :family_id').bindparams(family_id=family_id))


def upgrade() -> None:
    bind = op.get_bind()
    family_role.create(bind, checkfirst=True)

    families = op.create_table(
        'families',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_families')),
    )
    op.create_index(op.f('ix_families_id'), 'families', ['id'], unique=False)

    users = op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=160), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)

    op.create_table(
        'family_settings',
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=False),
        sa.Column('grading_scale', sa.String(length=64), server_default='letter', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_family_settings_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('family_id', name=op.f('pk_family_settings')),
    )

    op.create_table(
        'family_memberships',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('role', family_role, nullable=False),
        sa.Column('is_owner', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('invited_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_family_memberships_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_family_memberships_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'family_id', name=op.f('pk_family_memberships')),
    )
    op.create_index(op.f('ix_family_memberships_family_id'), 'family_memberships', ['family_id'], unique=False)

    op.create_table(
        'invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', family_role, nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_invitations_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_invitations')),
        sa.UniqueConstraint('token', name=op.f('uq_invitations_token')),
    )
    op.create_index(op.f('ix_invitations_id'), 'invitations', ['id'], unique=False)
    op.create_index(op.f('ix_invitations_family_id'), 'invitations', ['family_id'], unique=False)
    op.create_index(op.f('ix_invitations_email'), 'invitations', ['email'], unique=False)
    op.create_index(op.f('ix_invitations_token'), 'invitations', ['token'], unique=False)

    bind.execute(
        sa.insert(families).values(
            name=settings.bootstrap_family_name,
            settings={'timezone': settings.bootstrap_timezone, 'grading_scale': settings.bootstrap_grading_scale},
        )
    )
    family_id = bind.execute(sa.select(families.c.id).order_by(families.c.id)).scalar_one()
    now = dt.datetime.now(dt.timezone.utc)
    bind.execute(
        sa.insert(users).values(
            email=settings.bootstrap_owner_email.strip().lower(),
            display_name=settings.bootstrap_owner_display_name,
            password_hash=_hash_legacy_password(),
            is_active=True,
        )
    )
    user_id = bind.execute(sa.select(users.c.id).order_by(users.c.id)).scalar_one()
    bind.execute(
        sa.text(
            'INSERT INTO family_settings (family_id, timezone, grading_scale, created_at, updated_at) '
            'VALUES (:family_id, :timezone, :grading_scale, :created_at, :updated_at)'
        ),
        {
            'family_id': family_id,
            'timezone': settings.bootstrap_timezone,
            'grading_scale': settings.bootstrap_grading_scale,
            'created_at': now,
            'updated_at': now,
        },
    )
    bind.execute(
        sa.text(
            'INSERT INTO family_memberships (user_id, family_id, role, is_owner, invited_at, accepted_at) '
            'VALUES (:user_id, :family_id, :role, :is_owner, :invited_at, :accepted_at)'
        ),
        {
            'user_id': user_id,
            'family_id': family_id,
            'role': 'parent',
            'is_owner': True,
            'invited_at': now,
            'accepted_at': now,
        },
    )

    for table_name in ('students', 'subjects', 'assignments', 'submissions', 'grades', 'quizzes', 'quiz_attempts', 'grading_jobs'):
        _add_family_column(table_name, family_id)

    with op.batch_alter_table('students') as batch:
        batch.drop_constraint(op.f('uq_students_name'), type_='unique')
        batch.alter_column('family_id', nullable=False)
        batch.create_foreign_key(op.f('fk_students_family_id_families'), 'families', ['family_id'], ['id'], ondelete='CASCADE')
        batch.create_index(op.f('ix_students_family_id'), ['family_id'], unique=False)
        batch.create_unique_constraint('uq_students_family_id_name', ['family_id', 'name'])

    with op.batch_alter_table('subjects') as batch:
        batch.drop_constraint(op.f('uq_subjects_name'), type_='unique')
        batch.alter_column('family_id', nullable=False)
        batch.create_foreign_key(op.f('fk_subjects_family_id_families'), 'families', ['family_id'], ['id'], ondelete='CASCADE')
        batch.create_index(op.f('ix_subjects_family_id'), ['family_id'], unique=False)
        batch.create_unique_constraint('uq_subjects_family_id_name', ['family_id', 'name'])

    for table_name in ('assignments', 'submissions', 'grades', 'quizzes', 'quiz_attempts', 'grading_jobs'):
        with op.batch_alter_table(table_name) as batch:
            batch.alter_column('family_id', nullable=False)
            batch.create_foreign_key(op.f(f'fk_{table_name}_family_id_families'), 'families', ['family_id'], ['id'], ondelete='CASCADE')
            batch.create_index(op.f(f'ix_{table_name}_family_id'), ['family_id'], unique=False)


def downgrade() -> None:
    for table_name in ('grading_jobs', 'quiz_attempts', 'quizzes', 'grades', 'submissions', 'assignments'):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_index(op.f(f'ix_{table_name}_family_id'))
            batch.drop_constraint(op.f(f'fk_{table_name}_family_id_families'), type_='foreignkey')
            batch.drop_column('family_id')

    with op.batch_alter_table('subjects') as batch:
        batch.drop_constraint('uq_subjects_family_id_name', type_='unique')
        batch.drop_index(op.f('ix_subjects_family_id'))
        batch.drop_constraint(op.f('fk_subjects_family_id_families'), type_='foreignkey')
        batch.drop_column('family_id')
        batch.create_unique_constraint(op.f('uq_subjects_name'), ['name'])

    with op.batch_alter_table('students') as batch:
        batch.drop_constraint('uq_students_family_id_name', type_='unique')
        batch.drop_index(op.f('ix_students_family_id'))
        batch.drop_constraint(op.f('fk_students_family_id_families'), type_='foreignkey')
        batch.drop_column('family_id')
        batch.create_unique_constraint(op.f('uq_students_name'), ['name'])

    op.drop_index(op.f('ix_invitations_token'), table_name='invitations')
    op.drop_index(op.f('ix_invitations_email'), table_name='invitations')
    op.drop_index(op.f('ix_invitations_family_id'), table_name='invitations')
    op.drop_index(op.f('ix_invitations_id'), table_name='invitations')
    op.drop_table('invitations')

    op.drop_index(op.f('ix_family_memberships_family_id'), table_name='family_memberships')
    op.drop_table('family_memberships')
    op.drop_table('family_settings')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')

    op.drop_index(op.f('ix_families_id'), table_name='families')
    op.drop_table('families')

    bind = op.get_bind()
    family_role.drop(bind, checkfirst=True)
