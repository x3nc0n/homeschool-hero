from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from backend.config import settings


def ensure_runtime_directories() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


def ensure_family_auth_configured() -> None:
    if settings.testing:
        return
    if not (settings.family_password_hash or settings.family_password):
        raise RuntimeError("Set FAMILY_PASSWORD or FAMILY_PASSWORD_HASH before starting Homeschool Hero.")


def run_migrations() -> None:
    alembic_ini = Path(__file__).resolve().with_name("alembic.ini")
    migrations_dir = Path(__file__).resolve().with_name("migrations")

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(migrations_dir))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


def bootstrap_application() -> None:
    ensure_runtime_directories()
    ensure_family_auth_configured()
    if not settings.testing:
        run_migrations()
