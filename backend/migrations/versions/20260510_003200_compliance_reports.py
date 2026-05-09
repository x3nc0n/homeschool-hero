"""state compliance reports

Revision ID: 20260510_003200
Revises: 20260510_003100
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_003200'
down_revision: Union[str, Sequence[str], None] = '20260510_003100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops the compliance_reports table and the compliance_report_type and compliance_report_status enum types.
- All compliance report data will be permanently lost; export reports before rolling back.
- Composite indexes are dropped before the table to avoid constraint conflicts.
"""

compliance_report_type = postgresql.ENUM(
    'annual_assessment',
    'quarterly_report',
    'notice_of_intent',
    'attendance_log',
    'portfolio_review',
    name='compliance_report_type',
create_type=False,
)
compliance_report_status = postgresql.ENUM('draft', 'final', 'submitted', name='compliance_report_status', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    compliance_report_type.create(bind, checkfirst=True)
    compliance_report_status.create(bind, checkfirst=True)

    op.create_table(
        'compliance_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('state_code', sa.String(length=8), nullable=False),
        sa.Column('report_type', compliance_report_type, nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('generated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('status', compliance_report_status, nullable=False, server_default='draft'),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_compliance_reports_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['generated_by_user_id'], ['users.id'], name=op.f('fk_compliance_reports_generated_by_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], name=op.f('fk_compliance_reports_school_year_id_school_years'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_compliance_reports_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_compliance_reports')),
    )
    op.create_index(op.f('ix_compliance_reports_id'), 'compliance_reports', ['id'], unique=False)
    op.create_index(op.f('ix_compliance_reports_family_id'), 'compliance_reports', ['family_id'], unique=False)
    op.create_index(op.f('ix_compliance_reports_student_id'), 'compliance_reports', ['student_id'], unique=False)
    op.create_index(op.f('ix_compliance_reports_school_year_id'), 'compliance_reports', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_compliance_reports_state_code'), 'compliance_reports', ['state_code'], unique=False)
    op.create_index(op.f('ix_compliance_reports_report_type'), 'compliance_reports', ['report_type'], unique=False)
    op.create_index(op.f('ix_compliance_reports_generated_at'), 'compliance_reports', ['generated_at'], unique=False)
    op.create_index(op.f('ix_compliance_reports_generated_by_user_id'), 'compliance_reports', ['generated_by_user_id'], unique=False)
    op.create_index(op.f('ix_compliance_reports_status'), 'compliance_reports', ['status'], unique=False)
    op.create_index('ix_compliance_reports_family_student_year', 'compliance_reports', ['family_id', 'student_id', 'school_year_id'], unique=False)
    op.create_index('ix_compliance_reports_state_type_status', 'compliance_reports', ['state_code', 'report_type', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_compliance_reports_state_type_status', table_name='compliance_reports')
    op.drop_index('ix_compliance_reports_family_student_year', table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_status'), table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_generated_by_user_id'), table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_generated_at'), table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_report_type'), table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_state_code'), table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_school_year_id'), table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_student_id'), table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_family_id'), table_name='compliance_reports')
    op.drop_index(op.f('ix_compliance_reports_id'), table_name='compliance_reports')
    op.drop_table('compliance_reports')

    bind = op.get_bind()
    compliance_report_status.drop(bind, checkfirst=True)
    compliance_report_type.drop(bind, checkfirst=True)
