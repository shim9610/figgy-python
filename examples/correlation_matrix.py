"""A block-structured correlation matrix with discrete cells and inverted Y."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Compute correlations from twelve synthetic channels."""
    fig, ax = chart("Channel correlation", "Channel", "Channel")
    rng = np.random.default_rng(9610)
    factors = rng.normal(size=(3, 1200))
    channels = np.repeat(factors, 4, axis=0) + 0.45 * rng.normal(size=(12, 1200))
    channels[8:] *= -1
    channels[8:] += 0.5 * factors[0]
    ax.imshow(np.corrcoef(channels), extent=(0.5, 12.5, 0.5, 12.5), origin="upper",
              cmap="RdBu", vmin=-1, vmax=1, id="correlation")
    ax.grid(False)
    return fig


if __name__ == "__main__":
    run(make_figure, "correlation-matrix")
