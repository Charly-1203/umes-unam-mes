"""Runtime configuration of the MES server.

Settings come from environment variables so the same code runs on a developer laptop, on the
laboratory server and in tests without editing files.

| Variable           | Default             | Meaning                         |
|--------------------|---------------------|---------------------------------|
| ``MES_DATABASE_URL`` | ``sqlite:///mes.db`` | SQLAlchemy URL of the database |
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

ENV_DATABASE_URL = "MES_DATABASE_URL"
DEFAULT_DATABASE_URL = "sqlite:///mes.db"
"""SQLite file named ``mes.db`` in the current working directory."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Server settings.

    Attributes:
        database_url: SQLAlchemy URL of the database.
    """

    database_url: str = DEFAULT_DATABASE_URL

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Read the settings from environment variables.

        Args:
            environ: Variables to read. ``None`` uses the process environment.

        Returns:
            The settings, with defaults for anything not defined.
        """
        env = os.environ if environ is None else environ
        return cls(database_url=env.get(ENV_DATABASE_URL) or DEFAULT_DATABASE_URL)
