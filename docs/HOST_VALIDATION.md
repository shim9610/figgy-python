# 0.2 host verification

2026-10-14 (Asia/Seoul), based on main `294b270a2b2e6645056278b3ef035e5199a5f658`.

## Environment

- Linux x86_64, glibc 2.41, CPU quota 4 cores; no physical GPU available.
- Rust 1.99.0, CPython 3.12.14.
- Native: Vulkan **llvmpipe LLVM 19.1.7**, Xvfb X11 display.
- Browser: Chromium 154, software **SwiftShader Vulkan**, a headed browser on Xvfb.
- JupyterLab 4.6.4 + anywidget 0.11.0.

These are software GPU checks, not Windows RTX 4070 Ti or macOS hardware checks.
The earlier Windows results in `benchmarks/WINDOWS_GPU_RESULTS.md` measure the old
completed RGBA path; they do not validate the new hosts or predict their UI FPS.

## Installed package checks

Built `figgy_python-0.2.0-cp312-cp312-manylinux_2_39_x86_64.whl`, installed it with
`[notebook]` into a separate virtual environment, and ran the tests against that
installed package. No PySide6/QtWebEngine was installed in that environment.
The local wheel requires **glibc 2.39+**. Other Python/OS wheel builds are CI
configuration, not successful execution claims in this record.

Native extension import, WebGPU JS, WASM magic, and asset SHA-256 against
`assets/provenance.json` were checked. The wheel contains the local assets,
font notices and native hosts. Source distribution includes native source and
prebuilt WASM, so ordinary source installation does not build the browser kernel.
`cargo fmt --check`, release/locked wheel build and strict twine checks passed.

## Functional checks

The installed-wheel suite passes **17 tests**, including the original native and
explicit PNG editor tests, GPU-free notebook model/transfer policy checks, concurrent PyO3 core/GIL calls, the
X11 surface test, and the real JupyterLab/WebGPU test.

Desktop checks exercised an actual presented surface, title selection/drag and
text editing, Copy Python clipboard/replay, panel Save PNG, Python PNG export,
resize to 1350×680, close/reopen, and two independent Figures in one event loop.
Normal edit/drag frames reported **2 initial column uploads, 0 RGBA readbacks,
0 PNG encodes**. Reopening preserved the same 2 uploads. Explicit PNG operations
alone increased readback/encode counters.

A separate process with `WINIT_X11_SCALE_FACTOR=1.5` produced a 1905×900 physical
surface from a 1270×600 logical window while keeping the 960×600 document intact.
This checks forced DPI scaling; physical multi-monitor DPI transitions are not
verified.

The JupyterLab test forbids native GPU Figure construction in its kernel and
still displays the chart. It registers two float32 columns of 100,000 samples:
**800,000 binary bytes, 2 browser uploads**. It checks title edit/drag, red series
style, GPU picking, copied Python replay, `await fig.sync()`, browser download,
`await fig.savefig_async(...)`, and Python → browser title synchronization.
An actual composited canvas screenshot must contain the edited red data pixels;
valid JSON/settings or successful PNG export alone do not count as display proof.
External HTTPS asset requests are blocked during the test. Browser/kernel PNGs
are each 960×600. There are no uncaught browser errors.

Ordinary redraw/drag/style changes report **0 PNG exports**, with columns still
uploaded only twice. The two explicit save operations produce 2 PNG exports.
Browser snapshot buffers and widget binary traits are cleared after ready ack.
WASM async operations and redraw are serialized to avoid mutable-borrow overlap
while picking/exporting. Client tokens and revisions distinguish view edits.

## Software browser limitation found during verification

Chromium's headless Vulkan/software configuration could execute renderer exports
and settings operations while capturing a black canvas. A minimal standalone
WebGPU clear reproduces the software presentation issue independently of Figgy.
Verification therefore uses a **headed Chromium on Xvfb with SwiftShader** and
asserts displayed pixels. llvmpipe remains the native test adapter. This is not a
production automatic fallback or a claim that headless/hardware combinations all
work; verify the browser/driver actually used by the user.

## Submission measurement

