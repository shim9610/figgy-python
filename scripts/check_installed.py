"""Installed-wheel smoke check without requiring a kernel GPU or display."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np
import figgyplot
from figgyplot._native import NativeFigure


def main():
    root = Path(figgyplot.__file__).resolve().parent
    assert root.name == "figgyplot"
    assert NativeFigure.__module__ == "figgyplot._native"
    assert figgyplot.__version__ == importlib.metadata.version("figgyplot")
    assets = root / "assets"
    assert (assets / "figgy_bg.wasm").read_bytes()[:4] == b"\x00asm"
    assert (root / "webgpu.js").is_file()
    provenance = json.loads((assets / "provenance.json").read_text())
    for name, record in provenance["assets"].items():
        assert hashlib.sha256((assets / name).read_bytes()).hexdigest() == record["sha256"]
    with figgyplot.Figure(backend="webgpu") as fig:
        fig.axes[0].plot(np.arange(8, dtype=np.float32), id="signal")
        fig.axes[0].set_title("Installed figgyplot")
        widget = fig.widget(auto_prepare=False)
        assert widget.wasm and widget.wasm_js and widget.columns
    print(json.dumps({"package": str(root), "version": figgyplot.__version__,
                      "python": sys.version.split()[0], "numpy": np.__version__,
                      "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
                      "packaged_wasm_bytes": (assets / "figgy_bg.wasm").stat().st_size}))


if __name__ == "__main__":
    main()
