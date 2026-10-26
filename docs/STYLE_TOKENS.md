# Style tokens

`StyleToken` packages reusable appearance separately from optional coordinate
scales and text. Data arrays, column references, Figure/panel/series IDs, category
names, annotation geometry, and chart types stay owned by the destination.
Applying a token resolves and validates one candidate document, then commits it
through `Figure.apply_settings` once. Existing native windows and notebook
widgets receive that same accepted state; one Undo restores the previous state.

## Presets and common controls

The six legacy presets are generic appearance starting points. `paper` is not
a verified journal profile; `colorblind` is not whole-chart accessibility
certification, and `dark` does not define a dashboard task. See the
[preset research and measured gaps](STYLE_PRESET_RESEARCH.md) before treating
these names as suitability claims. Fourteen additional task profiles cover
publication, printing, scientific measurement, presentations, dashboards and
teaching. See the [profile catalog and rendered examples](STYLE_PROFILES.md).

```python
import figgyplot as fg

fig, ax = fg.subplots()
ax.plot([1, 2, 3], [2, 4, 3], label="Measured")
ax.set_title("My result")
ax.set_xlabel("Time (s)")
ax.legend()

fig.apply_style("paper")
# paper, report, presentation, dark, monochrome, colorblind
print(fg.styles.available())

style = fg.styles.preset("report")  # a fresh independent token
style.appearance["typography"]["font_size"] = 12
style.appearance["typography"]["font"] = "Noto Sans CJK KR"
style.appearance["palette"] = ["#0072b2", "#d55e00", "#009e73"]
style.appearance["background"] = "#ffffff00"
report = fig.apply_style(style)
```

Use a font available on the destination host. Explicit common typography wins
over captured object fonts and covers chart/axis titles, ticks, legends,
colorbar axes, secondary axes, and existing annotation text. Role-specific sizes
are `title_size`, `label_size`, and `legend_size`. Presets instead use relative
`title_scale`, `label_scale`, and `legend_scale`, so changing the common
`font_size` adjusts all roles together while preserving their hierarchy.
An explicit role size overrides its relative factor.
Extracted tokens preserve individual object fonts until a common override is
explicitly added. Colors accept the same named/hex/RGB(A) values as plotting,
and serialize as RGBA mappings.

The official presets contain appearance only: no text payload or coordinate
scale payload. Palette cycles style solid colors. Value-mapped points/vectors
retain their mappings and use the chart's colormap rather than the solid palette.

## Declare defaults within a codebase

```python
fg.use_style("dashboard.operations")
first, ax = fg.subplots()
ax.plot(time, latency, style_key="api-service", label="API")

second, ax2 = fg.subplots()
ax2.plot(time, throughput, style_key="api-service", label="API")
# Same category key, same appearance in both Figures.

with fg.style_context("publication.nature"):
    paper, paper_ax = fg.subplots(figsize=(89 / 25.4, 62 / 25.4), dpi=300)
paper_ax.errorbar(x, y, yerr=error)  # inherits even outside the context

fg.use_style(None)  # subsequent Figures return to ordinary defaults
```

Declarations live in the current Python execution context. They write no
configuration files and have no effect on another process. Async tasks inherit
their context and can override it independently; a new thread starts without a
declaration. Nested `style_context` blocks replace defaults temporarily and
restore them on normal exit or exceptions. `style_context(None)` temporarily
disables defaults.

Each Figure captures a deep copy at creation. Later series, annotations,
subplots and secondary axes inherit that copy. Changing the execution defaults
does not restyle existing Figures. Adding an object styles only that new object;
accepted edits to existing objects remain in place. Style resolution joins the
original constructor commit, without reuploading earlier data.

```python
standalone = fg.Figure(style="print.monochrome")
unstyled = fg.Figure(style=None)  # explicitly opt out of execution defaults

custom = fg.StyleToken({"typography": {"font_size": 12}})
local = fg.Figure(style=custom)  # override these fields over execution defaults

first.apply_style("dashboard.analysis")  # one existing-document edit
first.set_style("dashboard.analysis")    # restyle and retain defaults for additions
first.set_style(None)                    # disable future inheritance
snapshot = first.style_defaults          # independent copy, or None
```

Precedence is: explicit constructor arguments, then the Figure's captured
style, then original constructor defaults. Explicit arguments win even when
they equal the original default, such as `linewidth=1.5`, `color="black"` or
`markersize=4`. A format string such as `"r--o"` also counts as explicit.
Styles never introduce markers into a line-only series or convert chart kinds.
Scale and text payloads in a default declaration are intentionally ignored;
use `apply_scales` or explicit text opt-in for those operations.

`style_key` identifies a category across Figures created under one declaration.
Use keys consistently for categorical series; anonymous series use each
Figure's local cycle. User-specified colors/shapes may intentionally reuse an
encoding. A named semantic role (`focus`, `context`, `reference`, `warning`,
`critical`, `positive`) applies its declared role instead. These are labels
supplied by the caller, never inferred from numeric values:

```python
ax.plot(time, latency, style_key="api-service")
ax.plot([0, 10], [150, 150], style_key="warning", label="Supplied limit")
ax.scatter(events, values, style_key="critical", label="Flagged events")
# Explicit marker='o' would take precedence over the role's diamond marker.
first.apply_style("dashboard.operations", role_map={"limit-series-id": "warning"})
```

