"""Check our Linux build contract against the action's actual metadata.

Run with PyYAML and a checked-out PyO3/maturin-action/action.yml. Actionlint
does not validate arbitrary third-party action inputs, so it missed the typo
that prevented interpreter setup before the first manual wheel run.
"""
from pathlib import Path
import sys

import yaml


def validate(workflow, action):
    if set(workflow["on"]) != {"workflow_dispatch", "workflow_call"}:
        raise ValueError("Automatic CI must remain disabled")
    valid_inputs = set(action["inputs"])
    builds = [step for job in workflow["jobs"].values()
              for step in job.get("steps", [])
              if step.get("uses", "").startswith("PyO3/maturin-action@")]
    if len(builds) != 1:
        raise ValueError("Expected one portable Linux wheel build step")
    build = builds[0]
    inputs = build.get("with", {})
    unknown = set(inputs) - valid_inputs
    if unknown:
        raise ValueError("Unknown maturin-action inputs: " + ", ".join(sorted(unknown)))
    if inputs.get("before-script-linux") != "bash scripts/ci-before-linux.sh":
        raise ValueError("Linux interpreter setup must run before maturin")
    if not inputs.get("manylinux"):
        raise ValueError("The action must select the portable container and platform tag")
    # The action prepends --manylinux (an alias of --compatibility). Maturin
    # accepts multiple tags in some paths, but this interpreter build requires
    # exactly one, including when both occurrences specify the same value.
    for token in inputs.get("args", "").split():
        if token.split("=", 1)[0] in {"--manylinux", "--compatibility"}:
            raise ValueError("Duplicate platform tags: manylinux input already supplies the compatibility option")
    if inputs.get("container") != "${{ matrix.image }}":
        raise ValueError("Build and installation must use the same Linux image")
    steps = workflow["jobs"]["wheels"]["steps"]
    native_install = next(s for s in steps if s.get("name") == "Check metadata and install only binary distributions")
    if native_install.get("if") != "${{ !matrix.linux }}":
        raise ValueError("musllinux wheels must not be installed on the Ubuntu host")
    linux_install = next(s for s in steps if "ci-check-linux.sh" in s.get("run", ""))
    if linux_install.get("if") != "matrix.linux" or "${{ matrix.image }}" not in linux_install["run"]:
        raise ValueError("Linux installation must run inside its matching build image")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_wheel_workflow.py PATH/TO/maturin-action/action.yml")
    root = Path(__file__).resolve().parents[1]
    # BaseLoader preserves the YAML 'on' key rather than treating it as a
    # YAML 1.1 boolean. All values needed by this checker are strings/mappings.
    workflow = yaml.load((root / ".github/workflows/wheels.yml").read_text(), Loader=yaml.BaseLoader)
    action = yaml.load(Path(sys.argv[1]).read_text(), Loader=yaml.BaseLoader)
    validate(workflow, action)
    print("Manual-only workflow and maturin-action build contract passed")


if __name__ == "__main__":
    main()
