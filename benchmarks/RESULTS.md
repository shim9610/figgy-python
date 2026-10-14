# Python bindings and benchmark results

For Figgy 0.2.0 measurements on actual Ubuntu/Radeon 8060S hardware, see
[Linux GPU benchmarks](LINUX_GPU_RESULTS.md). The llvmpipe results below use
software Vulkan and should be considered separately.

Actual Windows/RTX 4070 Ti measurements are recorded in
[Windows benchmarks](WINDOWS_RESULTS.md). The follow-up
[Windows GPU comparison](WINDOWS_GPU_RESULTS.md) adds fastplotlib, VisPy and
actual pyqtgraph OpenGL rendering.

Report charts are rendered with Figgy one panel at a time, then arranged as
images. SVG embeds the finished PNG.

The original campaign used Python 0.1 alpha with figgy-renderer 0.16.1:
matplotlib-like plot/scatter/imshow, NumPy staging uploads, desktop/Jupyter
editing, Python settings export and PNG output. The current package is 0.2.0;
see [host validation](../docs/HOST_VALIDATION.md) for subsequent host changes.
There is no automatic streaming/downsampling/chunk-render transition. A small
resident pool grows as needed. Exceeding device limits raises `MemoryError`
with capacity, column and adapter context.

## Conditions

- Python 3.12.14, NumPy 2.5.4, matplotlib 3.11.2, pyqtgraph 0.14.0,
  PySide6 6.12.0.
- Linux x86_64, llvmpipe LLVM 19.1.7 **CPU Vulkan**, four-core CPU quota,
  no physical GPU.
- Completed 960×600 RGBA readback; line width 2.5 px, scatter diameter 5 px.
- Identical float64 inputs; separate smooth/noisy line signals with fixed seed.
- Actual Figgy/matplotlib plot areas matched. Heatmaps include colorbars.
  pyqtgraph dimensions differ by 0.5 px because of QGraphicsItem boundaries.
- Figgy uses sample count 1 and shader AA; matplotlib uses Agg AA; pyqtgraph
  default QPainter uses AA off, OpenGL off and autoDownsample off. Output pixels
  are not identical across backends.
- Independent workers separate initialization, registration/fit, first draw,
  repeated draw, axis/style edits and PNG output. Repeated draw is a median of
  three runs. Imports/input generation are excluded from totals.
- Processes are fresh, but OS/font/Mesa caches are not cleared. These are not
  fully cold-cache or screen-FPS measurements. PNG/Jupyter comm/browser latency
  are separate costs.
- Full-worker peak RSS includes input/library/driver memory; it is not physical
  VRAM or isolated Rust/Python object memory.

## Observations

Repeated four-million-cell heatmaps took 27.5 ms for Figgy and 124.3 ms for
matplotlib, approximately **4.5×** apart. First output favored matplotlib:
180 ms versus 601 ms for Figgy. The advantage appears when reusing a resident
matrix during repeated edits/renders.

One-million-point noisy lines took 650 ms for Figgy versus 2696 ms for
matplotlib with simplification disabled, approximately 4.1× apart. Default
matplotlib simplification is faster than that. For smooth lines, both default
and unsimplified matplotlib outperformed Figgy; scatter was broadly similar.
These results do not support a claim that Rust makes every workload faster.

At five million noisy samples, unsimplified matplotlib hit the Agg cell-block
limit. The original error remains in JSON rather than being labeled a timeout,
allocation failure or speed result. Default matplotlib, Figgy and pyqtgraph
completed the same input.

These are software Vulkan measurements. For hardware Vulkan, see the Windows
and Linux reports linked above. Windows/DX12 and macOS/Metal need separate
measurements.

## Line

| Input | Backend | Init + register/fit + first draw (ms) | Repeated draw (ms) | Axis edit + draw (ms) | Peak RSS (MiB) |
|---|---|---:|---:|---:|---:|
| 100,000 / smooth | figgy | 277.7 | 73.8 | 83.3 | 226.5 |
| 100,000 / smooth | matplotlib-default | 45.1 | 22.8 | 24.6 | 78.0 |
| 100,000 / smooth | matplotlib-unsimplified | 51.2 | 28.5 | 28.9 | 78.1 |
| 100,000 / smooth | pyqtgraph-default | 133.5 | 44.7 | 47.7 | 132.5 |
| 1,000,000 / smooth | figgy | 797.5 | 474.1 | 465.3 | 293.8 |
| 1,000,000 / smooth | matplotlib-default | 118.2 | 57.8 | 54.7 | 136.6 |
| 1,000,000 / smooth | matplotlib-unsimplified | 216.7 | 160.1 | 159.7 | 140.9 |
| 1,000,000 / smooth | pyqtgraph-default | 1036.5 | 429.6 | 426.2 | 174.0 |
| 5,000,000 / smooth | figgy | 3396.1 | 2433.8 | 2728.6 | 471.0 |
| 5,000,000 / smooth | matplotlib-default | 455.2 | 231.4 | 224.4 | 401.4 |
| 5,000,000 / smooth | matplotlib-unsimplified | 916.8 | 738.9 | 755.0 | 419.1 |
| 5,000,000 / smooth | pyqtgraph-default | 4738.3 | 2119.0 | 1988.8 | 353.9 |
| 100,000 / noisy | figgy | 301.6 | 103.5 | 97.0 | 230.5 |
| 100,000 / noisy | matplotlib-default | 136.0 | 102.9 | 111.1 | 119.6 |
| 100,000 / noisy | matplotlib-unsimplified | 259.1 | 259.0 | 237.2 | 167.9 |
| 100,000 / noisy | pyqtgraph-default | 193.5 | 83.0 | 90.8 | 135.9 |
| 1,000,000 / noisy | figgy | 886.8 | 650.0 | 647.5 | 410.7 |
| 1,000,000 / noisy | matplotlib-default | 232.2 | 175.6 | 191.7 | 181.1 |
| 1,000,000 / noisy | matplotlib-unsimplified | 2995.3 | 2695.7 | 2610.2 | 983.2 |
| 1,000,000 / noisy | pyqtgraph-default | 1378.7 | 640.1 | 623.5 | 176.9 |
| 5,000,000 / noisy | figgy | 5000.2 | 4756.4 | 4484.2 | 2276.5 |
| 5,000,000 / noisy | matplotlib-default | 881.0 | 389.9 | 437.5 | 402.3 |
| 5,000,000 / noisy | matplotlib-unsimplified | Agg error | — | — | — |
| 5,000,000 / noisy | pyqtgraph-default | 6789.0 | 2976.8 | 3089.2 | 357.8 |

