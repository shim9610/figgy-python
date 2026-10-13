"""Create standalone charts from benchmark JSON; error rows remain unplotted."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.ticker import NullFormatter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "comparison")
    args = parser.parse_args()
    rows = [row for path in args.reports for row in json.loads(path.read_text())["rows"]]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    panels = [("line", "smooth", "Smooth line"), ("line", "noisy", "Noisy line"), ("scatter", "noisy", "Scatter"), ("heatmap", "smooth", "Heatmap")]
    colors = {"figgy": "#1765ad", "matplotlib-default": "#df7d22", "matplotlib-unsimplified": "#c44343", "pyqtgraph-default": "#278762", "pyqtgraph": "#7e58a8"}
    for ax, (kind, signal, title) in zip(axes.flat, panels):
        for backend, color in colors.items():
            matches = sorted((row for row in rows if row["status"] == "ok" and row["backend"] == backend and row["kind"] == kind and row["signal"] == signal), key=lambda row: row["size"])
            if matches:
                ax.plot([r["size"] for r in matches], [r["redraw_median_s"] * 1000 for r in matches], "o-", color=color, label=backend)
        failures = [r for r in rows if r["status"] != "ok" and r["kind"] == kind and r["signal"] == signal]
        if failures:
            ax.text(.03, .03, "Failures/timeouts are recorded in JSON", transform=ax.transAxes, fontsize=8, color="#555")
        ax.set_xscale("log"); ax.set_yscale("log")
        sizes = sorted({row["size"] for row in rows if row["kind"] == kind and row["signal"] == signal})
        ax.set_xticks(sizes)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1e6:g}M" if v >= 1e6 else f"{v/1e3:.0f}k"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_title(title); ax.set_xlabel("Input samples / cells"); ax.set_ylabel("Completed redraw (ms, median)")
        ax.grid(True, which="both", alpha=.15); ax.legend(fontsize=8)
    fig.suptitle("Figgy Python vs Python plotting libraries\nCPU Vulkan / llvmpipe, 4-core CPU quota, 960 × 600 RGBA readback", fontsize=14)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output.with_suffix(".png"), dpi=160)
    svg = args.output.with_suffix(".svg")
    fig.savefig(svg)
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")


if __name__ == "__main__": main()
