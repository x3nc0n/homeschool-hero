import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from backend.startup import inspect_migration_status, lint_migration_scripts, verify_migration_cycle


def test_migration_lint_requires_filename_downgrade_and_notes(tmp_path: Path) -> None:
    versions_dir = tmp_path / 'versions'
    versions_dir.mkdir()
    (versions_dir / '__init__.py').write_text('', encoding='utf-8')
    (versions_dir / 'bad_name.py').write_text(
        'ROLLBACK_NOTES = """TODO: fill me"""\n\n'
        'def upgrade() -> None:\n    pass\n\n'
        'def downgrade() -> None:\n    pass\n',
        encoding='utf-8',
    )

    errors = lint_migration_scripts(versions_dir=versions_dir)

    assert 'bad_name.py: filename must follow YYYYMMDD_HHMMSS_slug.py' in errors
    assert 'bad_name.py: replace the ROLLBACK_NOTES TODO template before merge' in errors
    assert 'bad_name.py: downgrade() cannot be a no-op pass' in errors


def test_verify_migration_cycle_runs_upgrade_downgrade_upgrade(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr('backend.startup.lint_migration_scripts', lambda config=None: [])
    monkeypatch.setattr('backend.startup._upgrade_database', lambda config=None, revision='head': calls.append(('upgrade', revision)))
    monkeypatch.setattr('backend.startup.downgrade_database', lambda config=None, revision='-1': calls.append(('downgrade', revision)))

    verify_migration_cycle()

    assert calls == [('upgrade', 'head'), ('downgrade', '-1'), ('upgrade', 'head')]


def test_inspect_migration_status_reports_pending(monkeypatch) -> None:
    class _Revision:
        def __init__(self, revision: str) -> None:
            self.revision = revision

    class _ScriptDirectory:
        def walk_revisions(self):
            return [_Revision('20260508_224850'), _Revision('20260508_223000'), _Revision('20260508_170455')]

        def get_heads(self):
            return ('20260508_224850',)

    monkeypatch.setattr('backend.startup.build_alembic_config', lambda config=None: object())
    monkeypatch.setattr('backend.startup.ScriptDirectory.from_config', lambda config: _ScriptDirectory())

    def fake_asyncio_run(coro):
        coro.close()
        return ('20260508_223000',)

    monkeypatch.setattr('backend.startup.asyncio.run', fake_asyncio_run)

    status = inspect_migration_status()

    assert status.pending_revisions == ('20260508_224850',)


def test_inspect_migration_status_reports_ahead_revision(monkeypatch) -> None:
    class _Revision:
        def __init__(self, revision: str) -> None:
            self.revision = revision

    class _ScriptDirectory:
        def walk_revisions(self):
            return [_Revision('20260508_224850'), _Revision('20260508_223000'), _Revision('20260508_170455')]

        def get_heads(self):
            return ('20260508_224850',)

    monkeypatch.setattr('backend.startup.build_alembic_config', lambda config=None: object())
    monkeypatch.setattr('backend.startup.ScriptDirectory.from_config', lambda config: _ScriptDirectory())

    def fake_asyncio_run(coro):
        coro.close()
        return ('20260508_223000', 'future_revision')

    monkeypatch.setattr('backend.startup.asyncio.run', fake_asyncio_run)

    status = inspect_migration_status()

    assert status.ahead_revisions == ('future_revision',)


def test_api_tokens_migration_declares_reversible_downgrade() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / 'migrations'
        / 'versions'
        / '20260722_184240_api_tokens.py'
    )
    content = migration_path.read_text(encoding='utf-8')

    assert "op.create_table(" in content
    assert "'api_tokens'" in content
    assert "def downgrade()" in content
    assert "op.drop_table('api_tokens')" in content


