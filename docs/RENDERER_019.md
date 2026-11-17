# Renderer 0.19 Python API

This development integration awaits the official upstream 0.19 release and final
package pinning. See the [migration validation](RENDERER_019_AUDIT.md).

The native extension and bundled WebAssembly module use the same upstream
[integration revision](https://github.com/shim9610/figgy/commit/f5f611c4532b037f8c3b3087fab22a9f47852343).
Settings identify this integration as `0.19.0`. The upstream branch still declares
renderer package version `0.18.1`; the Git revision pins the actual API and shader
source. Rebuild the browser module with `scripts/build-wasm.sh` when changing it.

## Construct and edit charts

The object interface follows `fig, ax = figgyplot.subplots()` and `ax.plot(...)`.
The same constructors are available through `figgyplot.pyplot`. Use `id=` where a
constructor accepts it to give a series a stable address for later edits.

| Data and geometry | Constructors |
| --- | --- |
| Lines and points | `plot`, `scatter`, `step`, `stem`, `errorbar`, `fill_between` |
| Categories and distributions | `bar`, `barh`, `hist`, `stairs`, `boxplot`, `bxp`, `violinplot`, `raincloud` |
| Intervals and financial data | `range_bars`, `broken_barh`, `waterfall`, `candlestick` |
| Fields and flow | `imshow`, `imshow_rgb`, `contour`, `contourf`, `hexbin`, `quiver`, `streamplot`, `streamlines` |
| Meshes and 3-D data | `tripcolor`, `tricontour`, `tricontourf`, `plot_surface`, `plot_trisurf`, `plot3D`, `scatter3D`, `quiver3D` |
| Other coordinate systems | `radar`, `rose`, `ternary`, `parallel_coordinates` |
| Radial hierarchies and diagrams | `pie`, `donut`, `sunburst`, `energy_levels`, `feynman` |

```python
import numpy as np
import figgyplot as fg

with fg.Figure(backend="native") as fig:
    ax = fig.axes[0]
    ax.stem(np.array([1, 3, 2], dtype=np.float32), id="observations")
    ax.set_xlabel("Sample")
    ax.set_ylabel("Response")
    fig.set_theme("warm-paper")
    fig.tight_layout()
    fig.savefig("observations.svg", scale=2)
    fig.savefig("observations.pdf", scale=2)
```

`streamplot(x, y, u, v)` integrates a rectilinear vector field on the Python host.
`streamlines(x, y)` accepts precomputed paths with NaN separators. Violin density
estimation, hexagonal bin aggregation and box statistics are also host operations;
the resulting columns are drawn by the common renderer.

Mesh calls require explicit integer `triangles` of shape `(N, 3)`. `tripcolor`
uses one value per vertex with `shading="gouraud"`, or one value per triangle with
`shading="flat"`. Surface calls accept rectilinear X/Y grids; use `plot_trisurf`
for a mesh with arbitrary vertex positions.

`sunburst` accepts nested dictionaries containing `label`, `value` and `children`,
or parallel labels, parents and values. `energy_levels` and `feynman` accept row
mappings, NumPy structured arrays, column mappings or DataFrame-like tables.
NumPy scalars/coordinate arrays normalize to document values, and plain string
labels inherit the panel's rich text style. Energy levels require `id`, `column`
and `energy`; transitions require `id`, `lower` and `upper`. Feynman vertices
require `id`, and propagators require `id`, `from`, `to` and `particle`. Unplaced
vertices use the renderer's automatic layout. Use
`direction="bottom-to-top"` or `layout={"direction": "BottomToTop"}` for its
orientation. This draws the supplied topology; it does not infer reactions or
check conservation laws.

Diagram calls return a `DiagramArtist`. Its `level(id)`, `transition(id)`,
`limit(id)`, `band(id)`, `vertex(id)` and `propagator(id)` handles resolve stable
record IDs again on each edit. Reordering records does not retarget an existing
handle. Artist setters return the artist, so styling calls can be chained.

```python
levels = ax.energy_levels([{"id": "ground", "column": "S", "energy": 0}])
levels.level("ground").set_label("Ground state").set_label_offset((3, -2))

reaction = ax.feynman(
    [{"id": "a", "role": "incoming"}, {"id": "b", "role": "outgoing"}],
    [{"id": "p", "source": "a", "target": "b", "particle": "fermion"}],
)
reaction.set_color("navy").set_linewidth(1.5)
reaction.vertex("a").set_position((0.2, 0.5)).set_label("electron")
reaction.propagator("p").set_bend(20).set_linewidth(2)
reaction.propagator("p").set_momentum("q", side="right", label_offset=(2, -1))
```

`source`/`target` and `from_`/`to` are Python aliases for propagator endpoints.
Enum names accept lower-case words and underscores; plain strings and `TextRun`
labels are supported. Energies and vertex positions use data units. Common
line widths, marker radii, text sizes and label offsets in the handle API use
points. Advanced fields passed through `set_style(**properties)` retain their
renderer model units. `vertex.set_position(None)` and `propagator.set_bend(None)`
restore renderer placement and automatic bends. `set_momentum(None)` clears a
propagator momentum arrow. `get_position()` returns the
stored override or `None`; it does not calculate a provisional layout.

Individual propagators support stroke overrides. Energy strokes share the
series style; use `levels.set_style(level={...}, transition={...})` for those
public model fields. These methods do not infer atomic or particle physics.

`read_nist` reads NIST Atomic Spectra Database CSV files, CSV text, text streams
or tables. It preserves the exported energy/wavelength units, qualifiers,
uncertainties and references, separates ionization limits and links transitions
by configuration, term and J. Observed wavelengths take priority with Ritz
fallback; `wavelength="ritz"` reverses that choice. Unknown level references
raise by default; explicit `unmatched="skip"` records their count in the result.
It does not fetch a URL, convert units, infer missing transitions or collapse
fine structure into centroids.

```python
data = fg.read_nist("levels.csv", "lines.csv")
fig, ax = fg.subplots(backend="native")
ax.energy_levels(data)  # also names the Y axis using the exported energy unit
fig.set_theme("warm-paper").tight_layout()
fig.savefig("levels.pdf")
```

Use `inspect.signature` or MCP `capabilities` for supported chart arguments.
Advanced appearance remains editable through `fig.configure(series={id: patch})`.
The current integration's compatibility status is recorded in
[the audit](RENDERER_019_AUDIT.md).

## Themes, layout and axes

The themes are `gallery`, `cool-slate`, `midnight` and `warm-paper`.
`fig.set_theme(name)` applies the renderer theme across the document and fits its
layout. `fig.tight_layout()` uses upstream text and decoration measurements;
`fig.constrained_layout()` is an alias for that explicit layout pass.
Native and notebook editor toolbars provide theme selection and **Auto layout**.

The [runnable gallery](../examples/renderer_019.py) draws stem, violin, waterfall
and RGB charts with all four themes. These images are renderer output:
[gallery](images/renderer-019-gallery.png),
[cool-slate](images/renderer-019-cool-slate.png),
[midnight](images/renderer-019-midnight.png) and
[warm-paper](images/renderer-019-warm-paper.png).
Run `python examples/renderer_019.py --formats png svg pdf` to export the examples.

`ax.twiny()` creates an overlay with its own X axis and a linked Y axis;
`ax.twinx()` provides the converse. Axis units, discontinuities and probability
paper are available through `set_axis_unit`, `set_axis_breaks` and
`set_probability_scale`. `view_init`, `set_zlim` and `set_zlabel` edit a 3-D view.

## PNG, SVG and PDF

`fig.savefig(path, format=None, scale=1)` selects a format from the extension or
an explicit `format`. `fig.export("png")` and `fig.export("pdf")` return bytes;
`fig.export("svg")` returns text. A scale increases the raster resolution used
for data within SVG/PDF as well as the PNG resolution. SVG/PDF use upstream
hybrid export, retaining supported text and decorations as vector content.

For a displayed notebook, use `await fig.savefig_async(path)` or
`await fig.export_async(format)`. Rendering and export run in the browser's
WebGPU device. Source columns travel as binary buffers, including record,
ragged and triangle resources; they are not serialized as JSON number lists.
Notebook transfer snapshots are released after acknowledgement unless the Figure
was created with `retain_notebook_data=True`.

## Input precision and memory

Contiguous NumPy `float32` and `float64` arrays retain their input precision and
are borrowed during native upload. Strided arrays require a temporary contiguous
conversion. `float16`, booleans and integers of up to 16 bits convert to
`float32`; wider integers convert to `float64` to preserve their larger exact
integer range. The renderer's floating-point representation still limits values
outside that range. Triangle indices upload as `uint32`.

A notebook transfers an f32 scalar in four bytes instead of eight for f64.
The upstream GPU scalar representation uses two f32 lanes (eight bytes) for
both input types; choosing f32 reduces host conversion and transfer costs, and
does not halve that GPU allocation. Native uploads retain no permanent CPU copy
of the caller's source arrays.

## Saved settings

Current coordinate documents accept the compatible `0.17.0`, `0.18.0` and
`0.18.1` settings stamps and return the `0.19.0` stamp. Categorical, box and radar
charts now use common series and columns, allowing them to share document panels.
Their former top-level inline chart objects are no longer the current settings
shape. `fig.apply_settings(old_document)` can import such an inline legacy chart
into an empty Figure through the upstream conversion helpers.

Copy Python for advanced coordinate charts keeps source columns resident and
reapplies appearance and layout together with `preserve_data=True`. It checks
matching panel, category, series and source bindings before committing, and
preserves destination energy-level records and Feynman topology. A mismatched
structure raises atomically. Value-label format changes currently require
formatting on the destination before replay; destination formatted text is
retained rather than copied from a different dataset. Read the current model with `get_settings()` before
writing direct configuration patches.

## Local MCP server

Install `pip install 'figgyplot[mcp]'` with Python 3.10 or newer and start
`figgyplot-mcp` (or `python -m figgyplot.mcp`). The Model Context Protocol (MCP)
server uses stdio and holds its figures in that process.

Tools cover discovery (`capabilities`), creation (`figure_create`), chart
construction (`chart_add`), inspection and editing (`figure_get`, `figure_patch`),
themes and layout (`figure_theme`, `figure_layout`), file output (`figure_export`)
and resource release (`figure_close`). Chart construction uses the Python method
arguments and validation. Tools do not evaluate arbitrary Python code.

## Named category-chart editing

Bars, boxes and radar plots expose the existing `ax.chart` editing handles over
common renderer series. IDs come from `get_series()` and `get_categories()`:

```python
import figgyplot as fg

fig, ax = fg.subplots(backend="native")
ax.bar(["A", "B"], [2.25, 6.75])
sid = next(iter(ax.chart.get_series()))
cid = next(iter(ax.chart.get_categories()))
ax.chart.series(sid).set_label("Measured").set_style(linewidth=1.5)
ax.chart.cell(cid, sid).set_color("red").set_value_labels(position="outside")
ax.chart.set_value_labels(format="value", decimals=2, suffix=" eV")
ax.chart.cell(cid, sid).set_label("Reference")  # custom text after number formatting
ax.chart.decoration("value_label", category=cid, series=sid).set_offset((2, 3))
ax.chart.set_plot_bounds((70, 45, 300, 200))  # points: left, top, width, height
ax.chart.set_plot_bounds()                  # measured automatic layout
```

`cell.set_label(text)` and `cell.get_label()` edit/read one displayed label;
`set_label(None)` clears its text. Changing number-format settings regenerates
the numeric labels, so apply custom text afterwards.

Coordinate-chart decimals are integers from 0 through 6. Bar percentages are
shares across series within each category. Box labels use median/sample count;
radar labels use the vertex values. Cell overrides apply to bars and boxes.
Series styles on the common model are resolved per series; resetting a series
uses renderer defaults, while resetting a cell restores series inheritance.
`ax.chart.get_style()` reports the first matching series' effective appearance.
Spoke label offsets use points along/across that spoke, as defined by the renderer.
Radar selection uses rings; the old `emphasis_brightness` option is rejected
because it has no equivalent in the common series model.

`fig.apply_style(...)`, Figure style defaults and execution `style_context(...)`
apply family-specific presets as well as shared typography. Explicit constructor
arguments take precedence. Lengths in portable tokens and named controls use points.

SVG/PDF page dimensions follow Figure inches at every DPI. For example,
`Figure(figsize=(4, 3), dpi=72)` exports a 288×216 pt page; `scale=2` increases
embedded raster resolution without changing its physical dimensions. The native
save dialog, `savefig`, and notebook `await fig.savefig_async(...)` use this rule.
