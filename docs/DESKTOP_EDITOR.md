# Native desktop editor

The desktop editor uses Rust winit, egui and a wgpu surface. It opens directly
without Qt/PySide6 or a browser. The screenshots below were captured from actual
Linux X11 windows using software Vulkan. Window decorations and fonts vary by
platform; the new host has not yet been verified on Windows/macOS hardware.

winit creates the OS window and handles input. egui draws the toolbar, property
forms and popups inside that window. The upstream renderer draws the chart and
owns its layout, picking and drag policies.

| Component | Role |
| --- | --- |
| winit | OS windows, input events and main-thread event loop |
| wgpu | GPU surface, submission and presentation |
| figgy-renderer | Chart model, rendering, picking and drag policies |
| egui | Toolbar, property forms, text fields, buttons and color picker |

## Launch

From an existing checkout with an active virtual environment:

```bash
python -m pip install .
python examples/desktop_editor.py
```

For a new Windows PowerShell checkout:

```powershell
git clone https://github.com/shim9610/figgy-python.git
cd figgy-python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
python examples/desktop_editor.py
```

Source builds require Rust 1.99 or later and a system C/C++ toolchain: MSVC Build
Tools on Windows, Xcode Command Line Tools on macOS, or a compiler/linker on
Linux. These instructions target the upcoming 0.3.0 release; PyPI currently
provides 0.2.1. Compatible prebuilt wheels
do not require Rust. PR CI checks native/Jupyter interaction parity and packaged assets; see
[validation records](HOST_VALIDATION.md) for tested builds.

A minimal script:

```python
import numpy as np
import figgyplot as figgy

x = np.linspace(0, 20, 100_000, dtype=np.float32)
fig, ax = figgy.subplots(backend="native")
ax.plot(x, np.sin(x), label="Signal", id="signal")
ax.set_title("Interactive chart", fontsize=18)
ax.set_xlabel("Time (s)")
ax.set_ylabel("Amplitude")
ax.legend()
try:
    fig.show()
finally:
    fig.close()
```

Explicit `backend="native"` also selects native rendering in IPython/Jupyter.
The window opens on the desktop of the machine running the kernel. To display
inside a browser with a remote kernel, use `backend="webgpu"` and `display(fig)`.

## Properties and layout

The initial view contains the chart and toolbar, with properties closed. Click a
chart title, axis, legend or series to open that object's form on the right.
**Properties** also opens or closes the panel. Toolbar icons have name tooltips.

Opening properties expands a normal window horizontally while preserving the
chart's displayed size and aspect ratio. Closing it restores the previous width.
Maximized/fullscreen windows, or windows without enough adjacent space, show
properties as an overlay. Manual window resizing preserves the document aspect
ratio with surrounding space. PNG document dimensions stay unchanged.

![Chart and toolbar](images/desktop-editor-overview.png)

| Control or selected object | Action |
| --- | --- |
| Fit view | Fit axis ranges to current data |
| Show / hide | Toggle chart title, legend and axis titles; restore hidden objects |
| Style | Choose Precise, Sketch, Milkyway or Constellation and edit its parameters; incompatible choices are disabled |
| Select | Select data or decorations; default mode |
| Layout | Move and resize the plot area |
| Properties / Close | Open or close properties |
| Object list | Select named objects such as Chart title, X axis or a series |
| Title, axis title, legend | Visibility, text, font family, size and color; individual legend labels |
| Tick labels | Decimal, scientific or power notation; significant digits; font family, size and color |
| Line series | Color and width |
| Scatter series | Color and marker size |
| Matrix series / colorbar | Shared color limits, linear/log scale, palette, number format and significant digits |
| Axis | Limits, scale, tick spacing/direction/visibility, number format, significant digits, line width and color |
| Copy Python | Export common setters and readable `fig.configure(...)` patches |
| Save PNG | Enter a path, then Save image; export the chart at document resolution |
| Advanced settings… | Open full settings JSON in a separate OS window; Apply settings commits it |
| Esc, empty-space click or repeated data click | Clear selection |
| Arrow keys | Step samples or histogram bins, switch compatible series, step matrix cells or nudge decorations |
| Shift + arrow keys | Move samples or decorations by ten steps |
| F11 | Toggle fullscreen |

Enabling an empty chart or axis title creates visible default text and opens its
Properties editor. Empty titles appear unchecked even if their visibility flag
was already true. Existing text and rich formatting survive hide/show. This UI
action fits the title band when needed; direct SSOT edits retain explicit layout.

