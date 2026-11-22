"""Runtime configuration of the MES server.

Settings come from environment variables so the same code runs on a developer laptop, on the
laboratory server and in tests without editing files.

| Variable             | Default             | Meaning                                       |
|----------------------|---------------------|-----------------------------------------------|
| ``MES_DATABASE_URL``   | ``sqlite:///mes.db`` | SQLAlchemy URL of the database               |
| ``MES_HOST``           | ``127.0.0.1``        | Address the web server listens on            |
| ``MES_PORT``           | ``8080``             | Port the web server listens on               |
| ``MES_STORAGE_SECRET`` | random per start     | Secret that signs the browser session cookie |
| ``MES_BACKUP_DIR``     | ``respaldos`` next to the database file | Folder for backups     |
"""

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

ENV_DATABASE_URL = "MES_DATABASE_URL"
ENV_HOST = "MES_HOST"
ENV_PORT = "MES_PORT"
ENV_STORAGE_SECRET = "MES_STORAGE_SECRET"
ENV_BACKUP_DIR = "MES_BACKUP_DIR"

DEFAULT_DATABASE_URL = "sqlite:///mes.db"
"""SQLite file named ``mes.db`` in the current working directory."""

DEFAULT_HOST = "127.0.0.1"
"""Only this computer. Use ``0.0.0.0`` to accept connections from the laboratory network."""

DEFAULT_PORT = 8080


def _generate_secret() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True, slots=True)
class Settings:
    """Server settings.

    Attributes:
        database_url: SQLAlchemy URL of the database.
        host: Address the web server listens on.
        port: Port the web server listens on.
        storage_secret: Secret that signs session cookies. When it is not configured a random
            one is generated, which signs every user out whenever the server restarts.
        storage_secret_is_generated: Whether ``storage_secret`` was generated at start-up.
        backup_dir: Folder for backups; ``None`` uses ``respaldos`` next to the database file.
    """

    database_url: str = DEFAULT_DATABASE_URL
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    storage_secret: str = field(default_factory=_generate_secret, repr=False)
    storage_secret_is_generated: bool = True
    backup_dir: Path | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Read the settings from environment variables.

        Args:
            environ: Variables to read. ``None`` uses the process environment.

        Returns:
            The settings, with defaults for anything not defined.

        Raises:
            ValueError: If ``MES_PORT`` is not a valid port number.
        """
        env = os.environ if environ is None else environ
        secret = env.get(ENV_STORAGE_SECRET) or ""
        return cls(
            database_url=env.get(ENV_DATABASE_URL) or DEFAULT_DATABASE_URL,
            host=env.get(ENV_HOST) or DEFAULT_HOST,
            port=_parse_port(env.get(ENV_PORT)),
            storage_secret=secret or _generate_secret(),
            storage_secret_is_generated=not secret,
            backup_dir=Path(env[ENV_BACKUP_DIR]) if env.get(ENV_BACKUP_DIR) else None,
        )

    def resolve_backup_dir(self, database_url: str | None = None) -> Path | None:
        """Return the folder for backups.

        Args:
            database_url: Database whose backups are meant; defaults to :attr:`database_url`.

        Returns:
            :attr:`backup_dir` when configured, otherwise ``respaldos`` next to the SQLite
            database file, or ``None`` when the database is not a SQLite file.
        """
        if self.backup_dir is not None:
            return self.backup_dir
        from mes_server.services.backups import default_backup_dir

        return default_backup_dir(database_url or self.database_url)


def _parse_port(value: str | None) -> int:
    if not value:
        return DEFAULT_PORT
    try:
        port = int(value)
    except ValueError:
        raise ValueError(f"{ENV_PORT} must be an integer, got '{value}'.") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"{ENV_PORT} must be between 1 and 65535, got {port}.")
    return port
