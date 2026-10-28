# Matplotlib-shaped plotting API

Figgy implements a plotting subset with Figure, Axes, Axis, Text, Spine,
Legend and Artist handles. NumPy is the only required Python dependency;
Matplotlib is used as an independent reference in tests, not at runtime.

```python
import figgyplot as fg
from figgyplot.ticker import MultipleLocator

fig, ax = fg.subplots(figsize=(7, 4), dpi=120)
line, = ax.plot([0, 1, 2], [2, 1, 4], lw=2, marker="o", label="Signal")
ax.set(title="Measured signal", xlabel="Time (s)", ylabel="Amplitude")
ax.set_xlim(-0.5, 2.5)
ax.xaxis.set_major_locator(MultipleLocator(0.5))
ax.tick_params(direction="out", labelsize=10)
ax.spines["top"].set_visible(False)
ax.grid(True, axis="y", color="gray", alpha=0.3)
legend = ax.legend(loc="upper left", fontsize=10)
ax.title.set_fontweight("bold")
line.set_color("C2")
fig.savefig("signal.png")
```

Font sizes, line widths, tick lengths and line-marker diameters use points.
Scalar **and array** `scatter(s=...)` values are marker areas in points squared.
Previously, array sizes were automatically normalized into a diameter range;
that was inconsistent with Matplotlib. Explicit `size_domain` / `size_range`
select Figgy's optional data-to-size mapping instead.

`scatter(c=...)` accepts a single color, explicit color lists/RGB(A) rows, or
numeric values for a scalar map. Explicit colors do not create a colorbar. CSS
named colors, grayscale strings, `C0` cycle references and short colors are
supported. Independent opacity for scalar-mapped points requires renderer
support and raises explicitly; uniform/explicit-color opacity is supported.

`set_title`, `set_xlabel` and `set_ylabel` return editable Text handles. `plot`
returns a list of artists, while `scatter` and `imshow` return one artist.
`ax.lines`, `ax.collections`, `get_legend()` and stable `fig.artist(id)` lookup
edit existing objects without uploading their source columns again.

```python
points = ax.scatter([0, 1], [2, 3], s=[16, 64], c=[10, 20], cmap="viridis")
bar = fig.colorbar(points, ax=ax, label="Temperature")
points.set_cmap("magma")
points.set_clim(5, 25)
bar.ax.tick_params(labelsize=10)

note = ax.text(0.05, 0.95, "Review", transform=ax.transAxes)
note.set_text("Reviewed")
ax.annotate("Peak", xy=(1, 3), xytext=(0.5, 0.8),
            textcoords="axes fraction", arrowprops={"arrowstyle": "->"})
```

`transAxes` and `axes fraction` use a bottom-left origin, as in Matplotlib.
The older Figgy `coords="ratio"` option keeps its top-left origin for existing
scripts. Text layout uses Figgy's renderer; this does not promise identical
font metrics, baseline placement or pixels to Matplotlib. Annotations currently
belong to the parent panel; subplot annotations are rejected.

## Supported subset and extensions

- Tuple, partial and descending Cartesian limits are accepted. Bounded charts
  accept an explicit increasing value range. Their automatic ranges are not
  exposed by the current renderer, so getters do not invent limits.
- `tick_params` supports direction, lengths, label sizes/colors/font family,
  boundary visibility and grid styling. Regular, zero-aligned ticks are
  supported. Arbitrary positions/labels, tick padding and custom callable
  formatters require renderer capabilities that are not available yet.
- `MultipleLocator` accepts a regular locator's public `tick_values` protocol,
  including Matplotlib's locator. Figgy supplies `AutoLocator`, `AutoMinorLocator`,
  `LogLocator` and `SignificantFormatter` for renderer-supported rules. Explicit
  secondary-boundary locators affect only that boundary. Colorbar locators
  affect the colorbar without changing the main axes or data normalization.
- The renderer shares tick and spine color, width and line style. Spine edits
  therefore affect that boundary's ticks too. `tick_params` rejects a requested
  independent color/width change that would alter a visible spine implicitly.
- Existing lines accept `line.set(marker="s", ms=7)` without recreating or
  reuploading their data. Marker style is stored once a marker exists; latent
  marker sizes before that, and removing markers while retaining their hidden
  style, are outside the supported subset.
- Legends support corner locations, font sizes, family/size in `prop`, frame
  colors/alpha and border padding. Bounded legends support visibility only.
- `secondary_xaxis` / `secondary_yaxis` expose an existing boundary. Arbitrary
  transformed secondary axes are rejected; use `twinx()` for a separate Y scale.
- `get_position` / `set_position` use normalized **data-area** bounds.
  `get_panel_position` / `set_panel_position` are Figgy extensions for the outer
  panel, including labels and title. Bounded automatic geometry is guarded.
- Title `set_offset`, `set_layout_height`, axis `set_layout_margin`,
  `set_ticklabel_offset`, and legend `set_offset` are named Figgy extensions;
  their lengths use points. `arrow()`'s legacy sizes also use points.

