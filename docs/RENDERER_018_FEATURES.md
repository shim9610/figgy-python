# Renderer 0.18 Python features

These APIs extend ordinary plotting. They do not start an LLM review session,
write review caches or change the meaning of window close. Review approval,
temporary binary checkpoints and automatic revision cleanup belong to #18.

## Document ownership and identity

Figure owns the document, layout, data resources and shared-axis groups.
`fig.subplots[panel_id]` addresses a Subplot, which owns its local Axes and
secondary Y axes. `subplot.axes` returns its primary Axes; plotting methods are
also forwarded by the Subplot. `ax.subplot`, `ax.subplot_id`, `ax.id` and
`ax.figure` expose ownership. `fig.axes` is a flat convenience sequence.

Series IDs are unique within the Figure. Panel and overlay handles resolve
stable IDs each time; moving a panel does not redirect a previously saved Axes
handle. GPU allocation IDs are private and independent of persistent IDs.

```python
import figgyplot as figgy

fig = figgy.Figure(grid=[['large', 'top'], ['large', 'bottom']])
fig.subplots['large'].plot([0, 1, 2], [1, 3, 2], id='temperature')
fig.subplots['top'].step([0, 1, 2], [2, 1, 3], where='post', id='steps')
fig.subplots['bottom'].scatter([0, 1], [2, 3], id='samples')
fig.place('top', slot='bottom')  # Swap occupants, preserving panel identities.
```

Grid slot IDs and subplot IDs are separate. Supply `placement={'slot': 'panel'}`
to `set_layout`, along with `row_weights`, `column_weights` and a logical-pixel
`gap`. Repeated slot names must form rectangles. Interior empty cells use `None`;
entirely empty outer rows/columns are rejected because upstream document bounds
are the union of panel rectangles. Invalid layouts never partially replace the
document. `subplot.set_rect(x, y, width, height)` switches to explicit geometry.

`figgy.subplots(rows, columns, sharex=False, sharey=False, squeeze=True)` remains
available. One panel returns one Axes; grids return NumPy object arrays.
`squeeze=False` always returns a 2-D array. Sharing accepts `True`, `all`, `row`
or `col`. `fig.share_axes('x', ['panel_a', 'panel_b'], id='time')` creates an
explicit group. Range/scale/direction/ticks link; titles and styles stay local.
Figure fitting includes every coordinate group; `ax.fit()` fits the selected
coordinate group and its shared domains.

## Construction and capability matrix

All listed constructors support native and notebook WebGPU hosts, settings
round trips and code replay. Image export includes the complete document at the
requested scale, independently of which layer currently receives interaction.

| Capability | Public construction/configuration | Renderer limits |
| --- | --- | --- |
| Polar | `figgy.subplots(subplot_kw={'projection': 'polar'})`; `ax.set_polar(**options)` | Lines, scatter and scatter-lines; fields, histograms, errors, vectors and secondary Y axes rejected |
| Radar | `ax.radar(categories, values, labels=..., colors=..., **properties)` | Separate bounded document; values are series-by-category; upstream bounded limits apply |
| Point vectors | `ax.quiver(x, y, u, v, scale=20, units='pixels', pivot='middle')` | Equal-length vectors; anchor picking reports components |
| Grid vectors | `ax.quiver(x, y, u, v)` with 2-D components | Shape `(len(y), len(x))`; Cartesian; 0.18.1 picks drawn arrows; selection outlines the whole cell |
| Vector colors | `quiver(..., values=..., cmap=..., vmin=..., vmax=...)` | Values match component shape; colorbar owns the scale |
| Point color map | `ax.scatter(x, y, c=values, cmap=..., vmin=..., vmax=...)` | Explicit aligned numeric values; per-point values use the panel colorbar |
| Point size map | `scatter(..., s=values, size_domain=(lo, hi), size_range=(2, 12), size_scale='area')` | Size range is marker diameter in Python points; `radius` also supported |
| Baseline fill | `ax.fill_between(x, y, baseline)`; `plot(..., fill=0, fill_color=...)` | Line geometry; baseline expressed in data units |
| Between-series fill | `ax.fill_between(x, upper, lower)` | Shared resident X column, no resampling; lower/upper lines commit together |
| Steps | `ax.step(x, y, where='pre'/'post'/'mid')`; `plot(..., interpolation=...)` | Upstream line picking follows the stepped geometry |
| Secondary Y | `right = ax.twinx(id='pressure')`; `right.plot(...)`, `right.set_ylim(...)` | Shares the parent X mapping/plot rectangle; Cartesian only |
| Subplots | `Figure(grid=...)`, `set_layout`, `subplots`, `share_axes` | Cartesian/polar panels; one level; bounded families require separate Figures |
| Annotations | `axhline`, `axvline`, `axhspan`, `axvspan`, `text`, `arrow`, `annotate` | One parent-panel annotation layer; subplot-local annotation spaces rejected |
| Independent bounded titles | `ax.set_title(text, fontsize=..., color=..., visible=...)` | Rich title no longer changes category/data-label font sizes |
| Heatmap legend swatches | `ax.imshow(..., cmap=...)`, series label, `ax.legend()` | Uses the current colormap and preserves independently edited legend text |