Number format and significant digits (1–15) are available from an axis, its tick
labels, and a colorbar or matrix series in both desktop and Jupyter. Formatting
changes preserve limits and tick spacing. Decimal labels use uniform precision
with enough places to distinguish adjacent ticks; scientific and power notation
help display wide value ranges. Copy Python retains these settings.

Text, numeric and color changes immediately update the Figure. Numeric controls
support dragging and double-click entry. Invalid advanced JSON preserves the
current chart and reports an error in the settings window. Closing that window
leaves the chart open. Relative PNG paths resolve against the working directory;
existing files are overwritten. Create parent directories first.

Clicking a title shows its text, font, size and color:

![Title properties](images/desktop-editor-title.png)

Clicking a line exposes its series style. Selected data is highlighted without
reuploading source arrays:

![Series properties](images/desktop-editor-series.png)

Histogram selection shows the bin index, start, end and stored value in
**SELECTED DATA** in both hosts. The value can be a count, weighted total, density
or an explicit stairs height. Left/right moves through vertical bins; up/down
moves through horizontal bins. The perpendicular arrows switch compatible
histogram series; Esc clears the selection. Values come from resident GPU data,
so changing the original NumPy array after upload does not change the readout.

## Zoom, pan and selection

The window displays these instructions above the graph:

- **Ctrl + wheel:** zoom X around the pointer.
- **Shift + wheel:** zoom Y around the pointer.
- **Wheel:** zoom X and Y around the pointer.
- **Drag inside the plot:** pan horizontally and vertically.
- **Drag a title, axis title or legend:** move that element.
- **Layout mode:** move or resize the plot area with the renderer's handles.

Wheel zoom only applies while the pointer is inside the data area. Over titles,
axes, colorbars or canvas margins, Jupyter keeps normal notebook scrolling.
Fit uses zero padding when every series is a heatmap, contour or filled contour,
including combinations of these matrix families. A figure containing a line,
scatter or another Cartesian series uses 5% padding. An explicit argument such
as `fig.fit(padding=0.05)` requests 5% for any of these figures; use `padding=0`
to request a tight fit even with mixed series.

Contours and interpolated fills fit the rendered sample extent. Flat fills fit
the cell edges: edge grids use their supplied boundaries, while center grids
extend by half the outer sample spacing. For a fill combined with contours, Fit
covers both. Both Fit buttons and `fig.fit()` use the same policy, including
after the browser releases its transfer buffers.

Zoom supports linear, logarithmic and inverted axes. Movement and resize support
depend on the selected object's renderer policies. Data selection edits series
appearance; dragging samples does not modify their source values.

Properties show the selected index, X/Y coordinates and heatmap value. Only the
selected samples are read from resident GPU storage; original NumPy arrays are
not retained. These reads use `selection_value_readbacks`, independently of
RGBA/PNG counters. Hidden titles and legends remain accessible from **Show /
hide** and the object's Visible toggle.

## Copy settings into Python

Copy Python exports `ax.set_title(...)`, `ax.set_xlabel(...)`,
`ax.set_ylabel(...)`, ranges and other common setters. Advanced positions and
styles use ordinary Python values in `fig.configure(...)`. Font sizes convert
renderer pixels to Python points at the Figure's DPI.

The export contains settings rather than arrays. Recreate the same ordered
series IDs/kinds and data-column connections at the same DPI before replaying
it. Interactive edits are reflected in the Figure. Styling reuses uploaded data.
See [edit and reuse](README_DEMO.md) for the complete workflow.

## Multiple windows and resource lifetime

Pies and donuts use a dedicated native property form for slice values/colors,
materials, textures, camera tilt and extrusion. They support hover, click/toggle selection, arrow-key navigation, title/label
dragging, plot-area resizing, Copy Python and Save PNG. Categorical bars and
boxplots use the same bounded-chart interaction host. These gestures also apply
in the Jupyter WebGPU widget, with properties initially hidden until selection. See [chart and style API](CHART_TYPES.md) and the
[gallery recipes](../examples/README.md) for construction and host coverage.

```python
from figgyplot.desktop import run_events

window = fig.show(block=False)
window2 = fig2.show(block=False)
run_events()  # Process all open Figgy windows on the main thread.
```

Window creation and event processing must run on Python's main thread. Blocking
`show()` returns when all currently open Figgy windows close. Nonblocking
`show(block=False)` requires regular main-thread `poll_events()` calls or
`run_events()`; it does not start a background event loop. Automatic Qt/Tk or
`%gui qt` integration is not provided.

