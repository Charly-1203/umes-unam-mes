"""Command-line entry point for ``mes-server``."""

import argparse
from collections.abc import Sequence

from mes_server import __version__

PROG = "mes-server"
DESCRIPTION = "MES server: web application, REST API and persistence."


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the command-line interface.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(prog=PROG, description=DESCRIPTION)
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Arguments to parse. ``None`` reads them from ``sys.argv``.

    Returns:
        The process exit code.
    """
    build_parser().parse_args(argv)
    print(f"{PROG} {__version__}")
    return 0
