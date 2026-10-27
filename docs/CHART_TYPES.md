# Charts, materials and draw styles

The Python package calls the public upstream models and GPU renderers. Pies and
donuts use `RadialChart` / `RadialRenderer`; handwriting and star modes use
Cartesian `DrawStyle`. No chart images are synthesized by a Python drawing engine.
See the [gallery and runnable examples](../examples/README.md).

## Pie and donut

```python
import figgyplot as figgy

fig, ax = figgy.subplots(backend="native", figsize=(8, 5), dpi=120)
ring = ax.donut(
    [40, 25, 20, 15],
    labels=["Search", "Direct", "Email", "Other"],
    colors=["#3384f5", "#a5d848", "#ff973e", "#30c0e6"],
    inner_radius=0.5,
    material="ceramic", tilt=55, depth=0.16,
    inner_corner=0.045, outer_corner=0.045,
    bevel=0.025, gap_degrees=1.4, shadow=True,
)
ax.set_title("Traffic sources", fontsize=18)
try:
    fig.show()
    fig.savefig("donut.png")
finally:
    fig.close()
```

Use `ax.pie(values, ...)` for a filled circle. `ax.donut` accepts the same options
and defaults to `inner_radius=0.5`. The stateful `figgy.pyplot.pie()` and
`donut()` wrappers are available too.

| Argument | Meaning |
| --- | --- |
| `values` | 1–64 finite nonnegative values with a positive finite sum |
| `labels`, `colors`, `explode` | One item per category; colors must be opaque |
| `startangle` | Degrees from the right, positive toward the top; default 90 starts at the top |
| `inner_radius` | Donut hole as a fraction of outer radius, 0.1–0.85 |
| `labels_position` | `none`, `inside` or `outside` |
| `label_format` | `name`, `value`, `percent`, `name_percent`, `name_value`, `value_percent` or `name_value_percent` |
| `tilt`, `depth` | Camera tilt 0–65 degrees; extrusion depth 0–0.4 radii |
| `material` | One of the eleven materials below |
| Remaining style keywords | Upstream `RadialStyle` fields, such as texture strength/scale, gloss, roughness, corners, bevel, gap and shadow |

Setting a material leaves the chosen camera/depth unchanged. A top-down flat
chart remains flat until tilt and depth are explicitly set. Zero-valued slices
retain their original indices but have no visible surface/label. Data-label font
size remains chart-wide; `ax.set_title` now owns independent rich title styling.
Python point values are converted at the Figure's DPI. The bounded model requires
a canvas of at least 160×160 logical pixels.
Its shared annotation size is 8–64 renderer pixels; use export scaling for
higher-resolution output without increasing the logical font size.
Export scale is 0.5–4, subject to the device's texture limit.

Pie/donut Figures cannot mix Cartesian series. Axis limits, axis labels, grids and Cartesian legends
are rejected for this chart family; use radial labels and properties instead.
They share the native GPU device with other Figures and own their upstream
radial renderer/frame caches.
Their small category values remain in the validated CPU model; they do not use
the large Cartesian column pool. Source NumPy mutations do not change them.

## Materials and edits

Available material names:

`flat`, `matte`, `ceramic`, `brushed_metal`, `paper`, `wood`, `satin_metal`,
`toon`, `enamel`, `hatch`, `pearl`.

```python
# After creating a pie/donut:
fig.set_radial_style(material="wood", texture_strength=0.8, texture_scale=1.5,
                     roughness=0.85, gloss=0.1)
ring.set_slice(0, color="#be5133", label="Search ads", explode=0.08)
ring.set_slice(1, material="pearl")
ring.set_values([35, 30, 20, 15])  # Same slice count; explicit data replacement.
```

A per-slice style inherits the current chart style when first created, then
becomes an independent complete override. Later chart-style edits do not change
that override. Advanced `fig.configure_radial(...)` patches expose the upstream
serialized fields. Its `slices={index: patch}` changes appearance/labels; category
values are replaced explicitly through `set_values()`.

Click a slice in a native window or Jupyter WebGPU widget to select/clear it.
Left/Right cycle visible slices; Esc clears selection. Properties edit the title,
pie/donut shape, hole, material, camera, texture, lighting-related settings,
labels and the selected
slice's name/value/color/explode. Native properties expand a normal window;
maximized or fullscreen windows use an overlay. Native Advanced settings uses a
separate window; Jupyter exposes the JSON in its property panel. Copy Python and
Save PNG use the same document as the preview in either host.

