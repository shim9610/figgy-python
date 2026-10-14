"""Stars at source samples, joined by translucent lines."""
import numpy as np
from _gallery import chart, dark_theme, run


def make_figure():
    """Draw two synthetic constellations using marker-line series."""
    fig, ax = chart("Constellation traces", "Right ascension", "Declination")
    for i, (x, y, color, label) in enumerate([
        ([1.0, 1.6, 2.3, 2.8, 3.4, 4.1], [1.4, 2.7, 2.1, 3.8, 3.0, 4.2], "#5aa8e8", "Northern arc"),
        ([2.4, 3.0, 3.8, 4.4, 5.1, 5.8], [0.8, 1.9, 1.1, 2.4, 1.6, 2.7], "#d27e4c", "Southern arc"),
    ]):
        ax.plot(np.array(x), np.array(y), marker="o", markersize=8, linewidth=1.4,
                color=color, label=label, id=f"constellation-{i}")
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 5)
    ax.legend()
    ax.grid(False)
    dark_theme(fig)
    fig.set_draw_style("constellation", star_opacity=1, line_opacity=0.45)
    return fig


if __name__ == "__main__":
    run(make_figure, "constellation-style")
