from pathlib import Path

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