Calling `show()` again creates another view of the same Figure. Independent
Figures can also be displayed together; see
[multiple_windows.py](../examples/multiple_windows.py). Each Figure currently
has one Axes; multi-panel calls such as `subplots(2, 2)` are unsupported.

Native Figures share a GPU device, renderer and column pool. Exceeding the
adapter's storage-buffer limit raises `MemoryError`; there is no automatic
downsampling, streaming transition or eviction. Closing a window retains its
Figure data. `fig.close()` releases that Figure's ownership; after closing all
native Figures, `figgy.release_gpu()` releases the shared context.

## Fonts, preparation and coverage

- Font entries accept installed family names, not file paths. While typing in
  the editor, a missing family falls back to the renderer's bundled font; the
  Python API (`update(..., font=...)`) rejects one with `ValueError` on the
  native backend. Characters the chosen font lacks are drawn per character from
  the bundled font or an installed font that has them; text in other scripts
  still needs such a font, for example `Malgun Gothic` on Windows.
- Property sizes use renderer document units. Python `fontsize`/`linewidth`
  values use points, converted by `dpi / 72`. At 120 DPI, `fontsize=18` appears
  as 30 pixels in properties.
- Heatmap controls edit the document's shared colorbar. Independent per-series
  colorbar controls and a custom colormap UI are not exposed.
- First GPU initialization or new pipelines can take time. Optional
  `fig.prepare()` warms the current process; it does not guarantee persistent
  shader caching or compilation during installation.
- Automated input checks used isolated X11/software Vulkan. Selected GPU value
  reads and native Wayland launch were also checked on Radeon 8060S. Windows,
  macOS and physical monitor DPI transitions need separate host verification.

See [host architecture](HOSTS.md), [native sharing](NATIVE_SHARING.md),
[GPU preparation](PREPARATION.md) and [randomized validation](RANDOMIZED_VALIDATION.md)
for implementation details and test boundaries.

## Axis ticks and character formatting

In an axis property panel, **Axis line**, **Tick marks** and **Tick labels** are
independent controls. Hiding the line keeps ticks if Tick marks is still enabled.
Tick direction supports **Outside**, **Inside**, **Both sides** and **Hidden**.
Tick and label edits also patch the opposite edge when both axes had exactly the
same minimum, maximum, scale and inversion before the edit. Only changed fields
are shared: a font-size change preserves an existing opposite-side color, for
example. Axis-line visibility, titles, margins and offsets remain independent.
Different coordinate systems remain independent; no rounded comparison or
persistent link flag is used. Raw advanced settings preserve exact one-sided edits.
The Jupyter property panel exposes the same fields and directions.

Select characters in a title or axis-title text field, then use **B**, **I**,
**U**, **x²**, **x₂** or **αβ** for bold, italic, underline, superscript,
subscript or the renderer's Latin-to-Greek mapping. With no selected range, the
button applies to the whole text. Superscript and subscript are mutually
exclusive. Existing character formatting survives edits to other characters.
Legend entries also support rich character formatting. Copy Python retains these
rich segments for reuse; it does not flatten them into plain text.

## Axis and color scales

Select an X/Y axis and use **Scale → Linear / Logarithmic (base 10)**.
This edits the selected axis and its opposite when their pre-edit coordinate
settings match, including any fitted positive bounds and derived tick spacing.
Select **Color scale**, its axis, or a heatmap
series to change the color scale independently of X/Y. Color-scale logarithms
change the mapping of data values to colors as well as the colorbar ticks.

Zero or negative samples do not prevent switching to logarithmic display. They
are omitted from the log view; the original data is preserved. If the current
limits cross zero, the scale selector fits the positive data range automatically.
With no positive samples it opens an empty log view from 1 to 10. Existing
positive limits are preserved. The same rule applies to color values and to
Python's `set_xscale("log")` / `set_yscale("log")` helpers. These Python axis
helpers explicitly update both edges of their dimension. For a selected-object
edit with the conditional pairing rule, use `fig.update("axis_bottom",
scale="Logarithmic")`; for exact one-sided settings use `fig.configure(...)`.

Switching scale selects a tick spacing of one decade for logarithmic scales,
or one fifth of the range for linear scales. Direct SSOT range edits still
require positive bounds for a logarithmic axis. Copy Python preserves the
chosen scales. Both desktop and Jupyter expose these controls.
