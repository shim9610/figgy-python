"""A smooth signed field using a diverging colormap and bilinear interpolation."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Render a synthetic field on a 240 by 360 grid."""
    fig, ax = chart("Interference field", "X position", "Y position")
    x, y = np.meshgrid(np.linspace(-3, 3, 360), np.linspace(-2, 2, 240))
    field = np.sin(3 * x) * np.cos(3 * y) * np.exp(-0.22 * (x*x + y*y))
    ax.imshow(field.astype(np.float32), extent=(-3, 3, -2, 2), origin="lower",
              cmap="RdBu", vmin=-1, vmax=1, interpolation="bilinear", id="field")
    ax.grid(False)
    return fig


if __name__ == "__main__":
    run(make_figure, "heatmap-field")