## Scatter

| Input | Backend | Init + register/fit + first draw (ms) | Repeated draw (ms) | Axis edit + draw (ms) | Peak RSS (MiB) |
|---|---|---:|---:|---:|---:|
| 100,000 / noisy | figgy | 307.6 | 52.8 | 51.9 | 172.1 |
| 100,000 / noisy | matplotlib-default | 65.9 | 44.6 | 43.1 | 78.1 |
| 1,000,000 / noisy | figgy | 617.3 | 366.0 | 355.6 | 302.3 |
| 1,000,000 / noisy | matplotlib-default | 364.2 | 333.5 | 339.7 | 135.6 |
| 5,000,000 / noisy | figgy | 2074.2 | 1603.7 | 1624.1 | 619.5 |
| 5,000,000 / noisy | matplotlib-default | 1844.0 | 1720.7 | 1603.0 | 401.4 |

## Heatmap

| Input | Backend | Init + register/fit + first draw (ms) | Repeated draw (ms) | Axis edit + draw (ms) | Peak RSS (MiB) |
|---|---|---:|---:|---:|---:|
| 99,856 / smooth | figgy | 296.6 | 24.1 | 26.7 | 158.3 |
| 99,856 / smooth | matplotlib-default | 70.3 | 40.1 | 39.5 | 104.6 |
| 1,000,000 / smooth | figgy | 343.4 | 22.4 | 21.8 | 167.9 |
| 1,000,000 / smooth | matplotlib-default | 84.6 | 48.8 | 48.8 | 173.3 |
| 4,000,000 / smooth | figgy | 601.1 | 27.5 | 24.4 | 240.3 |
| 4,000,000 / smooth | matplotlib-default | 179.5 | 124.3 | 126.9 | 407.2 |

## Functional and packaging checks at this checkpoint

- Installed release wheel: **10 tests passed**, covering independence from
  source mutations, upload reuse, settings replay/image equality, stale/invalid
  settings, PNG scaling, matrix picking, widget editing, pool growth and real
  device-limit errors.
- Chromium with the common ES module/native renderer passed title edits,
  click/drag, clipboard copying and PNG download.
- Actual JupyterLab 4.6.4/kernel/anywidget passed title/color editing, Python
  copying and PNG download, with no page errors in that browser run.
- The historical QtWebEngine desktop host was launched and inspected in a
  headless/offscreen environment. This predates the current winit host.
- Built a Linux CPython 3.12 wheel for glibc 2.35 or later; strict twine checks
  passed.
- Windows/macOS and Python 3.11–3.14 wheel CI were configured but had not been
  run remotely at this checkpoint. CI is currently disabled while stabilizing.
- Actual Windows Qt/hardware checks are in the [separate report](WINDOWS_RESULTS.md).
- PyPI publication and actual macOS GUI verification have not been performed;
  upstream describes Metal support as experimental.

The high-level Python API exposes single-panel plot/scatter/imshow. Multi-panel
figures and high-level pie/bar/boxplot/contour APIs are future scope. Editing
changes appearance, layout and axes rather than dragging original data values.

## Reproduce

```bash
python -m pip install '.[benchmark]'
python benchmarks/compare.py --sizes 100000 1000000 5000000   --kinds line --signals smooth noisy   --backends figgy matplotlib-default matplotlib-unsimplified pyqtgraph-default   --repeats 3 --timeout 90 --output benchmarks/results/my-line.json
python benchmarks/compare.py --sizes 100000 1000000 5000000   --kinds scatter --signals noisy --backends figgy matplotlib-default   --repeats 3 --output benchmarks/results/my-scatter.json
python benchmarks/compare.py --sizes 100000 1000000 4000000   --kinds heatmap --backends figgy matplotlib-default   --repeats 3 --output benchmarks/results/my-heatmap.json
```

[Raw line data](results/llvmpipe-line.json) ·
[Raw scatter data](results/llvmpipe-scatter.json) ·
[Raw heatmap data](results/llvmpipe-heatmap.json) ·
[Comparison chart SVG](results/comparison.svg)
