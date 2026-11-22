from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlmodel import SQLModel

from mes_server.db import create_db_engine, migrate


def test_bundled_migrations_have_a_single_head():
    assert migrate.head_revision() is not None


def test_new_database_has_no_revision(file_db_url):
    assert migrate.current_revision(file_db_url) is None


def test_upgrade_creates_every_model_table(file_db_url):
    migrate.upgrade(file_db_url)
    engine = create_db_engine(file_db_url)
    try:
        tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()
    assert tables == set(SQLModel.metadata.tables)


def test_upgrade_is_idempotent(file_db_url):
    migrate.upgrade(file_db_url)
    migrate.upgrade(file_db_url)
    assert migrate.current_revision(file_db_url) == migrate.head_revision()


def test_migrations_match_the_models(file_db_url):
    """Fails when a model changes without a matching migration."""
    migrate.upgrade(file_db_url)
    engine = create_db_engine(file_db_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            differences = compare_metadata(context, SQLModel.metadata)
    finally:
        engine.dispose()
    assert differences == []