Keys address Cartesian series or a single-series bounded chart. A bounded
chart with multiple series/slices requires explicit `colors`; one key cannot
identify several independent series. Built-in task profiles repeat categorical
colors with additional dash/marker encodings, warning after the declared common
capacity for Cartesian categories (24, or 12 for monochrome). Bounded bars,
boxes and slices do not gain these line/marker combinations and warn once their
palette runs out (six, or three for monochrome). Use grouping or explicit
encodings beyond those sizes. Color-mapped values keep their column/grid references and domain;
their colormap remains a separate explicit choice.

## Extract, save, and reuse

```python
style = fig.extract_style()
style.save("my-style.json")
style = fg.StyleToken.load("my-style.json")
other.apply_style(style)

# String/dict transports for applications and agents:
encoded = style.to_json()
style = fg.StyleToken.from_json(encoded)
style = fg.StyleToken.from_dict(style.to_dict())
```

The token has `version=1`, `appearance`, `scales`, and `text` fields. The optional
payloads are `None` unless captured explicitly. Unknown appearance/schema fields
and unsupported token versions are rejected. Numeric values must be finite.

For pending edits made in a notebook browser, synchronize before extraction:

```python
style = await fig.extract_style_async()
# Equivalent: await fig.sync(); style = fig.extract_style()
```

## Optional scales and wording

```python
template = fig.extract_style(scales=True, text=True)
other.apply_style(template)  # appearance only, even though payloads are present
other.apply_style(template, scales=True)
other.apply_style(template, text={"axis_titles"})
other.apply_style(template, scales=True, text=True)
other.apply_scales(template.scales, limits=False)
```

Scale payloads include linear/log, inversion, bounds, major tick spacing and its
Auto/Fixed mode for all four axes and secondary axes; colorbar normalization;
and available box/radar value ranges. They do not carry shared-axis group IDs.
`limits=False` copies only linear/log and inversion on coordinate/color axes;
it preserves target bounds and ticks, and leaves bounded value ranges alone.
Nonpositive log domains and conflicts with destination shared-axis groups fail
atomically. The API never silently fits or clips destination data to accept a
scale. Polar angle units/orientation and per-point size-map domains are not
copied; these remain destination chart semantics.

Text selection is `True` for all captured groups, or a set containing:

- `titles`: chart titles.
- `axis_titles`: all four axis titles, secondary Y titles, and colorbar titles;
  category/value axis titles for applicable bounded charts.
- `legend_labels`: existing series/slice legend wording.

Category names, annotation wording, and values are not copied. Without text
opt-in, even rich-text characters and their superscripts/subscripts remain
unchanged. Text copying requires corresponding objects/counts or an explicit
series map; it cannot create a missing axis or colorbar.

## Physical sizes and layout

```python
other.apply_style(style, size_scale=1.25)
```

Visual lengths in tokens use points and convert using the destination DPI.
`size_scale` multiplies the lengths supplied by the token, such as font sizes,
line widths, markers, padding, axis margins and grid gaps. It does not multiply
data, axis bounds or fixed tick intervals. Reapplying the same token is absolute,
not a cumulative multiplication of the previous appearance.

Grid styles preserve current topology by default, while reusing applicable gap
and row/column weights. Axis/title margins reuse the renderer's existing layout
fields; automatic plot rectangles remain derived from those fields. To copy the
captured grid topology explicitly, use matching panel counts:

```python
other.apply_style(style, layout=True)
other.apply_style(style, layout=True, panel_map={0: "right", 1: "left"})
```

The token stores numeric panel slots, not source IDs. Figure size, DPI, source
membership and existing shared-axis groups are retained.

## Correspondence and incompatible charts

A single captured panel style broadcasts to destination panels. Multiple panels
match by order, or use `panel_map={source_index: destination_panel_id}`.
Series styles match the existing render kind (line, scatter, histogram, etc.)
and cycle within that kind in source order. No chart kind is converted. For
explicit correspondence use `series_map={source_index: destination_series_id}`;
this also addresses opt-in legend text. Only mapped series receive captured
series overrides; common typography/background still apply to the Figure.
Bounded series/slice styles cycle within the same chart family. Annotation
appearance cycles by kind/order and keeps destination IDs, anchors and text.

Unmatched style components produce `StyleWarning` and appear in
`StyleReport.skipped`. `strict=True` rejects such a partial application before
committing anything. Renderer validation failures always abort the entire edit.
No extra GPU data upload is needed for a style edit.

The renderer's existing restrictions still apply. For example, Milkyway requires
line-only series and Constellation requires marker lines. Categorical, box and
radar base fonts must be 8–32 logical pixels, and radial base fonts 8–64; an
out-of-range DPI/size combination raises an explicit error instead of clamping.

Per-datum overrides, binning, contour levels, fill-to-series/baseline references,
vector magnitude scales, polar coordinate conventions, category order and
annotation positions are intentionally not portable appearance. Destination
values for those fields are preserved. The token is a reusable style, not a
replacement for a complete chart checkpoint.
