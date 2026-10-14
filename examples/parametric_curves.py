"""Layered parametric curves built with the ordinary line API."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Trace nested hypotrochoid curves in four colors."""
    fig, ax = chart("Parametric traces", "X", "Y")
    t = np.linspace(0, 6 * np.pi, 6000)
    for i, (radius, color) in enumerate(zip([1.0, 0.82, 0.64, 0.46],
                                           ["#2467ad", "#298773", "#e1843c", "#b34970"])):
        x = radius * (0.72 * np.cos(t) + 0.28 * np.cos(7 * t / 3))
        y = radius * (0.72 * np.sin(t) - 0.28 * np.sin(7 * t / 3))
        ax.plot(x, y, color=color, linewidth=1.5, id=f"trace-{i}")
    # Leave space around the outer trace in the wide plot area.
    ax.set_xlim(-1.82, 1.82)
    ax.set_ylim(-1.1, 1.1)
    ax.grid(False)
    return fig


if __name__ == "__main__":
    run(make_figure, "parametric-curves")
