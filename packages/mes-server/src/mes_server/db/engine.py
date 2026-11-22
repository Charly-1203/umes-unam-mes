"""Database engine and session management."""

from collections.abc import Iterator
from contextlib import contextmanager
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """Turn on foreign key enforcement, which SQLite disables by default."""
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create a database engine configured for the MES.

    For SQLite the engine enforces foreign keys and allows use from several threads. An
    in-memory SQLite database shares a single connection so every session sees the same data.

    Args:
        database_url: SQLAlchemy URL of the database.
        echo: Log every SQL statement, useful when learning or debugging.

    Returns:
        The configured engine.
    """
    url = make_url(database_url)
    kwargs: dict[str, Any] = {"echo": echo}

    if url.get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool

    engine = create_engine(url, **kwargs)
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Open a session that commits on success and rolls back on error.

    Args:
        engine: Engine to bind the session to.

    Yields:
        The open session.
    """
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
