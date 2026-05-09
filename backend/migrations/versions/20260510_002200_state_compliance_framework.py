"""state compliance framework

Revision ID: 20260510_002202
Revises: 20260510_002100
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260510_002202'
down_revision: Union[str, Sequence[str], None] = '20260510_002100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLBACK_NOTES = """
- Downgrading removes family compliance state settings, seeded state rules, custom rules, and persisted compliance statuses.
- Export any family-specific compliance rules or dashboard snapshots before downgrade if that history must be preserved.
"""

compliance_rule_type = sa.Enum(
    'attendance_hours',
    'attendance_days',
    'subjects_required',
    'assessment_required',
    'notification_required',
    'portfolio_required',
    name='compliance_rule_type',
)
compliance_state = sa.Enum('compliant', 'warning', 'non_compliant', name='compliance_state')


def upgrade() -> None:
    bind = op.get_bind()
    compliance_rule_type.create(bind, checkfirst=True)
    compliance_state.create(bind, checkfirst=True)

    with op.batch_alter_table('family_settings') as batch:
        batch.add_column(sa.Column('state_code', sa.String(length=8), nullable=False, server_default='CUSTOM'))

    op.create_table(
        'compliance_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=True),
        sa.Column('state_code', sa.String(length=8), nullable=False),
        sa.Column('rule_type', compliance_rule_type, nullable=False),
        sa.Column('rule_name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('threshold_value', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('threshold_unit', sa.String(length=32), nullable=False, server_default='count'),
        sa.Column('subjects_list', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_compliance_rules_family_id_families'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_compliance_rules')),
        sa.UniqueConstraint('family_id', 'state_code', 'rule_name', name='uq_compliance_rules_family_state_name'),
    )
    with op.batch_alter_table('compliance_rules') as batch:
        batch.create_index(op.f('ix_compliance_rules_id'), ['id'], unique=False)
        batch.create_index(op.f('ix_compliance_rules_family_id'), ['family_id'], unique=False)
        batch.create_index(op.f('ix_compliance_rules_state_code'), ['state_code'], unique=False)
        batch.create_index(op.f('ix_compliance_rules_rule_type'), ['rule_type'], unique=False)

    op.create_table(
        'compliance_statuses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('school_year_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('status', compliance_state, nullable=False, server_default='compliant'),
        sa.Column('current_value', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('required_value', sa.Numeric(8, 2), nullable=False, server_default='0'),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], name=op.f('fk_compliance_statuses_family_id_families'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_compliance_statuses_student_id_students'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], name=op.f('fk_compliance_statuses_school_year_id_school_years'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['compliance_rules.id'], name=op.f('fk_compliance_statuses_rule_id_compliance_rules'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_compliance_statuses')),
        sa.UniqueConstraint(
            'family_id',
            'student_id',
            'school_year_id',
            'rule_id',
            name='uq_compliance_statuses_family_student_year_rule',
        ),
    )
    with op.batch_alter_table('compliance_statuses') as batch:
        batch.create_index(op.f('ix_compliance_statuses_id'), ['id'], unique=False)
        batch.create_index(op.f('ix_compliance_statuses_family_id'), ['family_id'], unique=False)
        batch.create_index(op.f('ix_compliance_statuses_student_id'), ['student_id'], unique=False)
        batch.create_index(op.f('ix_compliance_statuses_school_year_id'), ['school_year_id'], unique=False)
        batch.create_index(op.f('ix_compliance_statuses_rule_id'), ['rule_id'], unique=False)
        batch.create_index(op.f('ix_compliance_statuses_status'), ['status'], unique=False)

    rules_table = sa.table(
        'compliance_rules',
        sa.column('family_id', sa.Integer()),
        sa.column('state_code', sa.String()),
        sa.column('rule_type', sa.String()),
        sa.column('rule_name', sa.String()),
        sa.column('description', sa.Text()),
        sa.column('threshold_value', sa.Numeric(8, 2)),
        sa.column('threshold_unit', sa.String()),
        sa.column('subjects_list', sa.JSON()),
        sa.column('is_active', sa.Boolean()),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        rules_table,
        [
            {
                'family_id': None,
                'state_code': 'TX',
                'rule_type': 'attendance_days',
                'rule_name': 'Texas minimum instructional days',
                'description': 'Texas families should record at least 180 instructional attendance days each school year.',
                'threshold_value': 180,
                'threshold_unit': 'days',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'TX',
                'rule_type': 'subjects_required',
                'rule_name': 'Texas core subjects',
                'description': 'Texas records should show math, reading, spelling, grammar, and citizenship in the curriculum.',
                'threshold_value': 5,
                'threshold_unit': 'count',
                'subjects_list': ['math', 'reading', 'spelling', 'grammar', 'citizenship'],
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'CA',
                'rule_type': 'attendance_days',
                'rule_name': 'California instructional days',
                'description': 'California private school style calendars typically target 175 instructional days.',
                'threshold_value': 175,
                'threshold_unit': 'days',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'CA',
                'rule_type': 'subjects_required',
                'rule_name': 'California subject coverage',
                'description': 'California records should cover language arts, mathematics, science, social studies, fine arts, health, and physical education.',
                'threshold_value': 7,
                'threshold_unit': 'count',
                'subjects_list': [
                    'english language arts',
                    'mathematics',
                    'science',
                    'social studies',
                    'fine arts',
                    'health',
                    'physical education',
                ],
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'VA',
                'rule_type': 'attendance_days',
                'rule_name': 'Virginia instructional days',
                'description': 'Virginia families should maintain 180 instructional attendance days.',
                'threshold_value': 180,
                'threshold_unit': 'days',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'VA',
                'rule_type': 'assessment_required',
                'rule_name': 'Virginia annual assessment',
                'description': 'Virginia homeschool families should maintain annual assessment evidence.',
                'threshold_value': 1,
                'threshold_unit': 'count',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'NY',
                'rule_type': 'attendance_days',
                'rule_name': 'New York instructional days',
                'description': 'New York homeschool records should show at least 180 instructional days.',
                'threshold_value': 180,
                'threshold_unit': 'days',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'NY',
                'rule_type': 'notification_required',
                'rule_name': 'New York quarterly reports',
                'description': 'New York families should keep four quarterly report records each school year.',
                'threshold_value': 4,
                'threshold_unit': 'count',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'NY',
                'rule_type': 'assessment_required',
                'rule_name': 'New York annual assessment',
                'description': 'New York families should retain one annual assessment or evaluation record.',
                'threshold_value': 1,
                'threshold_unit': 'count',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'FL',
                'rule_type': 'attendance_days',
                'rule_name': 'Florida instructional days',
                'description': 'Florida families typically target 180 instructional attendance days.',
                'threshold_value': 180,
                'threshold_unit': 'days',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
            {
                'family_id': None,
                'state_code': 'FL',
                'rule_type': 'assessment_required',
                'rule_name': 'Florida annual evaluation',
                'description': 'Florida homeschool programs should document one annual evaluation each school year.',
                'threshold_value': 1,
                'threshold_unit': 'count',
                'subjects_list': None,
                'is_active': True,
                'created_at': now,
                'updated_at': now,
            },
        ],
    )


def downgrade() -> None:
    with op.batch_alter_table('compliance_statuses') as batch:
        batch.drop_index(op.f('ix_compliance_statuses_status'))
        batch.drop_index(op.f('ix_compliance_statuses_rule_id'))
        batch.drop_index(op.f('ix_compliance_statuses_school_year_id'))
        batch.drop_index(op.f('ix_compliance_statuses_student_id'))
        batch.drop_index(op.f('ix_compliance_statuses_family_id'))
        batch.drop_index(op.f('ix_compliance_statuses_id'))
    op.drop_table('compliance_statuses')

    with op.batch_alter_table('compliance_rules') as batch:
        batch.drop_index(op.f('ix_compliance_rules_rule_type'))
        batch.drop_index(op.f('ix_compliance_rules_state_code'))
        batch.drop_index(op.f('ix_compliance_rules_family_id'))
        batch.drop_index(op.f('ix_compliance_rules_id'))
    op.drop_table('compliance_rules')

    with op.batch_alter_table('family_settings') as batch:
        batch.drop_column('state_code')

    bind = op.get_bind()
    compliance_state.drop(bind, checkfirst=True)
    compliance_rule_type.drop(bind, checkfirst=True)
