"""Command-line entry point for ``mes-server``.

Commands:
    ``mes-server``                 Print the name and version.
    ``mes-server db upgrade``      Create or update the database schema.
    ``mes-server db status``       Show the applied and the latest schema revision.
"""

import argparse
from collections.abc import Sequence

from sqlalchemy.engine import make_url

from mes_server import __version__
from mes_server.config import Settings
from mes_server.db import migrate

PROG = "mes-server"
DESCRIPTION = "MES server: web application, REST API and persistence."


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

    db = commands.add_parser("db", help="Manage the database schema.")
    db_commands = db.add_subparsers(dest="db_command", metavar="ACTION", required=True)

    url_help = "SQLAlchemy URL of the database. Defaults to $MES_DATABASE_URL or sqlite:///mes.db."
    upgrade = db_commands.add_parser("upgrade", help="Create or update the schema.")
    upgrade.add_argument("--database-url", help=url_help)
    upgrade.add_argument("--revision", default="head", help="Target revision (default: head).")

    status = db_commands.add_parser("status", help="Show the schema revision.")
    status.add_argument("--database-url", help=url_help)
    return parser


def _run_db(args: argparse.Namespace) -> int:
    url = args.database_url or Settings.from_env().database_url
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Arguments to parse. ``None`` reads them from ``sys.argv``.

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    if args.command == "db":
        return _run_db(args)
    print(f"{PROG} {__version__}")
    return 0
