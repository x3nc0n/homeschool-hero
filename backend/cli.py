from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import threading
from collections.abc import Sequence

from backend.services.backup_service import get_backup_scheduler, run_scheduled_backups, validate_backup_configuration
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

    backups = subparsers.add_parser('backups', help='Backup helpers')
    backup_commands = backups.add_subparsers(dest='backup_command', required=True)
    backup_commands.add_parser('once', help='Run scheduled backups immediately')
    backup_commands.add_parser('healthcheck', help='Validate backup destination configuration')
    backup_commands.add_parser('worker', help='Start the cron-based backup worker')

    return parser


def _print_status() -> None:
    status = inspect_migration_status()
    print(f'mode={status.mode}')
    print(f'current={", ".join(status.database_revisions) if status.database_revisions else "base"}')
    print(f'head={", ".join(status.head_revisions) if status.head_revisions else "base"}')
    print(f'pending={", ".join(status.pending_revisions) if status.pending_revisions else "none"}')
    print(f'ahead={", ".join(status.ahead_revisions) if status.ahead_revisions else "none"}')
    print(f'elapsed_seconds={status.elapsed_seconds:.3f}')


def _run_backup_worker() -> None:
    scheduler = get_backup_scheduler()
    scheduler.start()
    stop_event = threading.Event()

    def _handle_signal(_signum, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    try:
        while not stop_event.wait(1):
            pass
    finally:
        scheduler.stop()


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == 'migrations':
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
        elif args.command == 'backups':
            if args.backup_command == 'once':
                job_ids = asyncio.run(run_scheduled_backups())
                print(f'Backups completed for jobs: {", ".join(str(job_id) for job_id in job_ids) if job_ids else "none"}')
            elif args.backup_command == 'healthcheck':
                summary = validate_backup_configuration()
                print(summary['message'])
            elif args.backup_command == 'worker':
                _run_backup_worker()
            else:  # pragma: no cover - argparse guards this
                parser.error(f'Unsupported backups command: {args.backup_command}')
        else:
            parser.error(f'Unsupported command: {args.command}')
    except StartupValidationError as exc:
        print(str(exc))
        return 1
    except Exception as exc:  # pragma: no cover - CLI surface for Alembic/runtime exceptions
        print(f'Command failed: {exc}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
