import subprocess
import sys

import pytest

from mes_erp_sim import __version__
from mes_erp_sim.cli import main


def test_main_without_arguments_prints_name_and_version(capsys):
    assert main([]) == 0
    assert capsys.readouterr().out.strip() == f"mes-erp-sim {__version__}"


def test_version_flag_prints_version_and_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"mes-erp-sim {__version__}"


def test_unknown_argument_is_rejected():
    with pytest.raises(SystemExit) as exc:
        main(["--not-an-option"])
    assert exc.value.code == 2


def test_package_runs_as_module():
    result = subprocess.run(
        [sys.executable, "-m", "mes_erp_sim"], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == f"mes-erp-sim {__version__}"
