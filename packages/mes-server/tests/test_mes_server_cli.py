import subprocess
import sys

import pytest

from mes_server import __version__
from mes_server.cli import display_url, main
from mes_server.db import migrate


def test_main_without_arguments_prints_name_and_version(capsys):
    assert main([]) == 0
    assert capsys.readouterr().out.strip() == f"mes-server {__version__}"


def test_version_flag_prints_version_and_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"mes-server {__version__}"


def test_unknown_argument_is_rejected():
    with pytest.raises(SystemExit) as exc:
        main(["--not-an-option"])
    assert exc.value.code == 2


def test_db_requires_an_action():
    with pytest.raises(SystemExit) as exc:
        main(["db"])
    assert exc.value.code == 2


def test_package_runs_as_module():
    result = subprocess.run(
        [sys.executable, "-m", "mes_server"], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == f"mes-server {__version__}"


def test_db_upgrade_creates_the_schema(file_db_url, capsys):
    assert main(["db", "upgrade", "--database-url", file_db_url]) == 0
    assert migrate.current_revision(file_db_url) == migrate.head_revision()
    assert migrate.head_revision() in capsys.readouterr().out


def test_db_upgrade_uses_environment_variable(file_db_url, monkeypatch):
    monkeypatch.setenv("MES_DATABASE_URL", file_db_url)
    assert main(["db", "upgrade"]) == 0
    assert migrate.current_revision(file_db_url) == migrate.head_revision()


def test_db_status_reports_out_of_date_schema(file_db_url, capsys):
    assert main(["db", "status", "--database-url", file_db_url]) == 1
    output = capsys.readouterr().out
    assert "Applied revision: none" in output
    assert "mes-server db upgrade" in output


def test_db_status_reports_up_to_date_schema(file_db_url, capsys):
    main(["db", "upgrade", "--database-url", file_db_url])
    capsys.readouterr()
    assert main(["db", "status", "--database-url", file_db_url]) == 0
    assert "out of date" not in capsys.readouterr().out


def test_display_url_hides_password():
    shown = display_url("postgresql://mes:secret@localhost/mes")
    assert "secret" not in shown
    assert "***" in shown


def test_display_url_keeps_sqlite_path():
    assert display_url("sqlite:///mes.db") == "sqlite:///mes.db"
