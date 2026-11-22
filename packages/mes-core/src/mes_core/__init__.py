"""Shared domain contracts for the MES.

This package holds the pieces that every other component must agree on:
message schemas, enumerations and small utilities. It must stay free of
infrastructure concerns (web, database, MQTT client, PLC drivers) so that
the server, the station gateway and the ERP simulator can all depend on it.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mes-core")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
