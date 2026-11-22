import pytest
from sqlalchemy import text
from sqlmodel import select

from mes_server.db import create_db_engine, session_scope
from mes_server.db.models import Station


def test_sqlite_foreign_keys_are_enabled(engine):
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_in_memory_database_is_shared_between_sessions(engine):
    with session_scope(engine) as session:
        session.add(Station(code="ST-10", name="Station 10"))
    with session_scope(engine) as session:
        assert session.exec(select(Station)).one().code == "ST-10"


def test_session_scope_commits_on_success(engine):
    with session_scope(engine) as session:
        session.add(Station(code="ST-20", name="Station 20"))
    with session_scope(engine) as session:
        assert len(session.exec(select(Station)).all()) == 1


def test_session_scope_rolls_back_on_error(engine):
    with pytest.raises(RuntimeError), session_scope(engine) as session:
        session.add(Station(code="ST-30", name="Station 30"))
        session.flush()
        raise RuntimeError("boom")
    with session_scope(engine) as session:
        assert session.exec(select(Station)).all() == []


def test_file_database_is_created_on_first_use(file_db_url, tmp_path):
    engine = create_db_engine(file_db_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()
    assert (tmp_path / "mes.db").exists()
