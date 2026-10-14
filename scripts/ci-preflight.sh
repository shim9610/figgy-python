#!/usr/bin/env bash
set -euo pipefail
export FIGGYPLOT_MATURIN_ACTION=${FIGGYPLOT_MATURIN_ACTION:-.ci/maturin-action/action.yml}
uv run --no-project --with actionlint-py --with shellcheck-py actionlint
uv run --no-project python scripts/check_assets.py
uv run --no-project --with 'PyYAML>=6,<7' python scripts/check_wheel_workflow.py "$FIGGYPLOT_MATURIN_ACTION"
uv run --no-project --with 'PyYAML>=6,<7' --with 'packaging>=24' --with pytest python -m pytest -q tests/test_wheel_workflow.py tests/test_packaged_assets.py tests/test_release.py

