"""Run each workload/backend in an isolated process; keep failure rows visible.

Every timing ends at a completed 960x600 RGBA readback. Data generation/import
time is excluded, initialization and registration/fit are reported separately.
Matplotlib defaults and simplification-disabled lines are separate competitors.
No figgy downsampling or screenshot-cache hits are used.
"""
from __future__ import annotations

import argparse
import csv
import gc
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import threading
import time

import numpy as np

ROOT = Path(__file__).resolve().parent
BACKENDS = ["figgy", "matplotlib-default", "matplotlib-unsimplified", "pyqtgraph-default", "pyqtgraph",
            "pyqtgraph-opengl", "fastplotlib", "vispy", "vispy-aa"]


def run_worker(command, timeout):
    # Kill the entire worker tree on Windows too: a venv launcher can spawn a
    # second python.exe, which subprocess.run(timeout=...) alone leaves alive.
    import psutil
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding="utf-8", errors="replace") as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                children = psutil.Process(process.pid).children(recursive=True)
            except psutil.NoSuchProcess:
                children = []
            for child in reversed(children):
                try: child.kill()
                except psutil.NoSuchProcess: pass
            process.kill()
            process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def timed(callback):
    start = time.perf_counter()
    result = callback()
    return time.perf_counter() - start, result


def data(kind, size, signal):
    if kind == "heatmap":
        side = int(np.sqrt(size))
        axis = np.linspace(-3, 3, side)
        return axis, np.sin(axis[:, None] * 2) * np.cos(axis[None, :] * 3)
    x = np.linspace(0, 100, size, dtype=np.float64)
    y = np.sin(x) + 0.2 * np.cos(x * 4)
    if signal == "noisy":
        y += np.random.default_rng(20261013).normal(0, 0.1, size)
    return x, y