For mixed documents containing fields, vectors, histograms or errorbars, renderer
0.18 requires the root (first-created) panel to be Cartesian. A Cartesian root
may contain polar subplots. Unsupported polar-root combinations fail before
upload; use a Cartesian root or separate Figures. Moving a panel to another grid
slot preserves its identity and does not change which panel is the root.

`ax.configure(**properties)` patches its local upstream Config. Secondary Axes
accept `y_axis` and optional `legend` patches. `set_polar` options use upstream
spellings such as `angle_unit='Radians'`, `clockwise=True`, `sector=[0, 180]`
and `interpolation={'Arc': {'pieces': 8}}`. `quiver(units='data', scale=factor)`
uses data-space arrow lengths; default pixel lengths remain stable under zoom.

## Annotations and interaction layers

Text and arrows accept `coords='data'` or `coords='ratio'`; ratio `(0, 0)` is the
top-left of the parent plot area. Polar, pie/donut and radar annotation spaces
support ratio anchors only. Reference lines/spans require value axes. Every
constructor returns an Annotation with an ID and `set`, `select` and `remove`
methods. Generic `annotate(kind, **geometry)` uses the upstream model; use
`from_` for the Python spelling of a geometry's `from` field.

`ax.activate()` chooses a panel/secondary-axis pointer route. Both hosts expose
a searchable Objects tree inside Properties, with panels, local axes, secondary
Y axes, series and annotations. Labels and titles identify objects; stable IDs
remain available for search. Canvas selection reveals the selected tree item,
and selecting another panel on the canvas activates its coordinate owner.
The context path identifies which object's form is being edited. Selecting an
annotation routes movement/resizing to upstream annotation handles. **Draw** opens
a tool strip for text, arrows, reference lines and bands, with transient previews,
Esc cancellation, immediate selection and annotation-specific Properties. The
forms expose geometry, rich content, strokes, arrow heads, fills, text boxes and
deletion. **Follow data** chooses data anchors for text/arrows; ratio anchors work
on every family. Value-axis tools are disabled where unsupported, and drawing is
scoped to the root panel. Further editor controls remain #17; complete validated settings are already editable
through Advanced settings and the Python API.

Box plots expose `ax.set_ylim(lo, hi)` for vertical charts and
`ax.set_xlim(lo, hi)` for horizontal charts. Radar exposes `ax.set_ylim(lo, hi)`
for the radial value domain. Both hosts offer manual/automatic range controls
and value-axis wheel zoom; Fit restores automatic bounds. The renderer fixes
categorical-bar domains from the supplied data and does not expose the same
manual-domain option. Pie/donut charts have no numeric value axis to zoom.

Notebook display initially respects the requested Figure size and shrinks to
fit a smaller output cell. **Fit width** explicitly enables enlargement to the
available width; **Actual size** restores the requested size. The docked
inspector sits outside the canvas. These view changes preserve document/export
dimensions, data ranges and DPI.

Mapped-point selection reports `color_value`/`size_value`; point-vector selection
reports `u`/`v` and optional `color_value`. Native readback is limited to selected
samples, with no whole-array or display-image readback.

## Settings and Copy Python

`get_settings` / `apply_settings` now use schema 2, adding `identity` metadata:
Figure ID, panel/overlay IDs, grid placement and shared-axis membership. Visual
values and source references remain in the upstream Config/series/family model.
Supported schema-1 settings migrate on input and are written as schema 2.
Unknown versions, invalid references and stale revisions fail explicitly.

`to_code()` and Copy Python restore complete advanced documents atomically on an
existing Figure with matching source columns/series IDs and DPI. They preserve
every supported panel/layer/reference without reuploading arrays. Bounded-chart
style replay preserves destination values. They do not reconstruct unavailable
source arrays or generate a standalone data-computation script. Ordinary manual
use does not create the future review mode's binary cache.

Run [renderer_018.py](../examples/renderer_018.py) for a multi-panel dashboard,
polar chart and radar chart. `python examples/renderer_018.py --output output/018`
writes native PNGs and settings-replay Python. In Jupyter, call
`make_figures('webgpu')`, display their widgets and use `await fig.savefig_async`
for browser exports.
