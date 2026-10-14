# Windows GPU library comparison

2026-10-14 (Asia/Seoul). Follow-up measurements adding fastplotlib, VisPy and
actual pyqtgraph OpenGL rendering.

## Environment and method

- Windows 11; Intel Core i7-13700KF; approximately 64 GiB RAM; RTX 4070 Ti
  12 GiB / NVIDIA 617.14.
- Python 3.13.1; Figgy 0.1.0; fastplotlib 0.7.0 / pygfx 0.17.0 /
  wgpu-py 0.32.0; VisPy 0.17.0; pyqtgraph 0.14.0 / PySide6 6.12.0.
- Completed 960×600 RGBA readback, independent processes per condition and
  medians of five runs.
- Lines 2.5 px; scatter diameter 5 px; identical float64 inputs; no downsampling.
- Figgy GPU coordinates use float64 hi/lo; competing GPU paths use float32.
  pyqtgraph subtracts the center before uploading a float32 VBO.
- Figgy/fastplotlib use Vulkan; VisPy/pyqtgraph use NVIDIA OpenGL 4.6.
- Figgy uses shader AA. fastplotlib uses default pixel_scale=1, PPAA none and
  LineMaterial AA off. VisPy line GL AA and pyqtgraph OpenGL AA are off; VisPy
  scatter uses 1 px marker AA. Pixel quality is not identical across backends.
- Plot viewports are matched, apart from a 0.5 px pyqtgraph difference from Qt
  boundaries. Axes/grid layout and initial automatic limits differ by library.
- Imports/input generation are excluded; data conversion and registration/fit
  are included. Initialization, first frame, repeated rendering, axis/style
  edits and PNG export are reported separately.
- Warm repetitions, with OS/font/driver caches intact. These do not measure
  display FPS or isolated GPU kernel time.
- Worker peak RSS includes inputs/libraries/drivers, not actual VRAM use.

## Repeated RGBA rendering at five million samples (ms)

| Workload | Figgy | fastplotlib | VisPy | pyqtgraph OpenGL | matplotlib default |
|---|---:|---:|---:|---:|---:|
| Smooth line | 9.07 | 12.41 | 4.77 | 4.09 | 99.87 |
| Noisy line | 18.52 | 20.49 | 10.96 | 8.71 | 211.00 |
| Scatter | 9.11 | 10.37 | 12.24 | — | 1357.62 |

pyqtgraph OpenGL and VisPy were faster for five-million-point lines; Figgy was
fastest for scatter. fastplotlib was close to Figgy at that scale. Consider
first-frame and axis/color-edit costs in the full table as well.

## Rendering paths and validation

- **pyqtgraph:** `pg.setConfigOptions(useOpenGL=True, antialias=False)`.
  Actual `GraphicsViewGLWidget` construction and `PlotCurveItem.paintGL`
  execution are verified. `glReadPixels` immediately after QGraphicsView paint
  waits for GPU completion. QImage/QPainter software export is not substituted.
- **fastplotlib:** every offscreen RenderCanvas call forces a full Figure draw
  and returns completed RGBA, rather than reading an old `export_numpy()` frame.
- **VisPy:** `SceneCanvas.render()` draws a new framebuffer then reads RGBA.
  Scatter color changes include resending coordinates through the required
  `Markers.set_data(pos=..., face_color=...)` public API.
- Every successful worker checks first-frame data, retained data in edited PNGs
  and a separate actual red-color edit. These checks occur after timing/peak
  RSS collection and are excluded from the measurements.
- VisPy GL AA-on line results remain in
  [separate JSON](results/windows-rtx4070ti-vispy-aa-line.json). The earlier
  approximately 337 ms noisy five-million-point result used AA on; the main
  table uses default AA off.
- pyqtgraph rows in the [earlier QPainter comparison](WINDOWS_RESULTS.md) use
  `useOpenGL=False` and are separate from these OpenGL results.