On the native backend, `fig.select(x, y)` also picks a slice at logical document
coordinates and returns its index, label and value. On WebGPU, pick in the widget.
Picking and window redraw do not read back a full RGBA image. PNG/RGBA export is an explicit operation.

## Handwriting, constellation and Milkyway

```python
# On an existing Cartesian Figure:
fig.set_draw_style("sketch", amplitude_px=1.5, wavelength_px=64, seed=7)
fig.set_draw_style("precise")
```

| Mode | Supported series and appearance |
| --- | --- |
| `precise` | Default scientific rendering |
| `sketch` | Line, scatter and errorbar series: hand-drawn paths/decoration strokes and bundled Comic Neue handwriting |
| `constellation` | `ax.plot(..., marker="o")`: stars at the actual source samples, connected by translucent lines |
| `milkyway` | Line-only series: star chains and series-colored nebula ribbons |

**Milkyway scatter and marker-line series are intentionally disabled.** Setting
it on a Figure containing scatter, marker lines or a heatmap raises `ValueError`.
Sketch does not draw bars, heatmaps or contours, so setting it on a Figure with
one (or adding one afterwards) also raises `ValueError` instead of leaving the
plot empty.
Adding those series afterward is also rejected. Raw settings, advanced JSON and
browser edits enforce the same rule. The native Style menu disables incompatible
choices. Constellation requires marker lines, avoiding silently invisible series.

```python
import numpy as np
import figgyplot as figgy

fig, ax = figgy.subplots(backend="native")
t = np.linspace(0, 12, 1800)
ax.plot(t, np.sin(t), id="stream")  # No marker: Milkyway is line-only.
fig.set_draw_style("milkyway", seed=9610, star_density=20,
                   ribbon_width_px=16, ribbon_intensity=0.3)
try:
    fig.show()
finally:
    fig.close()
```

Constellation options include `star_opacity` and `line_opacity`. Milkyway exposes
upstream density, ribbon, spread, star brightness/scale, glow, backdrop and seed
parameters. Invalid/unknown options preserve the accepted document. See
[sketch](../examples/sketch_style.py),
[constellation](../examples/constellation_style.py) and
[Milkyway](../examples/milkyway_style.py) recipes for complete styling.

Use `fig.set_facecolor("#0b0f17")` with light axis/text/legend colors for a dark
constellation chart. The examples configure those explicitly. These settings
also cross the browser widget, which calls upstream `set_clear_color`.

## Export and host coverage

`fig.to_code()` and native Copy Python preserve draw-mode parameters and radial
materials. Radial exports contain appearance and label patches, not category
values: recreate a pie/donut with the same slice count and DPI, then apply the
code. Transient radial hover and slice selection are cleared in exported
style code, so a selected source slice can become zero-valued in a new dataset.
Cartesian style exports do not serialize source arrays. They require matching
series IDs and kinds and preserve the destination's uploaded data. Stylized
patterns use stable user series IDs even when independent Figures share a GPU,
so replay does not reroll stars or handwriting.

Cartesian styles are exposed in native and WebGPU document models and their
Style menus. Unsupported chart/style combinations are rejected in both hosts.
Pies, donuts, categorical bars and boxplots also support browser WebGPU editing
and async PNG export. An explicit native `widget(backend="png")` remains available
as a kernel-GPU fallback; it uses the separate PNG transport editor.

## Python constructors and host coverage

Every row below is available on native desktop and Jupyter WebGPU. The browser
uses the same pinned upstream Rust models/renderers compiled to WASM. Neither
host transports a PNG for ordinary redraws.

| Python API | Upstream family |
| --- | --- |
| `plot`, `scatter` | Line, Scatter, ScatterLine |
| `errorbar(..., xerr=..., yerr=...)` | ScatterErrorbarX/Y/XY, LineScatterErrorbarX/Y/XY |
| `hist`, `stairs` | Histogram |
| `imshow` | Heatmap |
| `contour`, `contourf` | Contour, HeatmapContour |
| `pie`, `donut` | RadialChart |
| `bar`, `barh` | CategoricalChart |
| `boxplot`, `bxp` | BoxPlotChart |

```python
fig, ax = figgy.subplots()  # auto: Jupyter WebGPU in a kernel, native elsewhere
bars = ax.bar(["A", "B", "C"], [[4, 2, 6], [3, 5, 1]],
              label=["Before", "After"], mode="grouped")
ax.set_title("Category comparison")
ax.set_ylabel("Count")
# Choose fig.show() on desktop or display(fig.widget()) in Jupyter.
```

