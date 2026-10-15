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
retain their original indices but have no visible surface/label. Font size is
shared by radial annotations; Python point values are converted at the Figure's
DPI. The bounded model requires a canvas of at least 160×160 logical pixels.
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

Click a slice in a native window to select/clear it. Left/Right cycle visible
slices; Esc clears selection. Properties edit the title, pie/donut shape, hole,
material, camera, texture, lighting-related settings, labels and the selected
slice's name/value/color/explode. Properties expand a normal window; maximized
or fullscreen windows use an overlay. Advanced settings uses a separate window.
Copy Python and Save PNG use the same document as the native preview.

`fig.select(x, y)` also picks a slice at logical document coordinates and returns
its index, label and value. Picking and window redraw do not read back a full
RGBA image. PNG/RGBA export is an explicit operation.

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
Cartesian exports preserve uploaded series data and require matching IDs and
kinds. Stylized patterns use stable user series IDs even when independent
Figures share a GPU, so replay does not reroll stars or handwriting.

Cartesian styles are exposed in native and WebGPU document models. Native
rendering, high-DPI replay and actual X11 style-menu input are tested. Browser
model/transport changes are included; real browser pixel validation of the new
styles has not been rerun in this checkpoint.

Pie/donut editing and export currently require `backend="native"`. A native
radial Figure can display a static PNG in a notebook when the kernel has a GPU;
interactive browser WebGPU radial bindings are not exposed yet.