def test_attendance_migration_preserves_records_and_maps_status_on_sqlite() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / 'migrations'
        / 'versions'
        / '20261004_091800_simplify_attendance.py'
    )
    spec = importlib.util.spec_from_file_location('attendance_migration', migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE families (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('CREATE TABLE students (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql(
            "CREATE TABLE attendance_records ("
            "id INTEGER PRIMARY KEY, family_id INTEGER NOT NULL, student_id INTEGER NOT NULL, date DATE NOT NULL, "
            "status VARCHAR(7) NOT NULL DEFAULT 'present', check_in_time TIME, check_out_time TIME, "
            "instructional_hours NUMERIC(5,2) NOT NULL DEFAULT 0, notes TEXT, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY(family_id) REFERENCES families(id) ON DELETE CASCADE, "
            "FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE, "
            "UNIQUE(family_id, student_id, date))"
        )
        connection.exec_driver_sql('CREATE INDEX ix_attendance_records_id ON attendance_records (id)')
        connection.exec_driver_sql('CREATE INDEX ix_attendance_records_family_id ON attendance_records (family_id)')
        connection.exec_driver_sql('CREATE INDEX ix_attendance_records_student_id ON attendance_records (student_id)')
        connection.exec_driver_sql('CREATE INDEX ix_attendance_records_date ON attendance_records (date)')
        connection.exec_driver_sql('CREATE INDEX ix_attendance_records_status ON attendance_records (status)')
        connection.exec_driver_sql(
            "CREATE TABLE attendance_excuses ("
            "id INTEGER PRIMARY KEY, family_id INTEGER NOT NULL, attendance_record_id INTEGER NOT NULL, "
            "reason VARCHAR(255) NOT NULL, document_path TEXT, approved_by_user_id INTEGER, approved_at DATETIME, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY(family_id) REFERENCES families(id) ON DELETE CASCADE, "
            "FOREIGN KEY(attendance_record_id) REFERENCES attendance_records(id) ON DELETE CASCADE, "
            "FOREIGN KEY(approved_by_user_id) REFERENCES users(id) ON DELETE SET NULL, "
            "UNIQUE(attendance_record_id))"
        )
        connection.exec_driver_sql('CREATE INDEX ix_attendance_excuses_id ON attendance_excuses (id)')
        connection.exec_driver_sql('CREATE INDEX ix_attendance_excuses_family_id ON attendance_excuses (family_id)')
        connection.exec_driver_sql(
            'CREATE INDEX ix_attendance_excuses_attendance_record_id ON attendance_excuses (attendance_record_id)'
        )
        connection.exec_driver_sql(
            'CREATE INDEX ix_attendance_excuses_approved_by_user_id ON attendance_excuses (approved_by_user_id)'
        )
        connection.exec_driver_sql(
            "INSERT INTO attendance_records (id, family_id, student_id, date, status, instructional_hours) VALUES "
            "(1, 1, 1, '2026-01-01', 'present', 5), "
            "(2, 1, 1, '2026-01-02', 'tardy', 4), "
            "(3, 1, 1, '2026-01-03', 'absent', 0), "
            "(4, 1, 1, '2026-01-04', 'excused', 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO attendance_excuses (id, family_id, attendance_record_id, reason) VALUES (1, 1, 4, 'Doctor visit')"
        )

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        columns = {column['name'] for column in sa.inspect(connection).get_columns('attendance_records')}
        assert {'is_instructional_day', 'instructional_hours'} <= columns
        assert not {'status', 'check_in_time', 'check_out_time'} & columns
        migrated = connection.execute(
            sa.text('SELECT id, is_instructional_day, instructional_hours FROM attendance_records ORDER BY id')
        ).all()
        assert [bool(row.is_instructional_day) for row in migrated] == [True, True, False, False]
        assert [float(row.instructional_hours) for row in migrated] == [5.0, 4.0, 0.0, 0.0]
        assert 'attendance_excuses' not in sa.inspect(connection).get_table_names()
        connection.execute(sa.text('UPDATE attendance_records SET instructional_hours = NULL WHERE id = 4'))

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()

        restored = connection.execute(sa.text('SELECT id, status FROM attendance_records ORDER BY id')).all()
        assert [row.status for row in restored] == ['present', 'present', 'absent', 'absent']
        assert connection.execute(
            sa.text('SELECT instructional_hours FROM attendance_records WHERE id = 4')
        ).scalar_one() == 0
        assert sa.inspect(connection).get_table_names().count('attendance_excuses') == 1

    engine.dispose()


def test_curriculum_ai_import_sessions_migration_cycles_on_sqlite() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / 'migrations'
        / 'versions'
        / '20261008_105100_curriculum_ai_import_sessions.py'
    )
    spec = importlib.util.spec_from_file_location('ai_import_sessions_migration', migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == '20261006_172835'
    assert 'TODO' not in migration.ROLLBACK_NOTES

    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE families (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('CREATE TABLE imported_curricula (id INTEGER PRIMARY KEY)')
        migration.op = Operations(MigrationContext.configure(connection))
        for _ in range(2):
            migration.upgrade()
            inspector = sa.inspect(connection)
            assert 'curriculum_ai_import_sessions' in inspector.get_table_names()
            columns = {column['name'] for column in inspector.get_columns('curriculum_ai_import_sessions')}
            assert {
                'id', 'family_id', 'created_by_user_id', 'status', 'source_kind', 'source_name', 'warnings',
                'draft_payload', 'error_code', 'error_message', 'revision', 'expires_at', 'confirmed_at',
                'confirmed_curriculum_id', 'created_at', 'updated_at',
            } <= columns
            indexes = {index['name'] for index in inspector.get_indexes('curriculum_ai_import_sessions')}
            assert {'ix_curriculum_ai_import_sessions_family_status', 'ix_curriculum_ai_import_sessions_expires_at'} <= indexes
            migration.downgrade()
            assert 'curriculum_ai_import_sessions' not in sa.inspect(connection).get_table_names()