- **Plotly:** excluded from this campaign. Kaleido static output goes through
  Chrome/PNG, combining serialization, browser and encoding work with the
  native draw/readback comparison. It needs a separate end-to-end export study;
  see [official static export documentation](https://plotly.com/python/static-image-export/).

## All measurements

| Workload | Signal | Samples | Backend | Status | First frame (ms) | Repeated (ms) | Axis edit (ms) | Color edit (ms) | PNG (ms) | Peak RSS (MiB) |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| line | smooth | 100,000 | figgy | ok | 413.22 | 1.24 | 2.74 | 2.91 | 14.53 | 193.3 |
| line | smooth | 100,000 | matplotlib-default | ok | 31.70 | 12.37 | 11.68 | 11.61 | 28.70 | 76.4 |
| line | smooth | 100,000 | matplotlib-unsimplified | ok | 45.67 | 18.05 | 17.65 | 17.53 | 34.14 | 76.5 |
| line | smooth | 100,000 | pyqtgraph-opengl | ok | 461.93 | 6.83 | 6.84 | 6.84 | 18.97 | 213.8 |
| line | smooth | 100,000 | fastplotlib | ok | 891.52 | 2.84 | 3.11 | 2.49 | 13.75 | 263.6 |
| line | smooth | 100,000 | vispy | ok | 834.70 | 4.06 | 6.61 | 4.11 | 15.10 | 194.6 |
| line | smooth | 1,000,000 | figgy | ok | 416.95 | 2.16 | 3.83 | 4.00 | 16.73 | 207.6 |
| line | smooth | 1,000,000 | matplotlib-default | ok | 76.80 | 30.23 | 29.16 | 27.55 | 43.71 | 132.5 |
| line | smooth | 1,000,000 | matplotlib-unsimplified | ok | 138.21 | 89.32 | 87.70 | 87.25 | 101.25 | 128.1 |
| line | smooth | 1,000,000 | pyqtgraph-opengl | ok | 486.08 | 6.60 | 6.80 | 15.26 | 15.50 | 248.9 |
| line | smooth | 1,000,000 | fastplotlib | ok | 937.03 | 2.75 | 3.52 | 2.66 | 14.98 | 306.3 |
| line | smooth | 1,000,000 | vispy | ok | 817.30 | 4.08 | 6.88 | 4.10 | 16.14 | 227.4 |
| line | smooth | 5,000,000 | figgy | ok | 473.34 | 9.07 | 10.91 | 11.68 | 24.93 | 267.7 |
| line | smooth | 5,000,000 | matplotlib-default | ok | 293.38 | 99.87 | 96.91 | 97.62 | 112.55 | 375.3 |
| line | smooth | 5,000,000 | matplotlib-unsimplified | ok | 628.23 | 422.48 | 421.40 | 422.80 | 434.36 | 401.6 |
| line | smooth | 5,000,000 | pyqtgraph-opengl | ok | 535.87 | 4.09 | 13.45 | 52.86 | 16.06 | 409.8 |
| line | smooth | 5,000,000 | fastplotlib | ok | 1095.22 | 12.41 | 12.71 | 12.41 | 24.79 | 545.9 |
| line | smooth | 5,000,000 | vispy | ok | 923.81 | 4.77 | 7.28 | 5.19 | 18.09 | 365.5 |
| line | noisy | 100,000 | figgy | ok | 443.61 | 1.31 | 2.80 | 3.98 | 20.77 | 197.7 |
| line | noisy | 100,000 | matplotlib-default | ok | 114.91 | 61.51 | 67.80 | 64.94 | 79.82 | 117.9 |
| line | noisy | 100,000 | matplotlib-unsimplified | ok | 176.20 | 136.21 | 135.71 | 136.75 | 147.83 | 167.1 |
| line | noisy | 100,000 | pyqtgraph-opengl | ok | 467.33 | 6.12 | 6.75 | 6.85 | 18.77 | 220.7 |
| line | noisy | 100,000 | fastplotlib | ok | 883.02 | 2.37 | 2.92 | 2.46 | 13.49 | 265.6 |
| line | noisy | 100,000 | vispy | ok | 828.36 | 4.09 | 6.99 | 3.95 | 16.95 | 196.4 |
| line | noisy | 1,000,000 | figgy | ok | 424.63 | 4.22 | 5.98 | 5.75 | 21.53 | 211.2 |
| line | noisy | 1,000,000 | matplotlib-default | ok | 175.78 | 111.00 | 117.76 | 117.24 | 131.23 | 180.0 |
| line | noisy | 1,000,000 | matplotlib-unsimplified | ok | 2115.25 | 1843.28 | 1850.22 | 1848.54 | 1824.10 | 986.8 |
| line | noisy | 1,000,000 | pyqtgraph-opengl | ok | 485.64 | 6.16 | 6.85 | 12.43 | 15.49 | 259.6 |
| line | noisy | 1,000,000 | fastplotlib | ok | 902.83 | 4.89 | 5.39 | 4.87 | 16.77 | 293.8 |
| line | noisy | 1,000,000 | vispy | ok | 817.60 | 5.12 | 7.28 | 4.89 | 16.57 | 229.9 |
| line | noisy | 5,000,000 | figgy | ok | 487.90 | 18.52 | 20.12 | 19.57 | 37.93 | 271.7 |
| line | noisy | 5,000,000 | matplotlib-default | ok | 426.17 | 211.00 | 218.79 | 221.07 | 233.66 | 400.9 |
| line | noisy | 5,000,000 | matplotlib-unsimplified | error | — | — | — | — | — | — |
| line | noisy | 5,000,000 | pyqtgraph-opengl | ok | 532.21 | 8.71 | 23.88 | 59.79 | 19.98 | 409.0 |
| line | noisy | 5,000,000 | fastplotlib | ok | 1081.31 | 20.49 | 20.27 | 19.53 | 31.03 | 545.3 |
| line | noisy | 5,000,000 | vispy | ok | 867.26 | 10.96 | 13.07 | 10.49 | 23.70 | 352.1 |
| scatter | noisy | 100,000 | figgy | ok | 413.79 | 1.21 | 2.60 | 2.78 | 31.82 | 196.3 |
| scatter | noisy | 100,000 | matplotlib-default | ok | 57.66 | 37.52 | 37.76 | 37.14 | 50.21 | 76.3 |
| scatter | noisy | 100,000 | fastplotlib | ok | 866.82 | 2.71 | 2.95 | 2.58 | 15.01 | 264.9 |
| scatter | noisy | 100,000 | vispy | ok | 810.74 | 3.74 | 6.26 | 8.67 | 26.82 | 218.5 |
| scatter | noisy | 1,000,000 | figgy | ok | 423.24 | 2.37 | 4.14 | 4.43 | 39.01 | 210.1 |
| scatter | noisy | 1,000,000 | matplotlib-default | ok | 321.74 | 279.13 | 282.41 | 280.81 | 294.10 | 134.6 |
| scatter | noisy | 1,000,000 | fastplotlib | ok | 956.79 | 3.38 | 3.85 | 3.54 | 15.12 | 293.8 |
| scatter | noisy | 1,000,000 | vispy | ok | 895.49 | 4.94 | 7.44 | 63.95 | 31.04 | 444.4 |
| scatter | noisy | 5,000,000 | figgy | ok | 477.99 | 9.11 | 10.48 | 10.82 | 45.55 | 272.7 |
| scatter | noisy | 5,000,000 | matplotlib-default | ok | 1481.77 | 1357.62 | 1347.93 | 1350.21 | 1359.51 | 394.0 |
| scatter | noisy | 5,000,000 | fastplotlib | ok | 1057.61 | 10.37 | 10.91 | 10.11 | 23.33 | 544.3 |
| scatter | noisy | 5,000,000 | vispy | ok | 1212.84 | 12.24 | 14.84 | 297.67 | 33.61 | 1410.9 |

Of 48 conditions, 47 succeeded, one errored and none timed out.

- `matplotlib-unsimplified / line / noisy / 5,000,000`: error; original message
  retained in JSON.

## Reproduce

```powershell
$env:RUSTUP_TOOLCHAIN = '1.99.0'
.\.venv\Scripts\python.exe -m pip install ".[desktop,notebook,benchmark,benchmark-gpu,test]"
.\.venv\Scripts\python.exe benchmarks/compare.py --sizes 100000 1000000 5000000 --kinds line --signals smooth noisy --backends figgy matplotlib-default matplotlib-unsimplified pyqtgraph-opengl fastplotlib vispy --repeats 5 --timeout 120 --output benchmarks/results/windows-rtx4070ti-gpu-line.json
.\.venv\Scripts\python.exe benchmarks/compare.py --sizes 100000 1000000 5000000 --kinds scatter --signals noisy --backends figgy matplotlib-default fastplotlib vispy --repeats 5 --timeout 120 --output benchmarks/results/windows-rtx4070ti-gpu-scatter.json
.\.venv\Scripts\python.exe benchmarks/plot_results.py benchmarks/results/windows-rtx4070ti-gpu-line.json benchmarks/results/windows-rtx4070ti-gpu-scatter.json benchmarks/results/windows-rtx4070ti-heatmap.json --output benchmarks/results/windows-rtx4070ti-gpu-comparison --subtitle "Windows 11 / RTX 4070 Ti, Vulkan + OpenGL, 5 repeats, 960 x 600 RGBA"
```

The comparison chart is also rendered with Figgy. Four completed panels are
arranged as pixels, and the SVG embeds PNG. The heatmap panel uses the previous
Figgy/matplotlib campaign; heatmaps from additional GPU libraries were outside
this run's scope.

[Line JSON](results/windows-rtx4070ti-gpu-line.json) ·
[Scatter JSON](results/windows-rtx4070ti-gpu-scatter.json) ·
[Chart rendering record](results/windows-rtx4070ti-gpu-comparison.rendering.json)

![GPU library comparison rendered with Figgy](results/windows-rtx4070ti-gpu-comparison.svg)
