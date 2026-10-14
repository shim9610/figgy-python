"""Regressions for the expensive manual CI failures; no GPU is needed."""
import copy
import os
from pathlib import Path
import runpy

import pytest

yaml = pytest.importorskip("yaml", reason="CI workflow checks require PyYAML")
root = Path(__file__).resolve().parents[1]
validate = runpy.run_path(str(root / "scripts/check_wheel_workflow.py"))["validate"]


@pytest.fixture
def contract():
    metadata = os.environ.get("FIGGYPLOT_MATURIN_ACTION")
    if not metadata:
        pytest.skip("set FIGGYPLOT_MATURIN_ACTION to the actual action.yml")
    workflow = yaml.load((root / ".github/workflows/wheels.yml").read_text(), Loader=yaml.BaseLoader)
    action = yaml.load(Path(metadata).read_text(), Loader=yaml.BaseLoader)
    return workflow, action


def test_actual_action_contract(contract):
    validate(*contract)


def test_reject_ignored_before_script_input(contract):
    workflow, action = copy.deepcopy(contract)
    inputs = next(s["with"] for s in workflow["jobs"]["wheels"]["steps"]
                  if s.get("uses", "").startswith("PyO3/maturin-action@"))
    inputs["before-script"] = inputs.pop("before-script-linux")
    with pytest.raises(ValueError, match="Unknown maturin-action inputs: before-script"):
        validate(workflow, action)


@pytest.mark.parametrize("option", ["--compatibility manylinux_2_28", "--manylinux 2_28", "--compatibility=musllinux_1_2"])
def test_reject_duplicate_platform_tags(contract, option):
    workflow, action = copy.deepcopy(contract)
    inputs = next(s["with"] for s in workflow["jobs"]["wheels"]["steps"]
                  if s.get("uses", "").startswith("PyO3/maturin-action@"))
    inputs["args"] += " " + option
    with pytest.raises(ValueError, match="Duplicate platform tags"):
        validate(workflow, action)


def test_reject_automatic_ci(contract):
    workflow, action = copy.deepcopy(contract)
    workflow["on"]["push"] = ""
    with pytest.raises(ValueError, match="Automatic CI must remain disabled"):
        validate(workflow, action)


def test_reject_musl_install_on_glibc_host(contract):
    workflow, action = copy.deepcopy(contract)
    install = next(s for s in workflow["jobs"]["wheels"]["steps"]
                   if s.get("name") == "Check metadata and install only binary distributions")
    del install["if"]
    with pytest.raises(ValueError, match="musllinux wheels must not be installed on the Ubuntu host"):
        validate(workflow, action)
