# Direct selection and overlapping objects

The host knows panel rectangles, stable panel/series identities and axis ownership.
Users should click the chart they want to work on, then click the object they want
to edit. The Objects tree provides a searchable overview and an alternative route;
choosing a layer in a dropdown is not a prerequisite for canvas editing. Input
searches all visible coordinate layers within the selected panel. An inactive
secondary axis or its title can therefore be clicked, edited and dragged directly;
clicking a shared primary decoration routes input back to its panel owner.
Secondary Y axes stay independent even when their numeric domains happen to match
the primary axes; primary opposite-axis editing conveniences must not propagate
an overlay edit into the primary layer.

## Reference applications

These references describe patterns in the source applications. Figgy's near-click
chooser adapts those ideas to ambiguous renderer hits:

- [Origin Object Manager](https://docs.originlab.com/origin-help/object-manager/)
  connects graph selection with a hierarchy of layers, groups and plots. Plot rows
  include visual identifiers. Its selected-plot emphasis also helps distinguish
  overlapping plots.
- [Origin Mini Toolbar](https://docs.originlab.com/origin-help/mini-toolbar/)
  places relevant controls near the selected object. The controls depend on the
  selected object rather than exposing every possible property at once.
- [Prism Format Graph](https://www.graphpad.com/guides/prism/latest/user-guide/using_format_graph_two_way.htm)
  opens the relevant formatting dialog when a user double-clicks a plotted symbol
  or bar. Dataset-specific formatting is a direct consequence of that selection.
- [Prism front-to-back ordering](https://www.graphpad.com/guides/prism/latest/user-guide/using_changing_front_to_back_order_o.htm)
  treats plot stacking separately from legend order. Selection should not require
  changing either order or moving the data.

Figgy adopts direct manipulation, synchronized tree/context and object-specific
properties. Its near-click chooser is a host design for ambiguous hits. The
resulting interface follows Figgy's panel and axis ownership model.

## Host interaction contract

1. A grid chart's first click focuses that chart without editing an object.
   Subsequent clicks select visible data or decorations within the focused chart.
2. One nearby series selects directly. Multiple nearby series open **Choose what
   to edit** next to the click, including coincident series on the same axes.
   Each row identifies the label, color, stable ID and owning chart/axis.
3. Hover or Up/Down previews a candidate. Data preview uses the renderer's picked
   data marker; decorations and chart candidates have an outline. This
   is selection feedback, not a full-series fading effect.
4. Click or Enter chooses the target and opens its properties. Escape or an
   outside canvas click cancels the chooser without applying the preview.
   Larger candidate lists can be searched.
5. A click covered by several chart rectangles offers chart candidates first.
   The chosen chart retains ownership for subsequent input, including a chart
   behind another chart. **Switch chart (N)** exposes the other intersecting
   charts without requiring a modifier or changing draw order. The tree can
   select a rear chart too.
6. A drag in the plot area continues to pan. An ambiguous data click opens the
   chooser only on release when the pointer did not become a drag.
7. External document replacement cancels stale choices. Previews must not change
   the authoritative document/revision, source arrays, legend or draw order, and
   must not appear in exports or feedback to Python.

## Renderer boundary

The upstream picker returns one nearest primitive per coordinate layer. The host
collects all nearby series by querying the GPU and temporarily excluding each
already-found series from the renderer metadata registry. It does not keep CPU
copies of source arrays or upload those arrays again. Cross-series fills are
removed only from the temporary pick registry because fills are not pick
primitives; the original registry and configuration are restored on success and
failure. This can require one GPU query per overlapping series, plus a terminating
miss. There is no silent fixed candidate limit.

A renderer API that returns all nearby series in one GPU query would reduce that
latency and remove temporary metadata changes. Full-series dimming would also
belong in a transient renderer presentation API; it must not be implemented by
rewriting the Figure's styles.
