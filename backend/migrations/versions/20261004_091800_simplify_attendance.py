"""simplify attendance records to instructional days

Revision ID: 20261004_091800
Revises: 20260722_184240
Create Date: 2026-10-04
"""

from __future__ import annotations

from collections.abc import Sequence
from logging import getLogger
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20261004_091800'
down_revision: Union[str, Sequence[str], None] = '20260722_184240'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Attendance excuses and their database references are permanently removed; export attendance data and excuse documents before upgrading.
- Downgrade recreates an empty attendance_excuses table and cannot restore deleted excuse details or check-in/out times.
- Downgrade maps instructional days to present and non-instructional days to absent; hours that were left null are restored as zero.
"""


def upgrade() -> None:
    bind = op.get_bind()
    excuse_count = bind.execute(sa.text('SELECT COUNT(*) FROM attendance_excuses')).scalar_one()
    if excuse_count:
        getLogger('alembic.runtime.migration').warning(
            'Attendance migration will permanently remove %s attendance excuse record(s). Export attendance data and '
            'excuse documents before upgrading.',
            excuse_count,
        )

    op.drop_index(op.f('ix_attendance_excuses_approved_by_user_id'), table_name='attendance_excuses')
    op.drop_index(op.f('ix_attendance_excuses_attendance_record_id'), table_name='attendance_excuses')
    op.drop_index(op.f('ix_attendance_excuses_family_id'), table_name='attendance_excuses')
    op.drop_index(op.f('ix_attendance_excuses_id'), table_name='attendance_excuses')
    op.drop_table('attendance_excuses')

    op.add_column('attendance_records', sa.Column('is_instructional_day', sa.Boolean(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE attendance_records SET is_instructional_day = "
            "CASE WHEN status IN ('present', 'tardy') THEN true ELSE false END"
        )
    )
    op.drop_index(op.f('ix_attendance_records_status'), table_name='attendance_records')
    with op.batch_alter_table('attendance_records') as batch_op:
        batch_op.alter_column(
            'is_instructional_day',
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        )
        batch_op.alter_column(
            'instructional_hours',
            existing_type=sa.Numeric(5, 2),
            nullable=True,
            server_default=None,
        )
        batch_op.drop_column('status')
        batch_op.drop_column('check_in_time')
        batch_op.drop_column('check_out_time')
    op.create_index(op.f('ix_attendance_records_is_instructional_day'), 'attendance_records', ['is_instructional_day'])

    if bind.dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS attendance_status')


def downgrade() -> None:
    bind = op.get_bind()
    attendance_status = postgresql.ENUM(
        'present',
        'absent',
        'tardy',
        'excused',
        name='attendance_status',
        create_type=False,
    )
    if bind.dialect.name == 'postgresql':
        attendance_status.create(bind, checkfirst=True)

    op.execute(sa.text('UPDATE attendance_records SET instructional_hours = 0 WHERE instructional_hours IS NULL'))
    op.drop_index(op.f('ix_attendance_records_is_instructional_day'), table_name='attendance_records')
    with op.batch_alter_table('attendance_records') as batch_op:
        batch_op.alter_column(
            'instructional_hours',
            existing_type=sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text('0'),
        )
        batch_op.add_column(sa.Column('status', attendance_status, nullable=True))
        batch_op.add_column(sa.Column('check_in_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('check_out_time', sa.Time(), nullable=True))
    status_expression = "CASE WHEN is_instructional_day THEN 'present' ELSE 'absent' END"
    if bind.dialect.name == 'postgresql':
        status_expression = f'({status_expression})::attendance_status'
    op.execute(
        sa.text(
            f'UPDATE attendance_records SET status = {status_expression}'
        )
    )
    with op.batch_alter_table('attendance_records') as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=attendance_status,
            nullable=False,
            server_default='present',
        )
        batch_op.drop_column('is_instructional_day')
    op.create_index(op.f('ix_attendance_records_status'), 'attendance_records', ['status'])

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
        sa.ForeignKeyConstraint(
            ['approved_by_user_id'],
            ['users.id'],
            name=op.f('fk_attendance_excuses_approved_by_user_id_users'),
            ondelete='SET NULL',
        ),
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
    op.create_index(
        op.f('ix_attendance_excuses_attendance_record_id'),
        'attendance_excuses',
        ['attendance_record_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_attendance_excuses_approved_by_user_id'),
        'attendance_excuses',
        ['approved_by_user_id'],
        unique=False,
    )
