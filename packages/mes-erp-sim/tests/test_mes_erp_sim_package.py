import re
from importlib.metadata import requires, version

from packaging.requirements import Requirement

import mes_erp_sim

SEMVER = re.compile(r"^\d+\.\d+\.\d+")
FORBIDDEN_DEPENDENCIES = {"mes-server", "mes-gateway"}


def test_version_matches_installed_metadata():
    assert mes_erp_sim.__version__ == version("mes-erp-sim")


def test_version_is_semantic():
    assert SEMVER.match(mes_erp_sim.__version__)


def test_does_not_depend_on_forbidden_workspace_packages():
    declared = {Requirement(r).name for r in requires("mes-erp-sim") or []}
    assert declared.isdisjoint(FORBIDDEN_DEPENDENCIES)
