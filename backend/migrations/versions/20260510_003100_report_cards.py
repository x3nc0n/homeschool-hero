"""report cards and progress reports

Revision ID: 20260510_003100
Revises: 20260510_002300
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_003100'
down_revision: Union[str, Sequence[str], None] = '20260510_002300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes generated report card records, subject entries, and their saved comments.
- Export any final PDFs families need to retain before rollback.
- Finalized report cards should be archived externally before running downgrade in production.
"""

report_card_status = postgresql.ENUM('draft', 'final', 'archived', name='report_card_status', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    report_card_status.create(bind, checkfirst=True)

    op.create_table(
        'report_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('grading_period_id', sa.Integer(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('generated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('status', report_card_status, nullable=False, server_default='draft'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_report_cards_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['generated_by_user_id'], ['users.id'], name=op.f('fk_report_cards_generated_by_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['grading_period_id'], ['grading_periods.id'], name=op.f('fk_report_cards_grading_period_id_grading_periods'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], name=op.f('fk_report_cards_school_year_id_school_years'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_report_cards_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_report_cards')),
    )
    op.create_index(op.f('ix_report_cards_id'), 'report_cards', ['id'], unique=False)
    op.create_index(op.f('ix_report_cards_family_id'), 'report_cards', ['family_id'], unique=False)
    op.create_index(op.f('ix_report_cards_student_id'), 'report_cards', ['student_id'], unique=False)
    op.create_index(op.f('ix_report_cards_school_year_id'), 'report_cards', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_report_cards_grading_period_id'), 'report_cards', ['grading_period_id'], unique=False)
    op.create_index(op.f('ix_report_cards_generated_at'), 'report_cards', ['generated_at'], unique=False)
    op.create_index(op.f('ix_report_cards_generated_by_user_id'), 'report_cards', ['generated_by_user_id'], unique=False)
    op.create_index(op.f('ix_report_cards_status'), 'report_cards', ['status'], unique=False)

    op.create_table(
        'report_card_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_card_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('letter_grade', sa.String(length=4), nullable=True),
        sa.Column('percentage', sa.Float(), nullable=True),
        sa.Column('gpa_points', sa.Float(), nullable=True),
        sa.Column('attendance_summary', sa.JSON(), nullable=False),
        sa.Column('teacher_comments', sa.Text(), nullable=True),
        sa.Column('category_breakdown', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['report_card_id'], ['report_cards.id'], name=op.f('fk_report_card_entries_report_card_id_report_cards'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_report_card_entries_subject_id_subjects'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_report_card_entries')),
        sa.UniqueConstraint('report_card_id', 'subject_id', name='uq_report_card_entries_report_subject'),
    )
    op.create_index(op.f('ix_report_card_entries_id'), 'report_card_entries', ['id'], unique=False)
    op.create_index(op.f('ix_report_card_entries_report_card_id'), 'report_card_entries', ['report_card_id'], unique=False)
    op.create_index(op.f('ix_report_card_entries_subject_id'), 'report_card_entries', ['subject_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_report_card_entries_subject_id'), table_name='report_card_entries')
    op.drop_index(op.f('ix_report_card_entries_report_card_id'), table_name='report_card_entries')
    op.drop_index(op.f('ix_report_card_entries_id'), table_name='report_card_entries')
    op.drop_table('report_card_entries')

    op.drop_index(op.f('ix_report_cards_status'), table_name='report_cards')
    op.drop_index(op.f('ix_report_cards_generated_by_user_id'), table_name='report_cards')
    op.drop_index(op.f('ix_report_cards_generated_at'), table_name='report_cards')
    op.drop_index(op.f('ix_report_cards_grading_period_id'), table_name='report_cards')
    op.drop_index(op.f('ix_report_cards_school_year_id'), table_name='report_cards')
    op.drop_index(op.f('ix_report_cards_student_id'), table_name='report_cards')
    op.drop_index(op.f('ix_report_cards_family_id'), table_name='report_cards')
    op.drop_index(op.f('ix_report_cards_id'), table_name='report_cards')
    op.drop_table('report_cards')

    bind = op.get_bind()
    report_card_status.drop(bind, checkfirst=True)