The following calls are independent examples, not one combined document.
Errorbars, histograms and contours are Cartesian and can share a Figure or grid.
Bars, boxplots, radar and pies/donuts each need a separate single-panel Figure;
they cannot mix with Cartesian series or occupy grid slots.

```python
ax.errorbar([1, 2, 3], [2, 4, 3], yerr=[[.1, .2, .3], [.2, .1, .2]], xerr=.1)
counts, edges, artist = ax.hist(samples, bins=20)
artist = ax.stairs([2, 5, 3], [0, 1, 2, 4], baseline=0)
ax.contour(z, levels=[.2, .4, .6])
ax.contourf(x_centers, y_centers, z, levels=[.2, .4, .6])
ax.boxplot([[1, 2, 3, 8], [2, 4, 5]])
ax.bxp([dict(q1=1, med=2, q3=3, whislo=0, whishi=4, fliers=[7])])
```

`errorbar` accepts scalar, N-element symmetric or 2-by-N asymmetric magnitudes;
errors must be finite and nonnegative. `linestyle=None` omits connecting lines.
`hist` delegates bin calculation to NumPy; `stairs` accepts explicit edges and
counts. Selecting a histogram bin shows its index, start/end bounds and stored
value (count, weighted total, density or stairs height) in both hosts. Contours
accept a 2-D scalar array with optional 1-D x/y center coordinates.

`bar` accepts one value per category or a series-by-category matrix. `None`
is missing, zero is a real value. Modes are `grouped`, `stacked` and
`percent_stacked`; horizontal direction is available through `barh`. Upstream
bounds are 64 categories, 16 series and 512 bars. `boxplot` treats a 1-D array as
one box and a sequence of arrays as one box per array; it computes NumPy linear
quartiles, actual sample whiskers within `whis * IQR` (default 1.5), and all
outliers. It does not silently drop outliers to fit the bounded limits (128 per
box, 4096 total). `bxp` uses supplied statistics without recomputing them.
Axis names may be set before or after `bar`/`barh`/`boxplot`/`bxp`. Horizontal
charts map the X name to the value axis and the Y name to the category axis.
Explicit `category_title`/`value_title` constructor properties override inherited
names, including an explicit empty string. Category labels and these axis names
are single-line; use the chart title or annotations for longer descriptions.
The hollow circles beyond the whiskers are these individual outlier values.
They are data points, not extra boxes or selection handles. With the default
`whis=1.5`, the fences are `Q1 - 1.5*IQR` and `Q3 + 1.5*IQR`; whiskers extend
to the most extreme observations inside those fences.

Use `fig.configure_bounded(style={...}, ...)` or the returned artist's
`set`/`set_style` for selective SSOT patches. Unspecified fields are preserved;
these setters do not perform automatic layout or adjust ticks. Constructors and
`fit()` are convenience helpers that may compute statistics, ranges, ticks or
layout. Copy Python replays style/configuration against matching category and
series IDs, preserving the destination's data values.

`ax.set_title("Comparison\nObserved sample", fontsize=18)` uses the independent
rich title, with up to 512 characters and eight lines. It does not change the
category/data-label font. Titles set before construction keep their text and
rich formatting. The legacy single-line `title` is only a compatibility fallback;
`chart_title.text.segments` holds the complete displayed wording. Raw SSOT edits
still have to satisfy both fields' model constraints.

For Cartesian charts, `ax.legend(loc="upper left")` accepts upper/lower left/right
and their renderer names (`TopLeft`, `TopRight`, `BottomLeft`, `BottomRight`).
`fig.update("legend", corner="TopLeft", fontsize=11)` edits the existing legend.
Bounded legends expose visibility through `ax.legend(False)`; `loc` is rejected.

Use `ax.invert_yaxis()` for depth increasing downwards, after setting increasing
limits such as `ax.set_ylim(0, 700)`. Inversion preserves limits and tick spacing;
on `twinx` it affects only that Y axis. Cartesian tick spacing is configurable
with `fig.update("axis_bottom", major_spacing=2, minor_count=0)`. Explicit
arbitrary tick-position setters are not part of the API.

Both hosts open the property panel on selection. Drag annotations to move them;
use Layout and plot-area handles to resize; Fit restores automatic plot layout.
Left/right arrows step through bounded data selections, Escape clears selection,
and arrows move a selected decoration (Shift uses ten-pixel steps). Cartesian
wheel zoom anchors at the pointer; Ctrl restricts X, Shift restricts Y, and a
left-button drag inside the plot pans. CI exercises these shared contracts;
see [contributing](../CONTRIBUTING.md#nativejupyter-synchronization-contract).
