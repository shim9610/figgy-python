"""Compute a short-time spectrum with NumPy and display it as a heatmap."""
import numpy as np
from _gallery import chart, run


def make_figure():
    """Show a chirp and a fixed tone without a SciPy dependency."""
    fig, ax = chart("Chirp spectrogram", "Time (s)", "Frequency (Hz)")
    rate, length, hop = 256, 256, 32
    t = np.arange(rate * 8) / rate
    signal = np.sin(2*np.pi*(8*t + 2.5*t*t)) + 0.55*np.sin(2*np.pi*48*t)
    windows = np.lib.stride_tricks.sliding_window_view(signal, length)[::hop]
    spectrum = np.abs(np.fft.rfft(windows * np.hanning(length), axis=1))
    decibels = 20 * np.log10(np.maximum(spectrum / spectrum.max(), 1e-4))
    # Each column is one analysis window; keep the first 81 frequency bins.
    left = (length / 2 - hop / 2) / rate
    right = left + windows.shape[0] * hop / rate
    ax.imshow(decibels[:, :81].T, extent=(left, right, -0.5, 80.5), origin="lower",
              cmap="magma", vmin=-65, vmax=0, id="spectrum")
    ax.grid(False)
    return fig


if __name__ == "__main__":
    run(make_figure, "spectrogram")