`benchmarks/results/linux-software-surface.json` records a 100,000-point native
surface run: 60 measured submissions in 3.399 s, **17.65 submitted frames/s**, with
0 RGBA readbacks/PNG encodes. It includes CPU raster/host preparation, queue
submission and software surface presentation scheduling. It is not completed GPU
readback, physical monitor refresh rate, or hardware performance.

`last_input_to_submit_ms` starts at the Rust chart input callback and ends at CPU
submission. Browser timing starts at its input handler and ends at `frame()`
submission. Neither metric measures physical display/input latency.

## Reproduce

```bash
python -m pip install maturin ".[test]" playwright jupyterlab
maturin build --release --locked --out dist
# Install the compatible wheel in a fresh venv, then:
python -m pytest -q tests/test_figure.py tests/test_notebook_model.py
# Xvfb + xdotool + xclip + software Vulkan must be available:
xvfb-run -a python -m pytest -q tests/test_desktop_host.py
# Run real notebook verification in a display-enabled environment:
FIGGY_TEST_JUPYTER=1 FIGGY_TEST_HEADFUL=1 \
  FIGGY_BROWSER_VK_DRIVER=/usr/lib/chromium/vk_swiftshader_icd.json \
  python -m pytest -q tests/test_jupyter_webgpu.py
```

`FIGGY_BROWSER_VK_DRIVER` selects only the verification browser's Vulkan driver;
the production Python wrapper does not set it. `BROWSER_EXECUTABLE_PATH` can
select Chromium. Headed mode requires a working `DISPLAY`/Xvfb. Test screenshots
and raw browser metrics are emitted into pytest's temporary directory.

## Remaining platform work

Windows hardware surface/input/DPI, macOS Metal/event-loop behavior, Wayland,
physical monitor latency and wheel execution on other Python versions were not
run here. Native blocking/nonblocking calls require main-thread event pumping;
there is no automatic foreign GUI-loop integration. A browser view must be
connected for asynchronous exports. Default released notebook snapshots require
reexecuting the Figure cell after reload, or opting into retained snapshots.
PyPI publication is not part of this change.

## Explicit preparation follow-up

The preparation update was built and installed into the same separate wheel
environment. The full suite passed **20 tests**, including native repeated
`prepare()`, GPU-free manual widget request/error handling, and both automatic
and deferred initialization in real JupyterLab. Additional deferred-view closure
and pre-initialization input checks were verified with the installed wheel.

Native CLI preparation completed 82 observed start/finish events in approximately
**1.03 seconds** on llvmpipe. This measures the preparation call plus current
document RGBA execution after constructor initialization; it is not hardware
startup performance or proof of cross-process cache restoration. Native prepare
preserves settings/revision and 2 resident column uploads, adds one completed
RGBA readback per call, and performs 0 PNG encodes.

The manual notebook test observes **0 browser adapter requests** before
`await fig.prepare_async()`. After preparation it displays and edits the real
canvas, with 800,000 initial binary bytes / 2 uploads / 0 PNG exports before
explicit saves. Preparation returns stages and elapsed time. Browser transfer
snapshots are released on ready; creating/discarding an unprepared additional
view does not request an adapter. Automatic mode remains covered separately.

The wheel includes `figgy.prepare`, both preparation APIs, and local JS/WASM.
The sdist includes `docs/PREPARATION.md`; strict twine checks pass. Automatic CI
remains paused (`workflow_dispatch` only).

**No persistent shader cache was saved or restored.** Renderer 0.16.1 exposes
prewarming but no public pipeline-cache injection. Reports explicitly return
`persistent_cache_supported=False`. See `PREPARATION.md` for this boundary and
remaining target-format/first-use costs. Windows/macOS hardware preparation was
not executed.

## Native global sharing follow-up

All native Figures now share one device, renderer and resident pool. The installed
wheel suite passes **25 tests**. Checks cover same-id line/heatmap isolation,
selection identities and scaled PNG/SSOT replay, close/GC cleanup, sequential
context and prewarm reuse, explicit release refusal/reset, four concurrent Figure
constructors/renderers, and a second Figure's failure halfway through upload
without modifying the first Figure's pixels/settings or leaving orphan columns.

