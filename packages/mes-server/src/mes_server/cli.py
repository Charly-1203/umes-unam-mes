"""Command-line entry point for ``mes-server``.

Commands:
    ``mes-server``                     Print the name and version.
    ``mes-server serve``               Start the web application.
    ``mes-server db upgrade``          Create or update the database schema.
    ``mes-server db status``           Show the applied and the latest schema revision.
    ``mes-server users create-admin``  Create an administrator, prompting for the password.
    ``mes-server users create``        Create a user with any role.
    ``mes-server users list``          List every user.
    ``mes-server backup create``       Make a backup of the database now.
    ``mes-server backup list``         List the backups.
    ``mes-server course reset``        Back up, then delete the data of a course.
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlmodel import Session

from mes_core.enums import Role
from mes_server import __version__
from mes_server.config import Settings
from mes_server.db import create_db_engine, migrate, session_scope
from mes_server.services import audit, backups, course_reset
from mes_server.services import users as user_service
from mes_server.services.course_reset import CONFIRMATION_WORD, ResetLevel
from mes_server.services.errors import ServiceError

PROG = "mes-server"
DESCRIPTION = "MES server: web application, REST API and persistence."

PasswordPrompt = Callable[[str], str]
Prompt = Callable[[str], str]


def display_url(database_url: str) -> str:
    """Render a database URL with its password hidden, safe to print.

    Args:
        database_url: SQLAlchemy URL.

    Returns:
        The URL with any password replaced by ``***``.
    """
    return make_url(database_url).render_as_string(hide_password=True)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the command-line interface.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(prog=PROG, description=DESCRIPTION)
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    url_help = "SQLAlchemy URL of the database. Defaults to $MES_DATABASE_URL or sqlite:///mes.db."

    serve = commands.add_parser("serve", help="Start the web application.")
    serve.add_argument("--database-url", help=url_help)
    serve.add_argument("--host", help="Address to listen on. Defaults to $MES_HOST or 127.0.0.1.")
    serve.add_argument("--port", type=int, help="Port to listen on. Defaults to $MES_PORT or 8080.")

    db = commands.add_parser("db", help="Manage the database schema.")
    db_commands = db.add_subparsers(dest="db_command", metavar="ACTION", required=True)
    upgrade = db_commands.add_parser("upgrade", help="Create or update the schema.")
    upgrade.add_argument("--database-url", help=url_help)
    upgrade.add_argument("--revision", default="head", help="Target revision (default: head).")
    status = db_commands.add_parser("status", help="Show the schema revision.")
    status.add_argument("--database-url", help=url_help)

    users = commands.add_parser("users", help="Manage users.")
    user_commands = users.add_subparsers(dest="users_command", metavar="ACTION", required=True)
    create_admin = user_commands.add_parser("create-admin", help="Create an administrator.")
    create_admin.add_argument("--database-url", help=url_help)
    create_admin.add_argument("--username", default="admin", help="Sign-in name (default: admin).")
    create_admin.add_argument("--full-name", default="Administrador", help="Name shown on screens.")
    create = user_commands.add_parser("create", help="Create a user with any role.")
    create.add_argument("--database-url", help=url_help)
    create.add_argument("--username", required=True, help="Sign-in name.")
    create.add_argument("--full-name", required=True, help="Name shown on screens.")
    create.add_argument("--role", required=True, choices=[role.value for role in Role])
    list_ = user_commands.add_parser("list", help="List every user.")
    list_.add_argument("--database-url", help=url_help)

    backup = commands.add_parser("backup", help="Back up the database.")
    backup_commands = backup.add_subparsers(dest="backup_command", metavar="ACTION", required=True)
    for name, text in (("create", "Make a backup now."), ("list", "List the backups.")):
        sub = backup_commands.add_parser(name, help=text)
        sub.add_argument("--database-url", help=url_help)

    course = commands.add_parser("course", help="Course administration.")
    course_commands = course.add_subparsers(dest="course_command", metavar="ACTION", required=True)
    reset = course_commands.add_parser(
        "reset", help="Back up the database, then delete the data of a course."
    )
    reset.add_argument("--database-url", help=url_help)
    reset.add_argument(
        "--level",
        required=True,
        choices=[level.value for level in ResetLevel],
        help="production: orders and history; catalogs: also products, recipes and downtime "
        "reasons; everything: also every non-administrator user.",
    )
    reset.add_argument(
        "--yes", action="store_true", help=f"Do not ask to type {CONFIRMATION_WORD}."
    )
    return parser


def _database_url(args: argparse.Namespace) -> str:
    return args.database_url or Settings.from_env().database_url


def _run_db(args: argparse.Namespace) -> int:
    url = _database_url(args)
    if args.db_command == "upgrade":
        migrate.upgrade(url, args.revision)
        print(f"Database {display_url(url)} is at revision {migrate.current_revision(url)}.")
        return 0

    current = migrate.current_revision(url)
    head = migrate.head_revision()
    print(f"Database: {display_url(url)}")
    print(f"Applied revision: {current or 'none'}")
    print(f"Latest revision:  {head}")
    if current != head:
        print("The schema is out of date. Run: mes-server db upgrade")
        return 1
    return 0


def _require_current_schema(url: str) -> bool:
    if migrate.current_revision(url) == migrate.head_revision():
        return True
    print(
        f"The database {display_url(url)} is not up to date. Run: mes-server db upgrade",
        file=sys.stderr,
    )
    return False


def _prompt_new_password(prompt: PasswordPrompt) -> str | None:
    password = prompt("Password: ")
    if password != prompt("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return None
    return password


def _run_users(args: argparse.Namespace, prompt: PasswordPrompt) -> int:
    url = _database_url(args)
    if not _require_current_schema(url):
        return 1
    engine = create_db_engine(url)
    try:
        if args.users_command == "list":
            with Session(engine) as session:
                for user in user_service.list_users(session):
                    state = "active" if user.is_active else "inactive"
                    print(f"{user.username:<24} {user.role.value:<18} {state:<9} {user.full_name}")
            return 0

        role = Role.ADMIN if args.users_command == "create-admin" else Role(args.role)
        password = _prompt_new_password(prompt)
        if password is None:
            return 1
        try:
            with session_scope(engine) as session:
                user = user_service.create_user(
                    session,
                    username=args.username,
                    full_name=args.full_name,
                    password=password,
                    role=role,
                )
                username = user.username
        except ServiceError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        print(f"User '{username}' created with role '{role.value}'.")
        return 0
    finally:
        engine.dispose()


def _run_serve(args: argparse.Namespace) -> int:  # pragma: no cover - starts a blocking server
    from mes_server.web.app import run

    settings = Settings.from_env()
    url = args.database_url or settings.database_url
    if not _require_current_schema(url):
        return 1
    if settings.storage_secret_is_generated:
        print(
            "Warning: MES_STORAGE_SECRET is not set; users will be signed out on every restart.",
            file=sys.stderr,
        )
    host = args.host or settings.host
    port = args.port or settings.port
    print(f"UNAM-MES listening on http://{host}:{port}  (database: {display_url(url)})")
    run(
        create_db_engine(url),
        host=host,
        port=port,
        storage_secret=settings.storage_secret,
        database_url=url,
        backup_dir=settings.resolve_backup_dir(url),
    )
    return 0


def _backup_dir(url: str) -> Path | None:
    directory = Settings.from_env().resolve_backup_dir(url)
    if directory is None:
        print("Backups are only available for SQLite database files.", file=sys.stderr)
    return directory


def _run_backup(args: argparse.Namespace) -> int:
    url = _database_url(args)
    directory = _backup_dir(url)
    if directory is None:
        return 1
    if args.backup_command == "list":
        for info in backups.list_backups(directory):
            print(
                f"{info.file_name:<48} {info.created_at:%Y-%m-%d %H:%M} "
                f"{info.created_by:<16} {info.reason}"
            )
        return 0
    if not _require_current_schema(url):
        return 1
    engine = create_db_engine(url)
    try:
        info = course_reset.backup_now(
            engine, url, directory, actor=audit.TERMINAL_ACTOR, actor_role=Role.ADMIN
        )
    except ServiceError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(f"Backup created: {info.path}")
    return 0


def _run_course(args: argparse.Namespace, ask: Prompt) -> int:
    url = _database_url(args)
    directory = _backup_dir(url)
    if directory is None or not _require_current_schema(url):
        return 1
    level = ResetLevel(args.level)
    engine = create_db_engine(url)
    try:
        with Session(engine) as session:
            counts = course_reset.preview(session, level)
        summary = ", ".join(f"{count} {table}" for table, count in counts.items()) or "nothing"
        print(f"Level '{level.value}' will delete: {summary}.")
        confirmation = (
            CONFIRMATION_WORD if args.yes else ask(f"Type {CONFIRMATION_WORD} to continue: ")
        )
        try:
            result = course_reset.reset_course(
                engine,
                url,
                directory,
                level,
                actor=audit.TERMINAL_ACTOR,
                actor_role=Role.ADMIN,
                confirmation=confirmation,
            )
        except ServiceError as error:
            print(f"Error: {error} Nothing was deleted.", file=sys.stderr)
            return 1
    finally:
        engine.dispose()
    print(f"Backup created first: {result.backup.path}")
    print("Course reset complete.")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    prompt: PasswordPrompt = getpass.getpass,
    ask: Prompt = input,
) -> int:
    """Run the command-line interface.

    Args:
        argv: Arguments to parse. ``None`` reads them from ``sys.argv``.
        prompt: Function that reads a password without echoing it.
        ask: Function that reads a line of text, used for confirmations.

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    if args.command == "db":
        return _run_db(args)
    if args.command == "users":
        return _run_users(args, prompt)
    if args.command == "backup":
        return _run_backup(args)
    if args.command == "course":
        return _run_course(args, ask)
    if args.command == "serve":
        return _run_serve(args)
    print(f"{PROG} {__version__}")
    return 0
