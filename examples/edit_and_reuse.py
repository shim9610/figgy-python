"""Edit one plot, then reuse its exported Python settings across three datasets.

Run: python examples/edit_and_reuse.py --output output/edit-and-reuse
Adjust the first window and close it to export the code and apply it to all runs.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import figgy
from figgy.desktop import run_events


def make_figure(run=0):
    """Different synthetic measurements, with matching series IDs and canvas DPI."""
    x = np.linspace(0, 20, 100_000, dtype=np.float32)
    center = 16.2 + run * 0.25
    model = (2.1 - run * 0.1) * np.exp(-0.5 * ((x - center) / 0.85) ** 2)
    measured = model + 0.07 * np.sin(15 * x + run) * np.exp(-0.5 * ((x - center) / 3.2) ** 2)
    baseline = 0.12 + 0.04 * np.sin(0.8 * x + run)
    fig, ax = figgy.subplots(backend="native", figsize=(8, 5), dpi=120)
    ax.plot(x, measured, color="#2467ad", linewidth=1.2, label="Measured response", id="measured")
    ax.plot(x, model, color="#e5893d", linewidth=1.4, linestyle="--", label="Model prediction", id="model")
    ax.plot(x, baseline, color="#4a8f76", linewidth=1.0, label="Reference baseline", id="baseline")
    ax.set_title(f"Response / Run {run + 1:02d}", fontsize=18)
    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_ylabel("Amplitude", fontsize=11)
    ax.set_xlim(0, 20)
    ax.set_ylim(-0.15, 2.5)
    ax.legend()
    fig.update("legend", fontsize=11)
    # Keep the automatic upper-right legend; it overlaps the late response peak.
    return fig


def export_batch(style_code, output):
    """Apply the exported code to fresh data, retaining a separate title per run."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "chart_style.py").write_text(style_code, encoding="utf-8")
    figures = []
    try:
        for run in range(3):
            fig = make_figure(run)
            figures.append(fig)
            uploads = fig.info["column_uploads"]
            exec(style_code, {"fig": fig})
            fig.axes[0].set_title(f"Response / Run {run + 1:02d}")
            fig.savefig(output / f"run-{run + 1:02d}.png")
            assert fig.info["column_uploads"] == uploads
        return figures
    except BaseException:
        for fig in figures:
            fig.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/edit-and-reuse"))
    args = parser.parse_args()
    edited = make_figure()
    results = []
    try:
        edited.show()  # Closing the window keeps its edited Figure available.
        results = export_batch(edited.to_code(), args.output)
        print(f"Saved chart_style.py and three PNGs to {args.output}")
        for fig in results:
            fig.show(block=False)
        run_events()
    finally:
        edited.close()
        for fig in results:
            fig.close()


if __name__ == "__main__":
    main()
