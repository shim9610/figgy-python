"""A dense damped signal with dashed reference envelopes."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Plot 100,000 samples and two envelope curves."""
    fig, ax = chart("Damped oscillation", "Time (s)", "Amplitude")
    t = np.linspace(0, 8, 100_000, dtype=np.float32)
    envelope = np.exp(-0.38 * t)
    ax.plot(t, envelope * np.cos(2 * np.pi * 2 * t), color="#2467ad",
            linewidth=1.8, label="Response", id="response")
    ax.plot(t, envelope, color="#e1843c", linestyle="--", label="Envelope", id="upper")
    ax.plot(t, -envelope, color="#e1843c", linestyle="--", id="lower")
    ax.set_xlim(0, 8)
    ax.set_ylim(-1.2, 1.35)
    ax.legend()
    return fig


if __name__ == "__main__":
    run(make_figure, "line-signals")
