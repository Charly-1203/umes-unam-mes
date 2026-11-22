import pytest

from mes_server.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    ENV_DATABASE_URL,
    ENV_HOST,
    ENV_PORT,
    ENV_STORAGE_SECRET,
    Settings,
)


def test_defaults_when_environment_is_empty():
    settings = Settings.from_env({})
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT


def test_values_come_from_environment():
    settings = Settings.from_env(
        {
            ENV_DATABASE_URL: "sqlite:///other.db",
            ENV_HOST: "0.0.0.0",
            ENV_PORT: "9000",
            ENV_STORAGE_SECRET: "configured-secret",
        }
    )
    assert settings.database_url == "sqlite:///other.db"
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.storage_secret == "configured-secret"
    assert not settings.storage_secret_is_generated


def test_blank_variables_fall_back_to_defaults():
    settings = Settings.from_env({ENV_DATABASE_URL: "", ENV_HOST: "", ENV_PORT: ""})
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT


def test_missing_secret_is_generated_randomly():
    first, second = Settings.from_env({}), Settings.from_env({})
    assert first.storage_secret_is_generated
    assert len(first.storage_secret) >= 32
    assert first.storage_secret != second.storage_secret


def test_secret_is_not_shown_in_repr():
    assert "configured-secret" not in repr(
        Settings.from_env({ENV_STORAGE_SECRET: "configured-secret"})
    )


@pytest.mark.parametrize("value", ["abc", "0", "70000"])
def test_invalid_port_is_rejected(value):
    with pytest.raises(ValueError, match=ENV_PORT):
        Settings.from_env({ENV_PORT: value})


def test_reads_process_environment_by_default(monkeypatch):
    monkeypatch.setenv(ENV_DATABASE_URL, "sqlite:///from-process.db")
    assert Settings.from_env().database_url == "sqlite:///from-process.db"
