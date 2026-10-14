"""Overlay a smooth model and measured samples using line and marker styles."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Combine a dense model curve with sparse connected measurements."""
    fig, ax = chart("Model and measurements", "Input", "Response")
    x = np.linspace(0, 10, 2000)
    model = lambda value: 1 / (1 + np.exp(-(value - 5)))
    ax.plot(x, model(x), color="#2467ad", linewidth=2, label="Model", id="model")
    samples = np.linspace(0.3, 9.7, 18)
    measured = model(samples) + np.random.default_rng(9610).normal(0, 0.025, samples.size)
    ax.plot(samples, measured, marker="o", markersize=5, linestyle=":",
            color="#d26a44", label="Measurements", id="measurements")
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.1, 1.25)
    ax.legend()
    fig.configure(config={"legend": {"corner": "TopLeft"}})
    return fig


if __name__ == "__main__":
    run(make_figure, "line-markers")
