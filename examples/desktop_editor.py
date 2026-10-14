"""Run with python examples/desktop_editor.py; edit directly in the Rust window."""

import numpy as np
import figgy


def make_figure():
    x = np.linspace(0, 20, 100_000, dtype=np.float32)
    fig, ax = figgy.subplots(backend="native", figsize=(8, 5), dpi=120)
    ax.plot(x, np.sin(x), color="#1765ad", linewidth=1.5, label="Signal", id="signal")
    ax.plot(
        x,
        0.55 * np.cos(x),
        color="#df7d22",
        linewidth=1.5,
        label="Reference",
        id="reference",
    )
    ax.set_title("Interactive editor / 100,000 samples", fontsize=18)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.legend()
    return fig


if __name__ == "__main__":
    fig = make_figure()
    try:
        fig.show()  # Blocking main-thread event loop; click an object to open its properties.
    finally:
        fig.close()
