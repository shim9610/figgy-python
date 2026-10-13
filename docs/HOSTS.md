# Native surface / notebook WebGPU hosts

The Python distribution uses `figgy-renderer 0.16.1`. Chart layout, styles, data
rendering, hit maps and drag policies remain renderer APIs. No renderer source is
vendored. `benchmarks/plot_results.py` continues to render reports with Figgy.

## Desktop

`Figure(backend="native")` uploads NumPy columns through the original borrowed
f32/f64 → hi/lo staging path. `NativeFigure` and the desktop host share one
`Arc<Mutex<FigureCore>>`; window views are weak references to that core. The
figure retains its resident column pool, registered chart, device, queue and GPU
picking resources across close/reopen. The native host retains no CPU array copy.

The host uses winit 0.30.13, egui 0.36.2 and wgpu 30. The upstream
[`WindowedRenderer` and winit example](https://github.com/shim9610/figgy/blob/84aa2783caa97d679c72b5c079fb4aea8bf1040e/crates/renderer/examples/winit_simple.rs)
were inspected first. That convenience owner creates a new device and exposes no
constructor for attaching an existing `Renderer`. To preserve resident uploads,
this host creates a surface on the figure's existing instance/adapter and uses
public `ensure_target_format`, `display_config_for_surface`, `prepare` and
`paint_prepared`. Target-format changes rebuild final composition pipelines,
not columns. Each window owns its surface, egui state, views and display-scaled
styles. The chart document/export size stays unchanged by window resize/DPI.

A normal frame prepares and paints the chart plus egui into the swapchain,
submits and presents. It performs no RGBA mapping, PNG encoding, QWebChannel,
JavaScript or image transfer. GPU picking reads a small result on explicit picks;
it does not read the whole frame. PNG export alone uses renderer readback.

The panel edits title/axis/legend text and font/color, axes and series styles.
Chrome/series selection, renderer drag/resize policies, wheel zoom, Copy Python
and Save PNG are available; full SSOT JSON covers additional renderer fields.
Copy Python is a self-contained `json.loads` + `fig.apply_settings` snapshot.
Save PNG writes the path shown beside the button.

```python
from figgy.desktop import poll_events, run_events
window = fig.show(block=False)
# Integrate into a main-thread application loop:
while not window.closed:
    poll_events()
# Or use run_events() to run all current windows until they close.
```

All window creation/event pumping must run on Python's main thread, including
macOS. `show()` runs until **all currently open Figgy windows** close, and returns
a closed handle. `show(block=False)` creates/pumps the initial window and returns;
call `poll_events()` frequently or use `run_events()`. A worker thread cannot own
the winit event loop. Python mutations and Rust frames lock the same core. The GIL
is released during each event-loop pump and native rendering. PyO3 mutex waits
use `MutexExt::lock_py_attached` so concurrent callers cannot deadlock the GIL. The blocking loop
checks Python signals between pumps. Each window can close independently.
`fig.close()` requests window closure, pumps on the main thread, and drops the
figure core. `WindowHandle.close()` requests closure; event pumping completes it.
The process keeps one reusable main-thread winit loop for close/reopen. These
APIs do not integrate automatically with a foreign Qt/Tk event loop or `%gui qt`.

Native `fig.info` counts `column_uploads`, `rgba_readbacks`, `png_encodes`.
`window.info_json()` additionally counts surface frames and reports the last
input-to-submission time. That time ends at CPU queue submission, not monitor
presentation or completed GPU execution. `benchmarks/ui_surface.py` measures
surface submission rate; the existing `compare.py` measures completed RGBA
readback. Do not compare the two as the same FPS metric.

## Jupyter

`backend="auto"` selects `webgpu` inside an IPython kernel and `native` elsewhere.
Use `Figure(backend="webgpu")` explicitly in shared scripts. Its PyO3
`NotebookFigure` constructs only the common renderer's `Chart`/settings model;
it creates no adapter, device or native GPU pool. Initial min/max metadata is
computed while scanning inputs; renderer `Chart.auto_fit_*_extent` owns range
fitting. The browser Fit action uses upstream GPU fit. This initial metadata path
covers the exposed plot/scatter/heatmap APIs; it is not a general errorbar fit
engine.

The browser creates upstream `FiggyChart` on a real WebGPU canvas. Float32 and
float64 NumPy snapshots cross anywidget as binary buffers, then typed arrays
enter wasm-bindgen and upload into a separate browser GPU pool. They are not JSON
number arrays or base64. f64 uses upstream hi/lo registration. Upstream's initial
browser pool is 16 MiB and grows on allocation failure; `pool_bytes` currently
controls only the native initial pool. No automatic stream/downsample/chunk
transition is called by either host.

The kernel, browser JS, WASM linear memory and GPU are different memory domains.
Initial NumPy snapshot, Jupyter comm transfer, WASM input and GPU staging involve
copies. This is **not zero-copy**. The caller still owns its NumPy arrays. The
wrapper's temporary binary snapshots are independent, so later NumPy mutations
do not change the chart. After successful browser upload, default snapshots and
widget buffer traits are cleared. JS input buffers become collectible; freed WASM
input allocations do not shrink the WASM linear memory's reserved capacity.
Browser GPU resources remain until the widget view is disposed.

Data topology is sealed once a widget is displayed. Create a new Figure for new
source data. A released model cannot supply columns to a new view after reload.
Use `retain_notebook_data=True` to retain transfer buffers/assets for repeated
views/reload, or recreate and execute the cell. This option applies only to the
notebook backend; native does not retain original arrays. Initialization failure
retains snapshots for retry and reports a visible WebGPU error. Device loss
requires recreating the view/figure, with retained snapshots if desired.

Zoom, GPU picking, drag and style changes use resident browser resources. Pointer
moves update the canvas locally; a settings edit is sent on pointer release,
not each movement. Settings changes send a CAS base revision and sequence, with
one in-flight edit and a latest-edit queue. The kernel validates and acknowledges
the canonical document. Stale browser edits are rejected and the current kernel
state is restored visibly. Python edits push new revisioned settings, with no
column retransmission. Browser validation failures roll settings back through a
revision-checked rejection message. Browser display can be optimistic until ack;
`get_settings()` / `to_code()` read the kernel's last accepted revision.

```python
fig, ax = figgy.subplots(backend="webgpu")
ax.plot(x, y, id="signal")
display(fig)
# In another cell after interactive edits:
await fig.sync()               # wait for pending browser edits/ack
print(fig.to_code())
await fig.savefig_async("edited.png")
```

Synchronous `savefig`/`render_rgba` are native operations. WebGPU PNG requests are
asynchronous because the kernel cannot block its comm dispatcher. Use
`await fig.to_png_async()` or `savefig_async()`; browser Save PNG also downloads
from renderer export. Both export after pending settings edits are acknowledged.
They return/transfer PNG only on explicit export requests. A visible widget view
must be mounted for browser requests; they time out if no frontend is connected.

WebGPU needs a supported browser and secure origin (HTTPS or localhost), with a
usable GPU driver. No native GPU is required in the remote kernel. Unsupported
WebGPU/initialization failures appear in the output and widget status; they do
not silently switch backend. Explicit `Figure(backend="native").widget(backend="png")`
retains the older kernel PNG editor and is labeled **Kernel PNG fallback**. It
requires a usable kernel GPU and performs image transfers.

## Assets and builds

`python/figgy/assets/figgy.js` and `figgy_bg.wasm` are generated from upstream
`crates/web` at commit `84aa2783caa97d679c72b5c079fb4aea8bf1040e` (renderer 0.16.1,
web example 0.13.1). `scripts/build-wasm.sh` rebuilds with its Cargo.lock and
wasm-bindgen 0.2.129. `assets/provenance.json` records the versions and SHA-256.
The script uses an external checkout; it does not copy Rust sources into this
repository. It is a maintainer step; pip installation uses packaged artifacts.

The wheel/sdist include native bindings, local JS/WASM, CSS and font notices.
Anywidget sends the packaged JS text and WASM binary to its frontend; a local blob
module initializes from those bytes. No developer server or external asset CDN
is required. In remote-kernel setups, install Jupyter's widget/anywidget frontend
extension in the server environment too.

Linux software Vulkan + Xvfb/Chromium verification is recorded separately in
`HOST_VALIDATION.md`. Windows RTX 4070 Ti results already in the repository are
**the previous completed RGBA readback measurements**, not validation of these
new hosts. Windows hardware, macOS Metal, physical monitor DPI changes and actual
hardware display/input latency must still be verified there.