Unsupported arguments fail explicitly. Renderer materials, bounded-chart
containers and arbitrary decoration APIs are **not** full Matplotlib equivalents. Bounded charts expose named Figgy controls:

```python
ax.chart.set_label_style(fontsize=12)
ax.chart.set_series("series_0", color="C2", label="Observed")
ax.chart.set_category_label("category_0", "Baseline")
ax.chart.set_material("paper")
```

These setters keep existing values and IDs. Shared bounded labels have a renderer
limit of 8–32 logical pixels (8–64 for pies), converted from points at the Figure
DPI; an out-of-range request raises without changing the document. The chart
title has independent typography. `set_orientation`, `set_group_width` and
`set_gap` control categorical bars/boxes; `set_slice`, `set_startangle` and
`set_inner_radius` control pies/donuts.

The advanced SSOT methods remain available; they are not required by the common
plotting example above.

## Editing and Python export

`fig.batch_update()` commits existing style/layout edits as one revision and
rolls back on an error. Nested blocks provide savepoints. Create/upload data
outside this block. Concurrent accepted native edits are detected at commit.

`fig.to_code()` and Copy Python prefer public object calls for Cartesian and
bounded appearance. Replay targets an existing Figure with matching panel
ownership, stable artist IDs, source bindings and DPI; the destination Figure
identity is retained. Named Figgy objects cover materials, decorations, palettes, sparse overrides,
fields, vectors, contours, polar projections, annotations and colorbar axes.
The library does not claim full Matplotlib API coverage; exact internal state
that lacks a visual authoring API retains a clearly marked recovery block. Style constants are shortened only
when they round-trip to the same renderer f32 value. Scientific values and arrays
are never rounded by export.

`fig.to_code(mode="exact")` is the full recovery form: it restores the complete
accepted SSOT, including identities, editor metadata and advanced chart state.
`compact=False` expands that form for diagnostics. Exact recovery tests continue
to compare complete SSOT and arrays; public-API tests separately compare actual
Matplotlib properties and source/destination native pixels.

Editor startup is independent of public-code export: an export failure keeps the
chart available and provides a complete exact recovery recipe with its diagnostic.
The PNG editor waits for pending edits to be accepted before copying code.
Independent opposite-axis scales and angle/time tick formats use scoped Axis
setters and SignificantFormatter/TimestampFormatter.

## Complete appearance controls

Features outside Matplotlib's plotting subset have named Figgy objects. They
accept ordinary colors, marker symbols, point sizes and stable IDs. Passing a
renderer `render_type`, `matrix`, `color_map` or style-enum tree is not necessary.
These APIs use the same accepted document edits as the native and notebook UI.

| Object | Controls |
| --- | --- |
| `artist.markers` | Shared marker style, color/size mappings, palettes, individual overrides |
| `artist.errors` | Error strokes/caps, palettes and individual overrides |
| `artist.bins` | Bin fills/outlines, width, gap and individual overrides |
| `artist.vectors` | Stroke, arrowhead, pivot, data/pixel scaling and scalar coloring |
| `artist.contours` | Levels, strokes, per-level colors and inline labels |
| `artist.set_field_fill(...)` | Continuous/banded fields, flat/interpolated shading, opacity |
| `artist.set_grid(...)` | Registered scalar matrix, orientation and center/edge coordinates |
| `artist.legend_label` | One series' legend typography |
| `ax.legend_handle.content` | Custom rich legend keys, including hidden legends |
| `ax.get_overlay(id)` | Existing secondary Y axis and its independent legend |
| `ax.get_colorbar()` | Shared color scale, placement, outline, NaN color and independent axis |
| `ax.chart` | Materials, camera, labels, series/cell/slice styles and decoration placement |
| `fig.annotation(id)` | Existing text, line, span or arrow, retaining its ID |

```python
from figgyplot import MarkerStyle, ErrorBarStyle, TextRun, ContourLabel
from figgyplot.ticker import SignificantFormatter, TimestampFormatter

points.markers[2].set(color="red", marker="s", markersize=8)
points.markers.set_palette([
    MarkerStyle(color="C0", marker="o"),
    MarkerStyle(color="C1", marker="s", fillstyle="none"),
], source=fig.data.column("class_index"))
points.markers.map_color(fig.data.column("temperature"), clim=(250, 400), cmap="magma")
points.markers.map_size(fig.data.column("population"), domain=(0, 1e6),
                        markersizes=(4, 16), scale="area")
points.set_fillstyle("none")
```

`fig.data.add(name, values)` explicitly registers a new column outside a batch;
`fig.data.column(name)` references an existing column without copying data.
Constructors register their own columns. `artist.data.x`, `.y`, `.values`, `.u`,
`.v`, `.color`, `.size` and the applicable palette-index roles return resident
references. Rebinding a map does not replace scientific coordinates or values.
`fig.data.grid(columns, axis="y", coordinates="centers")` describes matrix
storage; it does not transpose, interpolate or resample the arrays.