The X11 test opens two independent Figures with the same `signal` id, verifies
their common context id, forces pool growth while the first surface remains
alive, and closes one Figure while the other keeps rendering. The original
selection/drag/text/resize/reopen/clipboard/PNG assertions remain. Normal surface
edits still perform no RGBA readback/PNG encoding. The font family input is edited
through real X11 input and its SSOT is checked. Native tests compare actual pixels
after size/color changes and after switching to an installed DejaVu Serif family,
then replay those settings on a second shared Figure.

Real JupyterLab automatic/manual preparation tests continue to pass after adding
font-family inputs. Browser GPU ownership and the binary transfer policy are
unchanged; these tests do not claim native/browser memory sharing.

`benchmarks/results/linux-software-shared-context.json` records eight Figures,
each with two 100,000-value float32 columns, in one context. The first constructor
took **88.46 ms** and the median of seven subsequent constructors was **0.30 ms**.
The shared pool used **12,800,000 bytes** with 16 MiB capacity; 16 independent column
uploads occurred. Prewarm emitted 80 stage events initially and 2 subsequently,
showing installed groups were reused. Preparation timings include current-chart
execution/readback and cannot be interpreted as shader compilation alone.

These are single-run **llvmpipe software-GPU** observations with the existing
driver cache/environment, not a cold-driver benchmark, UI FPS, Windows hardware
result or guaranteed acceleration factor. Reproduce with
`python benchmarks/shared_context.py --output benchmarks/results/shared-context.json`.
Report charts, when generated, continue to use Figgy.

Release/locked wheel/sdist builds and strict twine metadata checks passed. All
shared resources remain native-process local. Windows/macOS hardware behavior,
different surface formats and physical VRAM pressure remain unverified here.
Automatic CI is still disabled; pipeline disk-cache persistence remains absent.

## Contextual desktop editor, vector toolbar and repaint scheduling

`examples/desktop_editor.py` opens a real native surface with two 100,000-sample
signals. `docs/DESKTOP_EDITOR.md` contains X11 captures for the initial chart-centered
view, title/font editing and GPU-selected series editing. The toolbar glyphs are
vector strokes on the native surface with hover/selected backgrounds and tooltips.
These are screenshots of the presented window, not chart PNG exports or mockups. Capture sessions report 4 initial column
uploads and 0 renderer RGBA readbacks/PNG encodes during interaction.

Screenshot inspection exposed an egui popup sizing pass that requested another
frame without a new OS input event. The winit host now schedules egui viewport
repaint deadlines, including delayed caret updates. The installed-wheel native
surface regression checks that popup pixels appear without forcing refresh or
moving the mouse again; drag, font name/size editing, resize, zoom/fit, Copy Python, saves,
reopen and shared-Figure behavior continue to pass. The inspector starts closed,
opens after a chart selection, and reflows the available preview when toggled.
Export-popup interaction does not reopen a closed inspector or zoom the chart
under the popup. UI and Python PNG exports have identical pixels at the original
960×600 document size after preview resize and editing. A separate native
heatmap UI test edits bounds and a colormap and checks Python settings/to_code()
without readback, PNG encoding or column reuploads. The example's blocking
`show()` opens a window, handles a normal X11 `WM_DELETE_WINDOW` request and exits
successfully. Wheel/sdist builds and strict twine checks pass. These remain Linux
software-GPU checks, not Windows/macOS hardware screenshots.

The final installed-wheel suite passes **26 tests**, including actual headed
Chromium/JupyterLab WASM/WebGPU tests (SwiftShader browser GPU, llvmpipe native
GPU). Installed JS/CSS/WASM files and native extension loading were checked;
the sdist contains the native editor source, example and screenshots.
A separate X11 run with `WINIT_X11_SCALE_FACTOR=1.25` verifies physical icon bounds,
chart selection, inspector opening and resize with no PNG/readback or reupload.
This is a forced scale-factor check, not a physical monitor/DPI transition test.

![Installed-wheel JupyterLab WebGPU output](images/notebook-webgpu.png)
