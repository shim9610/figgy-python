#!/usr/bin/env bash
# Run in the SAME image/architecture/libc used to build this matrix wheel.
# A musllinux wheel cannot be installed or imported on the Ubuntu glibc host.
set -euo pipefail
bash scripts/ci-before-linux.sh
"/usr/local/bin/python$FIGGYPLOT_PYTHON" -m venv .wheel-test
test_python=.wheel-test/bin/python
"$test_python" -m pip install --only-binary=:all: twine
"$test_python" -m twine check --strict dist/*.whl
for wheel in dist/*.whl; do
    "$test_python" -m pip install --only-binary=:all: "${wheel}[notebook]"
done
"$test_python" scripts/check_installed.py