Palette slots inherit missing properties. `markers.palette[i].set(...)` edits a
slot; `markers[i].set(...)` edits one point. Error bars have the same interfaces.
`set_overrides([(index, MarkerStyle(...)), ...])` preserves declaration order,
including repeated partial records. `set_palette(None)`, `set_overrides(None)`,
`map_color(None)` and `map_size(None)` explicitly clear those optional policies.
Native precedence remains shared style → palette → scalar mapping → point
override. An explicit point color therefore remains fixed when its colormap
changes. Filled/hollow markers use normal symbols and `fillstyle="full"/"none"`.
Bin overrides use `BinStyle`, with no palette because the renderer has none.

```python
field.contours.set_levels([1, 2, 5])
field.contours.set_style(linewidth=1, linestyle="--", colors=["C0", "C1", "C2"])
field.contours.set_labels(fontsize=9, formatter=SignificantFormatter(3),
    positions=[ContourLabel(1, x=2, y=3, tangent=(1, 0))],
    spacing=80, background="white", padding=2)
field.set_field_fill(mode="bands", shading="interpolated", alpha=0.7)
```

Contour labels use explicit data positions/tangents; an empty positions list
restores automatic placement. `set_labels(None)` removes the optional label
configuration. Vector scaling has Figgy semantics: `units="data"` multiplies
components in data units, while `units="pixels"` specifies logical pixels per
component unit. It is not Matplotlib's reciprocal `quiver(scale=...)` convention.
Polar projection uses `ax.set_polar_options(unit="radians", zero=90,
clockwise=True, interpolation="arc", pieces=8)`; zero/label angles are degrees,
sector endpoints use the selected unit. Unsupported polar plot combinations
remain rejected.

```python
bar = ax.get_colorbar()
bar.set_layout(side="bottom", align="center", fraction=0.8,
               thickness=12, gap=8, offset=(0, 4))
bar.set_nan_color("gray")
bar.set_outline(color="black", linewidth=0.5)
bar.ax.yaxis.set_major_formatter(SignificantFormatter(4, style="scientific"))
bar.set_cmap("magma")
bar.set_clim(250, 400)
```

Both orientations use the same colorbar axis object (`bar.ax.xaxis` aliases
`bar.ax.yaxis`). `ax.add_colorbar(...)` can explicitly create a standalone scale;
it does not turn arbitrary per-point colors into a scalar mapping. Colors and
limits edited through an artist or colorbar share one update path.
`TimestampFormatter(unit="ms", timezone=540, pattern="%Y-%m-%d")` formats numeric
Unix timestamps, without converting their data. Degrees/radians are additional
`SignificantFormatter` styles. `Axis.set_scale` and `.line` edit just that
boundary, including independent secondary/colorbar axes.

```python
note = ax.text(.1, .2, [TextRun("Temperature ", bold=True),
                      TextRun("T", italic=True), TextRun("max", script="sub")],
               coords="ratio", id="peak-note")
note.set_bbox(facecolor="#ffffffe6", edgecolor="gray", linewidth=0.5, pad=4)
arrow = ax.arrow(0, 0, 1, 1, id="peak-arrow")
arrow.set_endpoints((.2, .2), (3, 10), coords="ratio", endcoords="data")
arrow.set_style(linestyle="--", head_length=8, head_width=6)
arrow.set_label("Maximum", fontsize=10)
```

`TextRun` works in titles, axis labels, legend entries and annotations. It also
supports per-span color/size, underline, superscript/subscript and rule marks.
`note.set_multialignment(...)` aligns multiline content. Reference lines expose
`set_value`, `set_style` and `set_label`; spans expose `set_bounds` and fill
`set_style`. Annotation frame padding uses points. Subplot-local annotation
spaces, curved arrows and unsupported transforms remain guarded.

For bounded charts, `ax.chart.get_style()` returns supported reusable keywords.
`set_style` covers every chart-global material/style leaf, including box
statistics/outliers, radial camera/light/corners/outlines and radar grid/fill.
Returned bounded/radial artists use the same named `get_style`/`set_style` API.
`chart.get_series()` and `get_categories()` expose IDs with display labels;
`get_slice_count(detail=True)` inspects detail slices without reading raw SSOT.
`chart.series(id)`, `chart.cell(category_id, series_id)` and
`chart.slice(index, detail=False)` expose scoped styles. `reset_style()` on an
element restores inheritance. Full per-element bar/box/pie styles snapshot the
chart defaults; the renderer's partial radar styles continue to inherit unset
fields. Value-label choices depend on the chart family: bars use
none/inside/outside/auto, boxes none/median/median_and_count, pies
none/inside/outside, and radar none/values/emphasized.

`chart.set_split(index, values, labels=..., colors=..., inner_radius=...)` creates
a pie detail chart whose child values must sum to the parent. Existing detail
slices are edited with `slice(i, detail=True)`. Appearance export retains those
resident child values. `chart.decoration("title").set_offset((x, y))`, named
axis/value/spoke/slice labels and `chart.set_plot_bounds((left, top, width,
height))` use points; `set_plot_bounds(None)` restores automatic layout.

Exact checkpoint/recovery APIs remain available for identities, interaction
records, diagnostic snapshots and renderer fields outside these visual
controls. They are separate from ordinary chart authoring.