def worker(args):
    import psutil
    from PIL import Image
    x, y = data(args.kind, args.size, args.signal)
    process = psutil.Process()
    stop = threading.Event()
    rss = [process.memory_info().rss]
    def sample():
        while not stop.wait(0.01):
            rss[0] = max(rss[0], process.memory_info().rss)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    row = {"backend": args.worker, "kind": args.kind, "signal": args.signal,
           "size": args.size if args.kind != "heatmap" else y.size,
           "input_bytes": x.nbytes + y.nbytes, "repeats": args.repeats,
           "width": 960, "height": 600, "status": "ok"}
    row["line_width_pixels"] = 2.5
    row["scatter_marker_diameter_pixels"] = 5.0

    cleanup = lambda: None
    if args.worker in ("fastplotlib", "vispy", "vispy-aa", "pyqtgraph-opengl"):
        from gpu_backends import SETUPS
        draw, view, style, save_png, cleanup = SETUPS[args.worker](args, x, y, row)
    elif args.worker == "figgy":
        import figgyplot as figgy
        row["initialize_s"], (fig, ax) = timed(figgy.subplots)
        def register():
            if args.kind == "line": return ax.plot(x, y, linewidth=1.5, color="#1f77b4")[0]
            if args.kind == "scatter": return ax.scatter(x, y, s=9, color="#1f77b4")
            return ax.imshow(y, origin="lower", extent=(-3, 3, -3, 3), interpolation="nearest")
        row["register_and_fit_s"], artist = timed(register)
        row["adapter"] = fig.info["adapter"]
        row["sample_count"] = 1
        draw = fig.render_rgba
        def view(i):
            if args.kind == "heatmap": ax.set_xlim(-3 + i * 0.02, 3 + i * 0.02)
            else: ax.set_xlim(i * 0.2, 100 + i * 0.2)
        def style(i):
            artist.set(color="#d62728" if i % 2 else "#1f77b4")
        save_png = fig.to_png
    elif args.worker.startswith("matplotlib"):
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        matplotlib.rcParams["path.simplify"] = args.worker == "matplotlib-default"
        matplotlib.rcParams["agg.path.chunksize"] = 0
        row["path_simplify"] = matplotlib.rcParams["path.simplify"]
        row["path_simplify_threshold"] = matplotlib.rcParams["path.simplify_threshold"]
        def initialize():
            fig = Figure(figsize=(8, 5), dpi=120)
            canvas = FigureCanvasAgg(fig)
            return fig, canvas, fig.add_subplot(111)
        row["initialize_s"], (fig, canvas, ax) = timed(initialize)
        if args.plot_area:
            left, top, width, height = args.plot_area
            ax.set_position([left / 960, (600 - top - height) / 600, width / 960, height / 600])
        def register():
            if args.kind == "line": artist = ax.plot(x, y, linewidth=1.5, color="#1f77b4")[0]
            elif args.kind == "scatter": artist = ax.scatter(x, y, s=9, color="#1f77b4", linewidths=0)
            else:
                artist = ax.imshow(y, origin="lower", extent=(-3, 3, -3, 3), interpolation="nearest", aspect="auto")
                if args.colorbar_area:
                    left, top, width, height = args.colorbar_area
                    cax = fig.add_axes([left / 960, (600 - top - height) / 600, width / 960, height / 600])
                    fig.colorbar(artist, cax=cax)
            ax.relim() if args.kind == "line" else None
            ax.autoscale_view()
            return artist
        row["register_and_fit_s"], artist = timed(register)
        def draw():
            canvas.draw()
            return np.asarray(canvas.buffer_rgba())
        def view(i):
            ax.set_xlim((-3 + i * 0.02, 3 + i * 0.02) if args.kind == "heatmap" else (i * 0.2, 100 + i * 0.2))
        def style(i): artist.set_color("#d62728" if i % 2 else "#1f77b4")
        def save_png():
            out = io.BytesIO(); canvas.print_png(out); return out.getvalue()
    elif args.worker.startswith("pyqtgraph"):
        if args.kind != "line":
            raise ValueError("pyqtgraph comparison currently covers lines only")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import pyqtgraph as pg
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import QRectF
        app = pg.mkQApp()
        antialias = args.worker != "pyqtgraph-default"
        pg.setConfigOptions(antialias=antialias, useOpenGL=False)
        def initialize():
            plot = pg.PlotWidget(background="w")
            plot.resize(960, 600)
            if args.plot_area:
                left, top, width, height = args.plot_area
                item = plot.getPlotItem()
                item.layout.setContentsMargins(0, 0, 0, 0)
                item.layout.setSpacing(0)
                item.showAxis("top"); item.showAxis("right")
                item.getAxis("top").setStyle(showValues=False)
                item.getAxis("right").setStyle(showValues=False)
                item.getAxis("left").setWidth(left)
                item.getAxis("top").setHeight(top)
                item.getAxis("right").setWidth(960 - left - width)
                item.getAxis("bottom").setHeight(600 - top - height)
            plot.show(); app.processEvents()
            return plot
        row["initialize_s"], plot = timed(initialize)
        def register():
            curve = plot.plot(x, y, pen=pg.mkPen("#1f77b4", width=2.5), autoDownsample=False, clipToView=False)
            plot.autoRange(); app.processEvents(); return curve
        row["register_and_fit_s"], artist = timed(register)
        row["auto_downsample"] = False
        row["use_opengl"] = False
        row["antialias"] = antialias
        def draw():
            image = QImage(960, 600, QImage.Format.Format_RGBA8888)
            image.fill(0xffffffff)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, antialias)
            try: plot.scene().render(painter, QRectF(0, 0, 960, 600), QRectF(plot.rect()))
            finally: painter.end()
            return np.frombuffer(image.constBits(), np.uint8).reshape(600, 960, 4).copy()
        def view(i): plot.setXRange(i * 0.2, 100 + i * 0.2, padding=0)
        def style(i): artist.setPen(pg.mkPen("#d62728" if i % 2 else "#1f77b4", width=2.5))
        def save_png():
            out = io.BytesIO(); Image.fromarray(draw()).save(out, format="PNG"); return out.getvalue()

    row["first_draw_s"], pixels = timed(draw)
    if args.worker == "figgy":
        bounds = json.loads(fig._native.bounds_json("data_area"))["rect"]
        row["plot_area_px"] = [bounds[0] + 2, bounds[1] + 2, bounds[2] - 4, bounds[3] - 4]
    elif args.worker.startswith("matplotlib"):
        row["plot_area_px"] = args.plot_area
    elif args.worker in ("pyqtgraph-default", "pyqtgraph"):
        rect = plot.getViewBox().sceneBoundingRect()
        row["plot_area_px"] = [rect.x(), rect.y(), rect.width(), rect.height()]
    row["first_frame_total_s"] = row["initialize_s"] + row["register_and_fit_s"] + row["first_draw_s"]
    if pixels.shape != (600, 960, 4): raise AssertionError(f"wrong output shape: {pixels.shape}")
    crop = pixels[100:500, 100:800, :3]
    if not np.any(crop.max(axis=2) - crop.min(axis=2) > 25): raise AssertionError("no colored data in plot area")
    if args.images:
        Path(args.images).mkdir(parents=True, exist_ok=True)
        Image.fromarray(pixels).save(Path(args.images) / f"{args.worker}-{args.kind}-{args.signal}-{args.size}.png")
    samples = [timed(draw)[0] for _ in range(args.repeats)]
    row["redraw_samples_s"] = samples
    row["redraw_median_s"] = statistics.median(samples)
    samples = [timed(lambda i=i: (view(i), draw()))[0] for i in range(1, args.repeats + 1)]
    row["view_change_samples_s"] = samples
    row["view_change_median_s"] = statistics.median(samples)
    if args.kind != "heatmap":
        samples = [timed(lambda i=i: (style(i), draw()))[0] for i in range(args.repeats)]
        row["style_change_samples_s"] = samples
        row["style_change_median_s"] = statistics.median(samples)
    row["png_s"], png = timed(save_png)
    row["png_bytes"] = len(png)
    row["peak_rss_mb"] = max(rss[0], process.memory_info().rss) / 1024**2
    stop.set(); sampler.join()
    # Outside the timed/RSS interval, verify that editing did not silently
    # remove the data (some APIs require positions again for a color update).
    final_pixels = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))
    final_crop = final_pixels[100:500, 100:800, :3].astype(np.int16)
    if not np.any(final_crop.max(axis=2) - final_crop.min(axis=2) > 25):
        raise AssertionError("no colored data after view/style edits")
    row["data_visible_after_edits"] = True
    if args.kind != "heatmap":
        style(1)
        red = draw()[100:500, 100:800, :3].astype(np.int16)
        if not np.any((red[:, :, 0] > red[:, :, 1] + 25) & (red[:, :, 0] > red[:, :, 2] + 25)):
            raise AssertionError("style edit did not render red data")
        row["style_render_validated"] = True
    if args.worker == "figgy":
        row["column_uploads_after_redraws"] = fig.info["column_uploads"]
        row["allocation_mode"] = fig.info["allocation_mode"]
        row["pool_used_bytes"] = fig.info["pool_used_bytes"]
        row["known_gpu_bytes"] = fig.info["known_gpu_bytes"]
        fig.close()
    cleanup()
    print(json.dumps(row), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100_000, 1_000_000, 5_000_000])
    parser.add_argument("--kinds", nargs="+", choices=["line", "scatter", "heatmap"], default=["line", "scatter"])
    parser.add_argument("--signals", nargs="+", choices=["smooth", "noisy"], default=["smooth", "noisy"])
    parser.add_argument("--backends", nargs="+", choices=BACKENDS,
                        default=["figgy", "matplotlib-default", "matplotlib-unsimplified", "pyqtgraph-opengl", "fastplotlib", "vispy"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "latest.json")
    parser.add_argument("--images", default=None)
    parser.add_argument("--plot-area", type=float, nargs=4, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--colorbar-area", type=float, nargs=4, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--worker", choices=BACKENDS, help=argparse.SUPPRESS)
    parser.add_argument("--kind", default="line", help=argparse.SUPPRESS)
    parser.add_argument("--signal", default="smooth", help=argparse.SUPPRESS)
    parser.add_argument("--size", type=int, default=100_000, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeats < 1 or min(args.sizes) < 2: parser.error("positive repeats and sizes >= 2 required")
    if args.worker:
        worker(args); return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def version(name):
        try: return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: return None
    report = {"method": "isolated workers; identical float64 arrays; completed RGBA readback at 960x600; no figgy downsampling; medians of repeated calls; PNG includes render and encoding",
              "python": sys.version, "platform": platform.platform(), "processor": platform.processor(),
              "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
              "cpu_quota": Path("/sys/fs/cgroup/cpu.max").read_text().strip() if Path("/sys/fs/cgroup/cpu.max").exists() else None,
              "versions": {name: version(name) for name in ["figgy-python", "numpy", "matplotlib", "pyqtgraph", "PySide6", "psutil", "fastplotlib", "pygfx", "wgpu", "vispy"]},
              "environment": {key: os.environ.get(key) for key in ["WGPU_BACKEND", "VK_DRIVER_FILES", "QT_QPA_PLATFORM", "LP_NUM_THREADS",
                              "QT_SCALE_FACTOR", "QT_AUTO_SCREEN_SCALE_FACTOR", "QT_ENABLE_HIGHDPI_SCALING", "QT_SCREEN_SCALE_FACTORS", "WAYLAND_DISPLAY"]}, "rows": []}
    # Query the renderer's own layout once, outside worker timing/RSS.
    import figgyplot as figgy
    areas, colorbars = {}, {}
    for kind in args.kinds:
        with figgy.Figure() as reference:
            if kind == "heatmap":
                reference.axes[0].imshow(np.array([[0., 1.], [1., 0.]]), origin="lower", extent=(-3, 3, -3, 3))
                rect = json.loads(reference._native.bounds_json("colorbar"))["rect"]
                colorbars[kind] = [rect[0] + 2, rect[1] + 2, rect[2] - 4, rect[3] - 4]
            else: reference.axes[0].plot([0., 1., 2.], [0., 1., 0.])
            rect = json.loads(reference._native.bounds_json("data_area"))["rect"]
            areas[kind] = [rect[0] + 2, rect[1] + 2, rect[2] - 4, rect[3] - 4]
    report["reference_plot_areas_px"] = areas
    report["reference_colorbar_areas_px"] = colorbars
    for kind in args.kinds:
        for signal in args.signals if kind != "heatmap" else ["smooth"]:
            for size in args.sizes:
                for backend in args.backends:
                    if backend.startswith("pyqtgraph") and kind != "line": continue
                    if backend in ("fastplotlib", "vispy", "vispy-aa") and kind == "heatmap": continue
                    if backend == "matplotlib-unsimplified" and kind != "line": continue
                    command = [sys.executable, str(Path(__file__).resolve()), "--worker", backend, "--kind", kind,
                               "--signal", signal, "--size", str(size), "--repeats", str(args.repeats)]
                    command += ["--plot-area", *map(str, areas[kind])]
                    if kind in colorbars: command += ["--colorbar-area", *map(str, colorbars[kind])]
                    if args.images: command += ["--images", args.images]
                    try:
                        result = run_worker(command, args.timeout)
                        if result.returncode != 0:
                            row = {"backend": backend, "kind": kind, "signal": signal, "size": size, "status": "error", "returncode": result.returncode, "error": result.stderr[-4000:] or f"worker exited with code {result.returncode}"}
                        else: row = json.loads(result.stdout.strip().splitlines()[-1])
                    except subprocess.TimeoutExpired:
                        row = {"backend": backend, "kind": kind, "signal": signal, "size": size, "status": "timeout", "timeout_s": args.timeout}
                    report["rows"].append(row)
                    args.output.write_text(json.dumps(report, indent=2))
                    print(f"{backend:25} {kind:7} {signal:6} {size:>9,} " + (f"first={row['first_frame_total_s']:.3f}s redraw={row['redraw_median_s']:.3f}s RSS={row['peak_rss_mb']:.0f}MB" if row["status"] == "ok" else row["status"]), flush=True)
    fields = ["backend", "kind", "signal", "size", "status", "initialize_s", "register_and_fit_s", "first_draw_s", "first_frame_total_s", "redraw_median_s", "view_change_median_s", "style_change_median_s", "png_s", "peak_rss_mb"]
    with args.output.with_suffix(".csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(report["rows"])


if __name__ == "__main__":
    main()
