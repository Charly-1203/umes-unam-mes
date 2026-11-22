"""Command-line entry point for ``mes-server``.

Commands:
    ``mes-server``                     Print the name and version.
    ``mes-server serve``               Start the web application.
    ``mes-server db upgrade``          Create or update the database schema.
    ``mes-server db status``           Show the applied and the latest schema revision.
    ``mes-server users create-admin``  Create an administrator, prompting for the password.
    ``mes-server users create``        Create a user with any role.
    ``mes-server users list``          List every user.
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from sqlalchemy.engine import make_url
from sqlmodel import Session

from mes_core.enums import Role
from mes_server import __version__
from mes_server.config import Settings
from mes_server.db import create_db_engine, migrate, session_scope
from mes_server.services import users as user_service
from mes_server.services.errors import ServiceError

PROG = "mes-server"
DESCRIPTION = "MES server: web application, REST API and persistence."

PasswordPrompt = Callable[[str], str]


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
    run(create_db_engine(url), host=host, port=port, storage_secret=settings.storage_secret)
    return 0


def main(argv: Sequence[str] | None = None, *, prompt: PasswordPrompt = getpass.getpass) -> int:
    """Run the command-line interface.

    Args:
        argv: Arguments to parse. ``None`` reads them from ``sys.argv``.
        prompt: Function that reads a password without echoing it.

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    if args.command == "db":
        return _run_db(args)
    if args.command == "users":
        return _run_users(args, prompt)
    if args.command == "serve":
        return _run_serve(args)
    print(f"{PROG} {__version__}")
    return 0
