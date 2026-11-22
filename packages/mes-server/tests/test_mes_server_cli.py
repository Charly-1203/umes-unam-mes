import subprocess
import sys

import pytest
from sqlmodel import Session, select

from mes_server import __version__
from mes_server.cli import display_url, main
from mes_server.db import create_db_engine, migrate
from mes_server.db.models import User


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


# ---------------------------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------------------------
def answers(*values):
    remaining = list(values)
    return lambda _prompt: remaining.pop(0)


@pytest.fixture
def upgraded_db(file_db_url):
    migrate.upgrade(file_db_url)
    return file_db_url


def test_create_admin_creates_an_administrator(upgraded_db, capsys):
    code = main(
        ["users", "create-admin", "--database-url", upgraded_db],
        prompt=answers("secret123", "secret123"),
    )
    assert code == 0
    assert "User 'admin' created with role 'admin'." in capsys.readouterr().out
    main(["users", "list", "--database-url", upgraded_db])
    assert "admin" in capsys.readouterr().out


def test_create_admin_accepts_a_custom_username(upgraded_db, capsys):
    main(
        ["users", "create-admin", "--database-url", upgraded_db, "--username", "Root.User"],
        prompt=answers("secret123", "secret123"),
    )
    assert "User 'root.user' created" in capsys.readouterr().out


def test_create_user_with_a_role(upgraded_db, capsys):
    code = main(
        [
            "users", "create", "--database-url", upgraded_db,
            "--username", "op1", "--full-name", "Operator One", "--role", "operator",
        ],
        prompt=answers("secret123", "secret123"),
    )  # fmt: skip
    assert code == 0
    main(["users", "list", "--database-url", upgraded_db])
    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("op1"))
    assert "operator" in line
    assert "Operator One" in line


def test_create_user_rejects_unknown_role(upgraded_db):
    with pytest.raises(SystemExit):
        main(
            [
                "users", "create", "--database-url", upgraded_db,
                "--username", "x1", "--full-name", "X", "--role", "superuser",
            ]
        )  # fmt: skip


def test_mismatched_passwords_are_rejected(upgraded_db, capsys):
    code = main(
        ["users", "create-admin", "--database-url", upgraded_db],
        prompt=answers("secret123", "different1"),
    )
    assert code == 1
    assert "do not match" in capsys.readouterr().err


def test_weak_password_is_reported(upgraded_db, capsys):
    code = main(
        ["users", "create-admin", "--database-url", upgraded_db], prompt=answers("short", "short")
    )
    assert code == 1
    assert "at least" in capsys.readouterr().err


def test_duplicate_user_is_reported(upgraded_db, capsys):
    args = ["users", "create-admin", "--database-url", upgraded_db]
    main(args, prompt=answers("secret123", "secret123"))
    assert main(args, prompt=answers("secret123", "secret123")) == 1
    assert "already exists" in capsys.readouterr().err


def test_users_commands_require_an_up_to_date_schema(file_db_url, capsys):
    assert main(["users", "list", "--database-url", file_db_url]) == 1
    assert "mes-server db upgrade" in capsys.readouterr().err


def test_inactive_users_are_listed_as_inactive(upgraded_db, capsys):
    main(
        ["users", "create-admin", "--database-url", upgraded_db],
        prompt=answers("secret123", "secret123"),
    )
    engine = create_db_engine(upgraded_db)
    with Session(engine) as session:
        user = session.exec(select(User)).one()
        user.is_active = False
        session.commit()
    engine.dispose()
    capsys.readouterr()
    main(["users", "list", "--database-url", upgraded_db])
    assert "inactive" in capsys.readouterr().out


# ---------------------------------------------------------------------------------------------
# backup and course
# ---------------------------------------------------------------------------------------------
def seed_order(url):
    from mes_server.db.models import Product, WorkOrder

    engine = create_db_engine(url)
    with Session(engine) as session:
        product = Product(code="P-1", name="Producto")
        session.add(product)
        session.flush()
        session.add(WorkOrder(order_number="WO-1", product_id=product.id, quantity=1))
        session.commit()
    engine.dispose()


def count_orders(url):
    from mes_server.db.models import WorkOrder

    engine = create_db_engine(url)
    with Session(engine) as session:
        total = len(session.exec(select(WorkOrder)).all())
    engine.dispose()
    return total


def test_backup_create_and_list(upgraded_db, tmp_path, capsys):
    assert main(["backup", "create", "--database-url", upgraded_db]) == 0
    assert "Backup created" in capsys.readouterr().out
    assert len(list((tmp_path / "respaldos").glob("*.db"))) == 1
    assert main(["backup", "list", "--database-url", upgraded_db]) == 0
    assert "terminal" in capsys.readouterr().out


def test_backup_dir_can_be_configured(upgraded_db, tmp_path, monkeypatch):
    monkeypatch.setenv("MES_BACKUP_DIR", str(tmp_path / "otra"))
    main(["backup", "create", "--database-url", upgraded_db])
    assert len(list((tmp_path / "otra").glob("*.db"))) == 1


def test_backup_requires_a_sqlite_file(capsys):
    assert main(["backup", "create", "--database-url", "sqlite://"]) == 1
    assert "only available" in capsys.readouterr().err


def test_backup_requires_an_up_to_date_schema(file_db_url, capsys):
    assert main(["backup", "create", "--database-url", file_db_url]) == 1


def test_course_reset_asks_for_confirmation(upgraded_db, tmp_path, capsys):
    seed_order(upgraded_db)
    code = main(
        ["course", "reset", "--database-url", upgraded_db, "--level", "production"],
        ask=lambda _prompt: "REINICIAR",
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "1 work_orders" in output
    assert "Course reset complete." in output
    assert count_orders(upgraded_db) == 0
    assert len(list((tmp_path / "respaldos").glob("*.db"))) == 1


def test_course_reset_aborts_without_the_word(upgraded_db, capsys):
    seed_order(upgraded_db)
    code = main(
        ["course", "reset", "--database-url", upgraded_db, "--level", "everything"],
        ask=lambda _prompt: "no",
    )
    assert code == 1
    assert "Nothing was deleted" in capsys.readouterr().err
    assert count_orders(upgraded_db) == 1


def test_course_reset_with_yes_skips_the_question(upgraded_db):
    seed_order(upgraded_db)

    def fail(_prompt):
        raise AssertionError("should not ask")

    assert (
        main(
            ["course", "reset", "--database-url", upgraded_db, "--level", "catalogs", "--yes"],
            ask=fail,
        )
        == 0
    )
    assert count_orders(upgraded_db) == 0


def test_course_reset_requires_a_valid_level(upgraded_db):
    with pytest.raises(SystemExit):
        main(["course", "reset", "--database-url", upgraded_db, "--level", "all"])
