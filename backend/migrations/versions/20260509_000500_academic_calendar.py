"""academic calendar

Revision ID: 20260509_000500
Revises: 20260508_224850
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260509_000500'
down_revision: Union[str, None] = '20260508_224850'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- downgrade() drops calendar_events, grading_periods, terms, and school_years tables, plus the
  term_type and calendar_event_type enum types.
- All academic calendar data will be permanently lost; export before rolling back.
- Tables are removed in reverse dependency order to satisfy foreign-key constraints.
"""

term_type = postgresql.ENUM('semester', 'quarter', 'trimester', 'custom', name='term_type', create_type=False)
calendar_event_type = postgresql.ENUM('holiday', 'closure', 'custom', name='calendar_event_type', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    term_type.create(bind, checkfirst=True)
    calendar_event_type.create(bind, checkfirst=True)

    op.create_table(
        'school_years',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_school_years_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_school_years')),
        sa.UniqueConstraint('family_id', 'name', name='uq_school_years_family_id_name'),
    )
    op.create_index(op.f('ix_school_years_id'), 'school_years', ['id'], unique=False)
    op.create_index(op.f('ix_school_years_family_id'), 'school_years', ['family_id'], unique=False)

    op.create_table(
        'terms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('term_type', term_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_terms_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], name=op.f('fk_terms_school_year_id_school_years'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_terms')),
        sa.UniqueConstraint('school_year_id', 'name', name='uq_terms_school_year_id_name'),
    )
    op.create_index(op.f('ix_terms_id'), 'terms', ['id'], unique=False)
    op.create_index(op.f('ix_terms_school_year_id'), 'terms', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_terms_family_id'), 'terms', ['family_id'], unique=False)

    op.create_table(
        'grading_periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('term_id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_grading_periods_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], name=op.f('fk_grading_periods_term_id_terms'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_grading_periods')),
        sa.UniqueConstraint('term_id', 'name', name='uq_grading_periods_term_id_name'),
    )
    op.create_index(op.f('ix_grading_periods_id'), 'grading_periods', ['id'], unique=False)
    op.create_index(op.f('ix_grading_periods_term_id'), 'grading_periods', ['term_id'], unique=False)
    op.create_index(op.f('ix_grading_periods_family_id'), 'grading_periods', ['family_id'], unique=False)

    op.create_table(
        'calendar_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('event_type', calendar_event_type, nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('is_instructional_day', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_calendar_events_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['school_year_id'],
            ['school_years.id'],
            name=op.f('fk_calendar_events_school_year_id_school_years'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_calendar_events')),
    )
    op.create_index(op.f('ix_calendar_events_id'), 'calendar_events', ['id'], unique=False)
    op.create_index(op.f('ix_calendar_events_family_id'), 'calendar_events', ['family_id'], unique=False)
    op.create_index(op.f('ix_calendar_events_school_year_id'), 'calendar_events', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_calendar_events_date'), 'calendar_events', ['date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_calendar_events_date'), table_name='calendar_events')
    op.drop_index(op.f('ix_calendar_events_school_year_id'), table_name='calendar_events')
    op.drop_index(op.f('ix_calendar_events_family_id'), table_name='calendar_events')
    op.drop_index(op.f('ix_calendar_events_id'), table_name='calendar_events')
    op.drop_table('calendar_events')

    op.drop_index(op.f('ix_grading_periods_family_id'), table_name='grading_periods')
    op.drop_index(op.f('ix_grading_periods_term_id'), table_name='grading_periods')
    op.drop_index(op.f('ix_grading_periods_id'), table_name='grading_periods')
    op.drop_table('grading_periods')

    op.drop_index(op.f('ix_terms_family_id'), table_name='terms')
    op.drop_index(op.f('ix_terms_school_year_id'), table_name='terms')
    op.drop_index(op.f('ix_terms_id'), table_name='terms')
    op.drop_table('terms')

    op.drop_index(op.f('ix_school_years_family_id'), table_name='school_years')
    op.drop_index(op.f('ix_school_years_id'), table_name='school_years')
    op.drop_table('school_years')

    bind = op.get_bind()
    calendar_event_type.drop(bind, checkfirst=True)
    term_type.drop(bind, checkfirst=True)
