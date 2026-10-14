"""Milkyway line ribbons and star chains; scatter is intentionally disabled."""
import numpy as np
from _gallery import chart, dark_theme, run


def make_figure():
    """Draw two line-only star streams without scatter/marker planets."""
    fig, ax = chart("Milkyway streams", "Time", "Displacement")
    t = np.linspace(0, 12, 1800)
    ax.plot(t, np.sin(0.8*t) + 0.12*np.cos(2.2*t), color="#61b8df",
            linewidth=2, label="Stream A", id="stream-a")
    ax.plot(t, 0.6*np.cos(0.65*t+0.5), color="#d98cbb",
            linewidth=2, label="Stream B", id="stream-b")
    ax.set_xlim(0, 12)
    ax.set_ylim(-1.5, 1.6)
    ax.legend()
    ax.grid(False)
    dark_theme(fig)
    fig.set_draw_style("milkyway", seed=9610, star_density=20,
                       ribbon_width_px=16, ribbon_intensity=0.3)
    return fig


if __name__ == "__main__":
    run(make_figure, "milkyway-style")
