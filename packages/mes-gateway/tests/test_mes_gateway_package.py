import re
from importlib.metadata import requires, version

from packaging.requirements import Requirement

import mes_gateway

SEMVER = re.compile(r"^\d+\.\d+\.\d+")
FORBIDDEN_DEPENDENCIES = {"mes-server", "mes-erp-sim"}


def test_version_matches_installed_metadata():
    assert mes_gateway.__version__ == version("mes-gateway")


def test_version_is_semantic():
    assert SEMVER.match(mes_gateway.__version__)


def test_does_not_depend_on_forbidden_workspace_packages():
    declared = {Requirement(r).name for r in requires("mes-gateway") or []}
    assert declared.isdisjoint(FORBIDDEN_DEPENDENCIES)
