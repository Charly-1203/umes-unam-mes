"""Station gateway.

Runs on the computer of each workstation. Receives work orders and recipes from
the MES server, executes the recipe steps against the station PLC through a
driver abstraction, and reports results, states and downtime back to the server.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mes-gateway")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
