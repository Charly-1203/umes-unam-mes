import pytest
from sqlmodel import Session, SQLModel

import mes_server.db.models  # noqa: F401  (registers every table)
from mes_server.db import create_db_engine


@pytest.fixture
def engine():
    engine = create_db_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def file_db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'mes.db').as_posix()}"
