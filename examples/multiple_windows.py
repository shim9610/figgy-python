"""Run with python examples/multiple_windows.py; close each window independently."""
import numpy as np
import figgyplot as figgy
from figgyplot.desktop import run_events

x = np.linspace(0, 20, 100_000, dtype=np.float32)
fig, ax = figgy.subplots(backend="native")
fig2, ax2 = figgy.subplots(backend="native")
try:
    ax.plot(x, np.sin(x), id="signal", label="Sine")
    ax.set_title("Window 1 / Sine", fontsize=18)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.legend()
    ax2.plot(x, np.cos(x), id="signal", color="orange", label="Cosine")
    ax2.set_title("Window 2 / Cosine", fontsize=18)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Amplitude")
    ax2.legend()
    fig.show(block=False)
    fig2.show(block=False)
    run_events()  # One event loop handles both windows.
finally:
    fig.close()
    fig2.close()
