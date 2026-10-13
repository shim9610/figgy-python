"""Render benchmark charts with Figgy itself; retain failures in JSON.

Each panel, including its text, axes and legend, is rendered by Figgy's native
renderer. Pillow only encodes/pastes finished RGBA pixels into the overview.
The SVG is a raster container, not a native vector export. Multi-panel Figure
support is not yet available in the Python API.
"""
import argparse
import base64
import io
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

import figgy
from PIL import Image

PANELS = [("line", "smooth", "Smooth line"), ("line", "noisy", "Noisy line"),
          ("scatter", "noisy", "Scatter"), ("heatmap", "smooth", "Heatmap")]
COLORS = {"figgy": "#1765ad", "matplotlib-default": "#df7d22",
          "matplotlib-unsimplified": "#c44343", "pyqtgraph-default": "#278762",
          "pyqtgraph": "#7e58a8", "pyqtgraph-opengl": "#006b3c",
          "fastplotlib": "#aa3377", "vispy": "#009eaa"}
PANEL_SIZE = (960, 600)


def header(subtitle):
    """Use native Figgy text for the overview heading too."""
    with figgy.Figure(figsize=(16, 1.25), dpi=120) as fig:
        ax = fig.axes[0]
        ax.set_title("Figgy Python vs Python plotting libraries", fontsize=20)
        ax.set_xlabel(subtitle, fontsize=12)
        state = fig.get_settings()
        cfg = state["config"]
        cfg["chart_title"]["top_margin"] = 32
        cfg["chart_title"]["offset_y"] = 10
        cfg["chart_area"]["height"] = 110
        for key in ("bottom_x", "top_x", "left_y", "right_y"):
            cfg[key]["line_visible"] = False
            cfg[key]["label_style"]["visible"] = False
            cfg[key]["major_tick_length"] = 0
            cfg[key]["minor_tick_length"] = 0
            cfg[key]["out_margin"] = 0
        cfg["bottom_x"]["out_margin"] = 38
        for key in ("show_major_x", "show_major_y", "show_minor_x", "show_minor_y"):
            cfg["grid"][key] = False
        fig.apply_settings(state)
        return Image.fromarray(fig.render_rgba()).crop((0, 0, 1920, 110))


def panel(rows, kind, signal, title):
    matching = [row for row in rows if row["kind"] == kind and row["signal"] == signal]
    successful = [row for row in matching if row["status"] == "ok"]
    with figgy.Figure(figsize=(8, 5), dpi=120) as fig:
        ax = fig.axes[0]
        for backend, color in COLORS.items():
            # A failure breaks the line: never connect across a missing result.
            run = []
            runs = []
            for row in sorted((r for r in matching if r["backend"] == backend), key=lambda r: r["size"]):
                if row["status"] == "ok":
                    run.append(row)
                elif run:
                    runs.append(run)
                    run = []
            if run:
                runs.append(run)
            for index, run in enumerate(runs):
                ax.plot([r["size"] / 1_000_000 for r in run],
                        [r["redraw_median_s"] * 1000 for r in run], "o-",
                        color=color, linewidth=1.8, markersize=6,
                        label=backend if index == 0 else None)
        if successful:
            xs = [r["size"] / 1_000_000 for r in successful]
            ys = [r["redraw_median_s"] * 1000 for r in successful]
            if min(xs) <= 0 or min(ys) <= 0 or not all(math.isfinite(v) for v in xs + ys):
                raise ValueError("logarithmic benchmark charts require positive finite sizes and timings")
            ax.set_xlim(min(xs) / 1.25, max(xs) * 1.25)
            ax.set_ylim(min(ys) / 1.35, max(ys) * 1.35)
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.legend()
        failures = sum(r["status"] != "ok" for r in matching)
        ax.set_title(title + (f" ({failures} failed; see JSON)" if failures else ""), fontsize=18)
        ax.set_xlabel("Input samples / cells (millions, log scale)", fontsize=12)
        ax.set_ylabel("Completed redraw (ms, median; log scale)", fontsize=12)
        state = fig.get_settings()
        cfg = state["config"]
        cfg["legend"]["corner"] = "TopLeft"
        cfg["legend"]["content"]["font_size"] = 16
        cfg["left_y"]["out_margin"] = 95
        cfg["bottom_x"]["out_margin"] = 65
        for key in ("bottom_x", "top_x", "left_y", "right_y"):
            cfg[key]["label_style"]["font_size"] = 16
        for axis in ("x", "y"):
            cfg["grid"][f"show_minor_{axis}"] = True
            cfg["grid"][f"major_{axis}_color"] = dict(r=.85, g=.85, b=.85, a=1.)
            cfg["grid"][f"minor_{axis}_color"] = dict(r=.94, g=.94, b=.94, a=1.)
        fig.apply_settings(state)
        image = Image.fromarray(fig.render_rgba())
        return image, {"kind": kind, "signal": signal, "successful_rows": len(successful),
                       "failed_rows": failures, "adapter": fig.info["adapter"],
                       "xscale": ax.get_xscale(), "yscale": ax.get_yscale()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "comparison")
    parser.add_argument("--subtitle", default="CPU Vulkan / llvmpipe, 4-core CPU quota, 960 x 600 RGBA readback",
                        help="Machine and rendering conditions shown below the chart title")
    args = parser.parse_args()
    rows = [row for path in args.reports for row in json.loads(path.read_text(encoding="utf-8"))["rows"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    heading = header(args.subtitle)
    overview = Image.new("RGBA", (PANEL_SIZE[0] * 2, PANEL_SIZE[1] * 2 + heading.height), "white")
    overview.paste(heading, (0, 0))
    provenance = {"chart_renderer": "figgy / native figgy-renderer", "figgy_python_version": figgy.__version__,
                  "reports": [path.name for path in args.reports],
                  "composition": "Pillow pastes completed Figgy RGBA pixels and encodes PNG; no chart drawing",
                  "svg": "embedded PNG, not vector export", "subtitle": args.subtitle, "panels": []}
    for i, (kind, signal, title) in enumerate(PANELS):
        image, info = panel(rows, kind, signal, title)
        overview.paste(image, ((i % 2) * PANEL_SIZE[0], heading.height + (i // 2) * PANEL_SIZE[1]))
        path = args.output.with_name(f"{args.output.name}-{kind}-{signal}.png")
        image.save(path)
        info["file"] = path.name
        provenance["panels"].append(info)
    png = io.BytesIO()
    overview.save(png, format="PNG")
    args.output.with_suffix(".png").write_bytes(png.getvalue())
    encoded = base64.b64encode(png.getvalue()).decode("ascii")
    args.output.with_suffix(".svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{overview.width}" height="{overview.height}" '
        f'viewBox="0 0 {overview.width} {overview.height}">\n'
        f'<title>Figgy-rendered benchmark comparison</title>\n'
        f'<desc>{escape(args.subtitle)}. All charts rendered by Figgy. Embedded raster image.</desc>\n'
        f'<image width="{overview.width}" height="{overview.height}" href="data:image/png;base64,{encoded}"/>\n'
        '</svg>\n', encoding="utf-8")
    args.output.with_suffix(".rendering.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(f"Figgy rendered {len(PANELS)} panels: {args.output.with_suffix('.png')}")


if __name__ == "__main__":
    main()
