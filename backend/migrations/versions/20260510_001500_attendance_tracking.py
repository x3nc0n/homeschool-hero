"""attendance tracking

Revision ID: 20260510_001530
Revises: 20260510_000100
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_001530'
down_revision: Union[str, None] = '20260510_000100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

attendance_status = sa.Enum('present', 'absent', 'tardy', 'excused', name='attendance_status')


def upgrade() -> None:
    bind = op.get_bind()
    attendance_status.create(bind, checkfirst=True)

    op.create_table(
        'attendance_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('status', attendance_status, server_default='present', nullable=False),
        sa.Column('check_in_time', sa.Time(), nullable=True),
        sa.Column('check_out_time', sa.Time(), nullable=True),
        sa.Column('instructional_hours', sa.Numeric(5, 2), server_default=sa.text('0'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_attendance_records_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_attendance_records_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_attendance_records')),
        sa.UniqueConstraint('family_id', 'student_id', 'date', name='uq_attendance_records_family_student_date'),
    )
    op.create_index(op.f('ix_attendance_records_id'), 'attendance_records', ['id'], unique=False)
    op.create_index(op.f('ix_attendance_records_family_id'), 'attendance_records', ['family_id'], unique=False)
    op.create_index(op.f('ix_attendance_records_student_id'), 'attendance_records', ['student_id'], unique=False)
    op.create_index(op.f('ix_attendance_records_date'), 'attendance_records', ['date'], unique=False)
    op.create_index(op.f('ix_attendance_records_status'), 'attendance_records', ['status'], unique=False)

    op.create_table(
        'attendance_excuses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('attendance_record_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('document_path', sa.Text(), nullable=True),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], name=op.f('fk_attendance_excuses_approved_by_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(
            ['attendance_record_id'],
            ['attendance_records.id'],
            name=op.f('fk_attendance_excuses_attendance_record_id_attendance_records'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_attendance_excuses_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_attendance_excuses')),
        sa.UniqueConstraint('attendance_record_id', name='uq_attendance_excuses_attendance_record_id'),
    )
    op.create_index(op.f('ix_attendance_excuses_id'), 'attendance_excuses', ['id'], unique=False)
    op.create_index(op.f('ix_attendance_excuses_family_id'), 'attendance_excuses', ['family_id'], unique=False)
    op.create_index(op.f('ix_attendance_excuses_attendance_record_id'), 'attendance_excuses', ['attendance_record_id'], unique=False)
    op.create_index(op.f('ix_attendance_excuses_approved_by_user_id'), 'attendance_excuses', ['approved_by_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attendance_excuses_approved_by_user_id'), table_name='attendance_excuses')
    op.drop_index(op.f('ix_attendance_excuses_attendance_record_id'), table_name='attendance_excuses')
    op.drop_index(op.f('ix_attendance_excuses_family_id'), table_name='attendance_excuses')
    op.drop_index(op.f('ix_attendance_excuses_id'), table_name='attendance_excuses')
    op.drop_table('attendance_excuses')

    op.drop_index(op.f('ix_attendance_records_status'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_date'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_student_id'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_family_id'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_id'), table_name='attendance_records')
    op.drop_table('attendance_records')

    bind = op.get_bind()
    attendance_status.drop(bind, checkfirst=True)
