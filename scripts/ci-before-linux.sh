#!/usr/bin/env bash
# Executed inside the Linux wheel container. Prefer its native interpreters.
set -euo pipefail
: "${FIGGYPLOT_PYTHON:?select a Python version}"
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
    /opt/python/cp312-cp312/bin/python -m pip install 'uv>=0.9,<1'
    export UV_PYTHON_INSTALL_DIR=/opt/figgyplot-python
    uv python install "$FIGGYPLOT_PYTHON"
    interpreter=$(uv python find "$FIGGYPLOT_PYTHON")
fi
ln -sf "$interpreter" "/usr/local/bin/python$FIGGYPLOT_PYTHON"
"/usr/local/bin/python$FIGGYPLOT_PYTHON" -V
