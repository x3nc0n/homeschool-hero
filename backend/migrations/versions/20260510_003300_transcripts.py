"""transcript generation and GPA tracking

Revision ID: 20260510_003300
Revises: 20260510_003000, 20260510_003200
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_003300'
down_revision: Union[str, Sequence[str], None] = ('20260510_003000', '20260510_003200')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes generated transcripts, transcript entries, and stored GPA totals.
- Export any finalized transcript PDFs before rollback if families need a permanent copy.
- Recreating transcripts after downgrade will require regenerating weighted flags and credit edits.
"""

transcript_status = postgresql.ENUM('draft', 'final', 'archived', name='transcript_status', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    transcript_status.create(bind, checkfirst=True)

    op.create_table(
        'transcripts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('generated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('status', transcript_status, nullable=False, server_default='draft'),
        sa.Column('cumulative_gpa', sa.Float(), nullable=True),
        sa.Column('weighted_gpa', sa.Float(), nullable=True),
        sa.Column('total_credits', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_transcripts_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['generated_by_user_id'], ['users.id'], name=op.f('fk_transcripts_generated_by_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_transcripts_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_transcripts')),
    )
    op.create_index(op.f('ix_transcripts_id'), 'transcripts', ['id'], unique=False)
    op.create_index(op.f('ix_transcripts_family_id'), 'transcripts', ['family_id'], unique=False)
    op.create_index(op.f('ix_transcripts_student_id'), 'transcripts', ['student_id'], unique=False)
    op.create_index(op.f('ix_transcripts_generated_at'), 'transcripts', ['generated_at'], unique=False)
    op.create_index(op.f('ix_transcripts_generated_by_user_id'), 'transcripts', ['generated_by_user_id'], unique=False)
    op.create_index(op.f('ix_transcripts_status'), 'transcripts', ['status'], unique=False)

    op.create_table(
        'transcript_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transcript_id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('subject_name', sa.String(length=120), nullable=False),
        sa.Column('credits', sa.Numeric(6, 2), nullable=False, server_default='1'),
        sa.Column('letter_grade', sa.String(length=4), nullable=True),
        sa.Column('gpa_points', sa.Float(), nullable=True),
        sa.Column('is_honors', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_ap', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], name=op.f('fk_transcript_entries_school_year_id_school_years'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_transcript_entries_subject_id_subjects'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], name=op.f('fk_transcript_entries_transcript_id_transcripts'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_transcript_entries')),
        sa.UniqueConstraint('transcript_id', 'school_year_id', 'subject_id', name='uq_transcript_entries_transcript_year_subject'),
    )
    op.create_index(op.f('ix_transcript_entries_id'), 'transcript_entries', ['id'], unique=False)
    op.create_index(op.f('ix_transcript_entries_transcript_id'), 'transcript_entries', ['transcript_id'], unique=False)
    op.create_index(op.f('ix_transcript_entries_school_year_id'), 'transcript_entries', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_transcript_entries_subject_id'), 'transcript_entries', ['subject_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_transcript_entries_subject_id'), table_name='transcript_entries')
    op.drop_index(op.f('ix_transcript_entries_school_year_id'), table_name='transcript_entries')
    op.drop_index(op.f('ix_transcript_entries_transcript_id'), table_name='transcript_entries')
    op.drop_index(op.f('ix_transcript_entries_id'), table_name='transcript_entries')
    op.drop_table('transcript_entries')

    op.drop_index(op.f('ix_transcripts_status'), table_name='transcripts')
    op.drop_index(op.f('ix_transcripts_generated_by_user_id'), table_name='transcripts')
    op.drop_index(op.f('ix_transcripts_generated_at'), table_name='transcripts')
    op.drop_index(op.f('ix_transcripts_student_id'), table_name='transcripts')
    op.drop_index(op.f('ix_transcripts_family_id'), table_name='transcripts')
    op.drop_index(op.f('ix_transcripts_id'), table_name='transcripts')
    op.drop_table('transcripts')

    bind = op.get_bind()
    transcript_status.drop(bind, checkfirst=True)
