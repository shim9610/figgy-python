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
identity is retained. Renderer-only
materials, decorations and per-element overrides that lack public setters are
kept in a clearly marked advanced block. This boundary is explicit; the library
does not claim full Matplotlib API coverage. Style constants are shortened only
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
Independent opposite-axis scales and angle/time tick formats remain explicit
advanced settings when they cannot be expressed by the public subset.
