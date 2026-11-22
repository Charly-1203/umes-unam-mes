"""ERP simulator.

Stands in for the enterprise layer (ISA-95 level 4). It does not implement an ERP;
it only emits production orders and bills of materials to the MES server so the
integration between levels can be demonstrated.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mes-erp-sim")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
