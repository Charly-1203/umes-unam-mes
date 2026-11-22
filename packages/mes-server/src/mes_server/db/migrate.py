"""Programmatic access to the database migrations.

Migrations are managed with Alembic. This module lets the server apply them without an
``alembic.ini`` file, which is what ``mes-server db upgrade`` uses. Developers who create new
migrations use the Alembic command line with ``packages/mes-server/alembic.ini``.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from mes_server.db.engine import create_db_engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config(database_url: str) -> Config:
    """Build an Alembic configuration pointing at the bundled migrations.

    Args:
        database_url: SQLAlchemy URL of the database to migrate.

    Returns:
        The Alembic configuration.
    """
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    # Alembic interpolates "%" in option values, so it must be escaped.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    """Apply migrations up to ``revision``, creating the schema on an empty database.

    Args:
        database_url: SQLAlchemy URL of the database.
        revision: Target revision; ``"head"`` applies every migration.
    """
    command.upgrade(alembic_config(database_url), revision)


def head_revision() -> str | None:
    """Return the newest revision bundled with the code.

    Returns:
        The identifier of the latest migration.
    """
    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    return script.get_current_head()


def current_revision(database_url: str) -> str | None:
    """Return the revision the database is at.

    Args:
        database_url: SQLAlchemy URL of the database.

    Returns:
        The applied revision, or ``None`` if no migration has been applied.
    """
    engine = create_db_engine(database_url)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
