"""Compare power laws using logarithmic X and Y axes."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Plot three power laws over four decades."""
    fig, ax = chart("Power laws", "Frequency (Hz)", "Relative power")
    x = np.geomspace(1, 10_000, 2000)
    for i, (exponent, color, style) in enumerate([
        (0.5, "#2467ad", "-"), (1, "#e1843c", "--"), (1.5, "#298773", "-.")
    ]):
        ax.plot(x, x ** -exponent, color=color, linestyle=style, linewidth=2,
                label=f"Exponent = {exponent:g}", id=f"power-{i}")
    # Positive ranges must be set before enabling logarithmic scales.
    ax.set_xlim(1, 10_000)
    ax.set_ylim(1e-6, 2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.legend()
    return fig


if __name__ == "__main__":
    run(make_figure, "log-scales")
