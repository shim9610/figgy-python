"""Hand-drawn paths and bundled Comic Neue lettering from Sketch mode."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Draw synthetic weekly growth with deterministic handwriting/wobble."""
    fig, ax = chart("Small habits, lasting growth", "Week", "Active members")
    x = np.arange(13, dtype=np.float64)
    ax.plot(x, 100 + 58*x + 1.8*x*x, marker="o", markersize=5,
            color="#be5133", linewidth=2.5, label="Community", id="community")
    ax.plot(x, 80 + 33*x + 1.2*x*x, marker="s", markersize=4,
            color="#31796b", linewidth=2.5, label="Newsletter", id="newsletter")
    ax.set_xlim(-0.3, 12.3)
    ax.set_ylim(0, 1250)
    ax.legend()
    fig.configure(config={"legend": {"corner": "TopLeft"}})
    fig.set_draw_style("sketch", amplitude_px=1.5, wavelength_px=64, seed=7)
    return fig


if __name__ == "__main__":
    run(make_figure, "sketch-style")
