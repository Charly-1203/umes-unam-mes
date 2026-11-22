"""MES server.

Hosts the web application (engineering, supervision and administration screens),
the REST API used by the ERP simulator, the persistence layer and the messaging
service that dispatches work to the station gateways.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mes-server")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
