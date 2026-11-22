from mes_server.config import DEFAULT_DATABASE_URL, ENV_DATABASE_URL, Settings


def test_defaults_when_environment_is_empty():
    assert Settings.from_env({}).database_url == DEFAULT_DATABASE_URL


def test_database_url_comes_from_environment():
    settings = Settings.from_env({ENV_DATABASE_URL: "sqlite:///other.db"})
    assert settings.database_url == "sqlite:///other.db"


def test_blank_variable_falls_back_to_default():
    assert Settings.from_env({ENV_DATABASE_URL: ""}).database_url == DEFAULT_DATABASE_URL


def test_reads_process_environment_by_default(monkeypatch):
    monkeypatch.setenv(ENV_DATABASE_URL, "sqlite:///from-process.db")
    assert Settings.from_env().database_url == "sqlite:///from-process.db"
