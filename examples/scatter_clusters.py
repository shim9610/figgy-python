"""Seeded point clouds with different colors and marker shapes."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Draw three synthetic clusters with transparent markers."""
    fig, ax = chart("Three populations", "Feature 1", "Feature 2")
    rng = np.random.default_rng(9610)
    for i, (center, color, marker) in enumerate([
        ((-1.7, -0.7), "#2467ad99", "o"),
        ((0.8, 1.3), "#e1843c99", "^"),
        ((1.5, -1.0), "#29877399", "D"),
    ]):
        points = rng.normal(size=(900, 2)) @ np.array([[0.65, 0.22], [0, 0.45]])
        points += center
        ax.scatter(points[:, 0], points[:, 1], s=20, color=color, marker=marker,
                   label=f"Population {i + 1}", id=f"population-{i}")
    ax.set_xlim(-4, 4)
    ax.set_ylim(-3, 3.5)
    ax.legend()
    return fig


if __name__ == "__main__":
    run(make_figure, "scatter-clusters")
