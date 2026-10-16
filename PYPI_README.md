# figgyplot

**Plot NumPy data on the GPU. Edit directly. Reuse the settings in Python.**

Explore lines, scatter, errorbars, histograms, heatmaps, contours, categorical
bars, boxplots, pies and donuts in native windows or Jupyter.
Adjust the axes, text, colors and layout, then copy executable Python to reuse
the result across datasets. Export the edited chart directly to PNG.

[Examples](https://github.com/shim9610/figgy-python/tree/main/examples) ·
[Documentation](https://github.com/shim9610/figgy-python/tree/main/docs) ·
[Measured performance](https://github.com/shim9610/figgy-python/blob/main/benchmarks/WINDOWS_GPU_RESULTS.md)

![Actual native editor: adjust the plot, move the legend, copy Python and reuse the settings across datasets](https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/edit-and-reuse.gif)

*100,000 samples per series. Edit the native plot, copy Python, paste into
VS Code and apply the same settings to three independent datasets.*
[Demo recipe and recording](https://github.com/shim9610/figgy-python/blob/main/docs/README_DEMO.md).

## Scientific plots

Every image below is actual Figgy output from synthetic data. Click a chart
to open its runnable Python example.

<table>
  <tr>
    <td align="center"><strong>Spectrogram</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/spectrogram.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/spectrogram.png" alt="Short-time spectrum of a chirp" width="180"></a></td>
    <td align="center"><strong>Correlation matrix</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/correlation_matrix.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/correlation-matrix.png" alt="Twelve-channel correlation matrix" width="180"></a></td>
    <td align="center"><strong>Scatter populations</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/scatter_clusters.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/scatter-clusters.png" alt="Three scatter populations" width="180"></a></td>
  </tr>
  <tr>
    <td align="center"><strong>Interpolated heatmap</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/heatmap_field.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/heatmap-field.png" alt="Signed interference field" width="180"></a></td>
    <td align="center"><strong>Logarithmic axes</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/log_scales.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/log-scales.png" alt="Power laws on logarithmic axes" width="180"></a></td>
    <td align="center"><strong>Lines and measurements</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/line_markers.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/line-markers.png" alt="Model curve and measured markers" width="180"></a></td>
  </tr>
</table>

## Draw styles

<table>
  <tr>
    <td align="center"><strong>Sketch / handwriting</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/sketch_style.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/sketch-style.png" alt="Hand-drawn curves on warm ivory paper" width="180"></a></td>
    <td align="center"><strong>Constellation</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/constellation_style.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/constellation-style.png" alt="Stars connected at source samples" width="180"></a></td>
    <td align="center"><strong>Milkyway</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/milkyway_style.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/milkyway-style.png" alt="Line-only star chains and nebula ribbons" width="180"></a></td>
  </tr>
</table>

## More chart families

<table>
  <tr>
    <td align="center"><strong>Parametric curves</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/parametric_curves.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/parametric-curves.png" alt="Layered parametric traces" width="180"></a></td>
    <td align="center"><strong>Pie</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/pie_chart.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/pie-chart.png" alt="Labeled and exploded pie slices" width="180"></a></td>
    <td align="center"><strong>Ceramic donut</strong><br><a href="https://github.com/shim9610/figgy-python/blob/main/examples/donut_chart.py"><img src="https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/donut-chart.png" alt="Raised ceramic donut with rounded corners" width="180"></a></td>
  </tr>
</table>

[Procedural materials: paper, wood, hatch and pearl](https://github.com/shim9610/figgy-python/blob/main/docs/CHART_TYPES.md) ·
[Gallery rendering provenance](https://github.com/shim9610/figgy-python/blob/main/docs/images/gallery/manifest.json).

## Performance measurements

An earlier Windows 11 / RTX 4070 Ti campaign measured completed 960×600 RGBA
rendering at five million samples. Medians of five repeated renders, in ms:

| Workload | Figgy | fastplotlib | VisPy | pyqtgraph OpenGL | matplotlib default |
| --- | ---: | ---: | ---: | ---: | ---: |
| Smooth line | 9.07 | 12.41 | 4.77 | 4.09 | 99.87 |
| Noisy line | 18.52 | 20.49 | 10.96 | 8.71 | 211.00 |
| Scatter | 9.11 | 10.37 | 12.24 | — | 1357.62 |

This historical campaign used Figgy 0.1.0. Precision and antialiasing differed
between libraries; first-frame, upload, edits and export costs are reported
separately. These measurements include RGBA readback and do not measure UI FPS.
[Full conditions, results and the comparison chart rendered with Figgy](https://github.com/shim9610/figgy-python/blob/main/benchmarks/WINDOWS_GPU_RESULTS.md).

## Install

This description covers **figgyplot 0.3.0**. Until that version is published,
PyPI provides 0.2.1; use the [source-checkout instructions](https://github.com/shim9610/figgy-python#install)
for the upcoming features.

Install from PyPI:

```sh
python -m pip install figgyplot
```

For interactive editing in Jupyter, install the notebook extra:

```sh
python -m pip install 'figgyplot[notebook]'
```

Compatible Windows, macOS and Linux wheels include the native extension and
notebook JS/WASM assets. No Rust compiler is needed when a compatible wheel
is available.

## Quick start

```python
import numpy as np
import figgyplot as plt

x = np.linspace(0, 20, 100_000, dtype=np.float32)
fig, ax = plt.subplots(backend="native", figsize=(8, 5), dpi=120)
ax.plot(x, np.sin(x), id="signal")
ax.set_title("Edit, copy Python, and reuse")
try:
    fig.show()                  # Edit; close the window to continue.
    fig.savefig("edited.png")  # Save the edited chart without the UI.
finally:
    fig.close()
```

In Jupyter, use `plt.subplots(backend="webgpu")` and display `fig.widget()`.
Selection and editing run in the notebook's browser. Both hosts expose tick
visibility/direction, numeric notation/significant digits, rich text editing,
axis/color logarithms and histogram-bin values. Matching opposite axes share
only the fields you edit; direct SSOT patches remain exact. Log views omit
nonpositive samples without changing the source arrays. See the
[editor guide](https://github.com/shim9610/figgy-python/blob/main/docs/DESKTOP_EDITOR.md)
for these controls and matrix Fit behavior.

## Compatibility

CPython 3.8–3.15. A compatible wheel needs no Rust compiler; source builds need
Rust 1.99+ and a C/C++ toolchain. Native rendering needs a supported GPU driver.
Jupyter needs a WebGPU-capable browser over HTTPS or localhost. Native window
creation and event pumping must run on the main thread.
Native windows use the Rust winit/wgpu host; Jupyter uses packaged WASM and
browser WebGPU. Normal wheel installation requires no separate WASM build or CDN.

[Documentation](https://github.com/shim9610/figgy-python/tree/main/docs) ·
[Examples](https://github.com/shim9610/figgy-python/tree/main/examples) ·
[Platform compatibility and verification](https://github.com/shim9610/figgy-python/blob/main/docs/DISTRIBUTION.md)

The distribution and import name are both **figgyplot**. This is independent of
the unrelated `figgy` distribution on PyPI. MIT OR Apache-2.0.
