#!/usr/bin/env bash
# Executed inside the Linux wheel container. Prefer its native interpreters.
set -euo pipefail
: "${FIGGYPLOT_PYTHON:?select a Python version}"
case "$FIGGYPLOT_PYTHON" in
    3.8|3.9|3.10|3.11|3.12|3.13|3.14|3.15|3.14t|3.15t) ;;
    *) echo "Unsupported CI Python selector: $FIGGYPLOT_PYTHON" >&2; exit 1 ;;
esac
version=${FIGGYPLOT_PYTHON%t}
tag=cp${version//./}
abi=$tag
if [[ "$FIGGYPLOT_PYTHON" == *t ]]; then abi=${tag}t; fi
interpreter=/opt/python/$tag-$abi/bin/python
if [ ! -x "$interpreter" ]; then
    # EOL 3.8 was removed from current manylinux images; install its portable
    # interpreter without raising the glibc floor of the extension build.
    if [[ "${FIGGYPLOT_COMPATIBILITY:-}" == musllinux* ]]; then
        echo "No native musl interpreter for $FIGGYPLOT_PYTHON" >&2
        exit 1
    fi
    if ! command -v uv >/dev/null; then
        /opt/python/cp312-cp312/bin/python -m pip install 'uv>=0.9,<1'
        export PATH=/opt/python/cp312-cp312/bin:$PATH
    fi
    export UV_PYTHON_INSTALL_DIR=/opt/figgyplot-python
    uv python install "$FIGGYPLOT_PYTHON"
    interpreter=$(uv python find --managed-python "$FIGGYPLOT_PYTHON")
fi
# Fail here with the selected ABI, rather than after downloading Cargo crates.
"$interpreter" - <<'PY'
import os
import sys
import sysconfig

requested = os.environ["FIGGYPLOT_PYTHON"]
actual = "%d.%d%s" % (*sys.version_info[:2], "t" if sysconfig.get_config_var("Py_GIL_DISABLED") else "")
if actual != requested:
    raise SystemExit("CI interpreter ABI mismatch: requested %s, found %s at %s" % (requested, actual, sys.executable))
print("CI interpreter: %s (%s)" % (actual, sys.executable))
PY
ln -sf "$interpreter" "/usr/local/bin/python$FIGGYPLOT_PYTHON"
"/usr/local/bin/python$FIGGYPLOT_PYTHON" -V
