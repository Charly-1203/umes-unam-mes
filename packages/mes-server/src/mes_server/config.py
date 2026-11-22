"""Runtime configuration of the MES server.

Settings come from environment variables so the same code runs on a developer laptop, on the
laboratory server and in tests without editing files.

| Variable             | Default             | Meaning                                       |
|----------------------|---------------------|-----------------------------------------------|
| ``MES_DATABASE_URL``   | ``sqlite:///mes.db`` | SQLAlchemy URL of the database               |
| ``MES_HOST``           | ``127.0.0.1``        | Address the web server listens on            |
| ``MES_PORT``           | ``8080``             | Port the web server listens on               |
| ``MES_STORAGE_SECRET`` | random per start     | Secret that signs the browser session cookie |
"""

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field

ENV_DATABASE_URL = "MES_DATABASE_URL"
ENV_HOST = "MES_HOST"
ENV_PORT = "MES_PORT"
ENV_STORAGE_SECRET = "MES_STORAGE_SECRET"

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
    """

    database_url: str = DEFAULT_DATABASE_URL
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    storage_secret: str = field(default_factory=_generate_secret, repr=False)
    storage_secret_is_generated: bool = True

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
        )


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
