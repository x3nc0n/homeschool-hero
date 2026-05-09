from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from backend.startup import (
    StartupValidationError,
    create_migration_revision,
    downgrade_database,
    ensure_database_migrations,
    inspect_migration_status,
    lint_migration_scripts,
    run_migrations,
    verify_migration_cycle,
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='python -m backend.cli', description='Homeschool Hero maintenance commands')
    subparsers = parser.add_subparsers(dest='command', required=True)

    migrations = subparsers.add_parser('migrations', help='Alembic migration helpers')
    migration_commands = migrations.add_subparsers(dest='migration_command', required=True)

    migration_commands.add_parser('status', help='Show current/head/pending revisions')

    upgrade = migration_commands.add_parser('upgrade', help='Upgrade database schema')
    upgrade.add_argument('revision', nargs='?', default='head')

    downgrade = migration_commands.add_parser('downgrade', help='Downgrade database schema')
    downgrade.add_argument('revision', nargs='?', default='-1')

    create = migration_commands.add_parser('create', help='Create a new migration file')
    create.add_argument('-m', '--message', required=True)
    create.add_argument('--autogenerate', action='store_true')

    migration_commands.add_parser('lint', help='Check migration rollback discipline and naming')
    migration_commands.add_parser('verify', help='Run lint, upgrade head, downgrade one revision, upgrade head')
    migration_commands.add_parser('startup-check', help='Run startup migration preflight/apply logic')

    return parser


def _print_status() -> None:
    status = inspect_migration_status()
    print(f'mode={status.mode}')
    print(f'current={", ".join(status.database_revisions) if status.database_revisions else "base"}')
    print(f'head={", ".join(status.head_revisions) if status.head_revisions else "base"}')
    print(f'pending={", ".join(status.pending_revisions) if status.pending_revisions else "none"}')
    print(f'ahead={", ".join(status.ahead_revisions) if status.ahead_revisions else "none"}')
    print(f'elapsed_seconds={status.elapsed_seconds:.3f}')


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command != 'migrations':
            parser.error(f'Unsupported command: {args.command}')
        if args.migration_command == 'status':
            _print_status()
        elif args.migration_command == 'upgrade':
            run_migrations(revision=args.revision)
        elif args.migration_command == 'downgrade':
            downgrade_database(revision=args.revision)
        elif args.migration_command == 'create':
            create_migration_revision(args.message, autogenerate=args.autogenerate)
        elif args.migration_command == 'lint':
            errors = lint_migration_scripts()
            if errors:
                raise StartupValidationError('Migration lint failed:\n- ' + '\n- '.join(errors))
            print('Migration lint passed.')
        elif args.migration_command == 'verify':
            verify_migration_cycle()
            print('Migration upgrade/downgrade cycle passed.')
        elif args.migration_command == 'startup-check':
            ensure_database_migrations()
            print('Startup migration check passed.')
        else:  # pragma: no cover - argparse guards this
            parser.error(f'Unsupported migrations command: {args.migration_command}')
    except StartupValidationError as exc:
        print(str(exc))
        return 1
    except Exception as exc:  # pragma: no cover - CLI surface for Alembic/runtime exceptions
        print(f'Command failed: {exc}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
