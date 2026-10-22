# Host verification history

## Current 0.3 validation setup

The current binding is `figgyplot 0.3.0`, targeting `figgy-renderer 0.18.0`
and `figgy-model 0.12.0`. The dated measurements and test totals below belong
to earlier checkpoints; they are not a test count or performance claim for the
current release candidate.

### Layout and review editing follow-up (2026-10-22)

The installed release wheel passed **273 focused model, history, recovery and
oracle cases**, **12 real UI cases** (9 paired native/Jupyter and 3 native-only), and **134 workflow
and packaged-asset checks**, with no skips in those runs. Full collection contains
809 cases; the focused runs do not establish a complete CI result.

The input cases cover first-click plot geometry editing, inspector resizing,
unchanged plot dimensions when opening the inspector, disabled polar/radar wheel
zoom, annotation drawing, targeted Korean review comments, comment editing and
deletion, title/series ownership, and annotation dragging. Geometry checks also
resize radar, box, pie/donut and bar documents and restore their exact settings
with Undo. Subscription is checked through both Python and the CLI across the
complete Figure approval barrier.

Annotation drag checks save complete before/after SSOT dumps. Only the selected
arrow's four coordinate values change; the other annotation, series, axes and
layout remain identical, and no columns are uploaded again. During the synthetic
gesture, property descriptions rebuild 0 times in native and 1 time in the
browser. [Recorded counters and SSOT changes](measurements/layout-review-host-work-20261022.json)
include the tested wheel digest. Elapsed times include input-driver waits and
are not a physical-GPU frame-rate measurement. Renderer drawing/cache behavior
is unchanged.

Environment: Linux x86_64, Python 3.12.14, llvmpipe Vulkan, Xvfb/Openbox,
Chromium 154/SwiftShader and installed Noto Sans CJK KR. Rust formatting, JS
syntax, installed-package checks and property-catalog inventory checks passed.
Physical GPU and Windows/macOS runtime behavior remain unverified by these runs.

PR run 61 did not execute tests: its build job exhausted the existing 20-minute
budget after the Azure Ubuntu mirror downloaded 105 MB in 14 minutes 37 seconds
(120 kB/s). Font unpacking/setup took seconds. The
[timestamped log evidence](measurements/ci61-ubuntu-mirror-20261022.json) records
the download separately from font configuration and build cancellation. Both CI
install steps now use the official Ubuntu archive for the same signed packages;
test assertions, execution auditing and job budgets are unchanged.

Run 62 built the wheel successfully, but one shard's setup failed when the
image's unrelated Microsoft APT feed returned HTTP 403. Its log also showed
that replacing a host in `ubuntu.sources` did not override the image's separate
mirrorlist. The final [shared installer](../scripts/install_ci_runtime.sh) uses
an explicit temporary source list for the official Ubuntu archive and security
feeds, with the Ubuntu archive signing key and image source parts disabled for
both APT commands. No repository error is ignored. Three local installer checks
exercise the real APT URI planner, detect vendor feeds when isolation is removed,
and stop installation after an update failure. See the
[failed setup evidence](measurements/ci62-image-apt-sources-20261022.json).

Run 63 completed three shards with 202 passing cases each. The fourth exposed
a native form regression: after Esc cleared a pie selection, the geometry form
hid the ordinary title/material controls. The existing test was retained and
reproduced locally before the fix. Geometry now takes priority for explicit plot
selection or Layout mode; ordinary unselected editing keeps its global form.
The expanded test edits title/material, checks Copy Python and no readbacks, and
compares complete settings across mode switches with the same settled pointer
hover state. All 12 focused UI cases and the 48 cases not executed after that CI
failure passed locally. See the [before/after control evidence](measurements/native-unselected-form-20261022.json).

Automatic pull-request checks are enabled in
[PR tests](../.github/workflows/pr-tests.yml), including Linux native/Jupyter
integration. The [interaction parity guard](../scripts/check_interaction_parity.py)
rejects changes to only one host without the corresponding host/test updates.
[Shared interaction tests](../tests/test_interaction_parity.py) cover native and
real Jupyter WebGPU controls. Pies/donuts, categorical bars and boxplots now use
both hosts; radar and multi-panel documents are also covered by the renderer
0.18 integration. The historical native-only radial limitation below no longer applies.
See [chart types](CHART_TYPES.md) and [desktop editing](DESKTOP_EDITOR.md) for
current supported controls. A configured check or an earlier passing run does
not establish the result of a later commit; inspect that commit's CI result.


## Overlay ownership and ambiguous selection (2026-10-20)

The installed release wheel passed **15 focused real-host cases, with no skips**
across two runs on Linux x86_64, Python 3.12.14, native llvmpipe Vulkan and headed
Chromium 154/SwiftShader under Xvfb/Openbox. The installed native binary and browser
assets were compared byte-for-byte with the final wheel and browser source.

Coverage includes direct editing/dragging of inactive secondary-axis objects,
independent secondary ranges even when their numbers match the primary axes,
inactive annotation drag/endpoint resizing, same-axis and cross-axis coincident
series, duplicate labels, keyboard/hover preview and cancellation, retained chart
ownership for fully overlapping panels and tree selection, isolated Y zoom,
primary opposite-axis property pairing, numeric drafts and multiline text during
resizing. A new object's form starts at the top. Preview checks preserve the
native document/revision and browser settings; the browser ambiguity scenario
sends exactly one edit to Python when a target is finally chosen. Source uploads,
reference-fill settings and legend contents are preserved.

The preceding Actions run at `3a8aa75` had **430 passed and 3 failed**. All three
failed cases passed in this local run. Fixes complete sidebar click delivery
before replacing controls, retain the selected property's input value across
queued work, and constrain the inline text editor horizontally through CSS layout
during resizing. Additional ownership checks exposed and fixed native overlay
edits propagating into primary axes and browser rejection of the canonical
omitted `Base` default.

Workflow/assets preflight passed **112 tests**; Rust formatting/locked compilation,
JavaScript syntax and release wheel packaging passed. The final PR's Actions
result is independent of these local results. See the
[selection design and official application references](EDITOR_SELECTION_DESIGN.md)
and [actual host screenshots](DESKTOP_EDITOR.md).

## Renderer 0.18 feature integration (2026-10-20)

Local verification covers all **409 current suite cases** across a complete
integration run and focused reruns of affected and newly added cases. The final
installed release wheel passed **72 focused cases**, including all new feature
model/replay tests, malformed-input and concurrency checks, native window
regressions, mixed panel styles on real Jupyter WebGPU and the actual
maturin-action contract. Cases skipped in the complete run because the action
path was unset were subsequently executed with the real action file.

Environment: Linux x86_64, CPython 3.12.14, Rust 1.99.0, native llvmpipe
software Vulkan, Xvfb/Openbox and headed Chromium 154 with SwiftShader.
The complete run exercised both real hosts: editing, zoom/pan, picking,
annotations and endpoint resizing, active panels/layers, linked axes, radar,
vector fields, mapped points, fills/steps, polar charts and whole-document PNGs.
Mixed precise/stylized panels replay identically at export scales 1, 1.25 and 2.
Ordinary display checks assert no PNG transport or whole-image native readback.

Workflow/asset preflight passed **112 tests**. Locked Rust compilation,
formatting and JavaScript syntax checks passed. Wheel and sdist builds include
the new Python/Rust modules; separate-environment installation, packaged-asset
verification and public API smoke checks passed. The matching upstream WASM
assets and their provenance remain unchanged from the #15 migration baseline.

These are local software-GPU results. The required Actions checks must pass on
the final PR commit independently; physical GPU, Windows/macOS and ARM64 runtime
coverage are not established by this record. Manual plotting remains separate
from the future #18 review controller and binary recovery cache.

## Reported issue verification (2026-10-20)

The source fixes for issues #6–#13 were already present before the renderer
0.18 migration. They were rechecked on the migration branch with Python
3.12.14 on Linux x86_64 and llvmpipe software Vulkan. These are source-build
results. PyPI 0.3.0 is already published with renderer 0.17.0/model 0.11.0;
its sdist contains the earlier fixes. The renderer 0.18 migration is subsequent
source work and does not replace published artifacts.

| Issue | Resolution and regression evidence |
| --- | --- |
| [#6](https://github.com/shim9610/figgy-python/issues/6) | Automatic range setters retain their documented tick derivation. `set_xlim_without_tick_auto` / `set_ylim_without_tick_auto` preserve explicit tick and label settings; tests cover linear/log axes on native and browser models. |
| [#7](https://github.com/shim9610/figgy-python/issues/7) | Histogram recoloring writes `fill_color` and exports the same setting in generated Python. |
| [#8](https://github.com/shim9610/figgy-python/issues/8) | Sketch rejects unsupported existing histograms and new unsupported series, preserving the current settings and rendered image. |
| [#9](https://github.com/shim9610/figgy-python/issues/9) | A grayscale colorbar has no brightness reversals inside its ramp; the pixel check excludes the antialiased frame and covers the former one-third/two-thirds discontinuities. |
| [#10](https://github.com/shim9610/figgy-python/issues/10) | Unknown font families raise `ValueError`; supported and default names remain accepted. |
| [#11](https://github.com/shim9610/figgy-python/issues/11) | Unicode super/subscripts normalize to rich text. A Greek alpha in the Latin-only handwritten face uses fallback and renders differently from an unassigned character's missing-glyph box. |
| [#12](https://github.com/shim9610/figgy-python/issues/12) | Multiline title helpers grow the title band; direct settings retain explicitly chosen geometry. |
| [#13](https://github.com/shim9610/figgy-python/issues/13) | The original unsupported multi-panel message used the running package version. The subsequent #16 integration now supports multi-panel construction and tests stable public panel addressing. |

The behavioral checks are in `tests/test_issue_fixes.py`. Native/Jupyter
interaction checks and renderer-migration coverage are recorded separately;
these issue checks do not establish physical GPU or Windows/macOS results.

## Historical 0.2 checkpoints (2026-10-14)

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

When `FIGGY_BROWSER_VK_DRIVER` selects the software-GPU verification driver, the
shared Jupyter harness sets Chromium's GPU watchdog to 180 seconds, matching the
existing first-frame startup deadline. The watchdog remains enabled; device-loss
errors, gesture deadlines, and interaction assertions still fail the test.
[CI run 38883720288](https://github.com/shim9610/figgy-python/actions/runs/38883720288)
recorded the ceramic donut failing before its first frame: Chromium terminated
its GPU process after about 30 seconds with raw POSIX exit status 512, which is
Chromium's `RESULT_CODE_HUNG` (2), and WebGPU reported a lost external Instance.
Chromium's `gpu/ipc/service/gpu_watchdog_thread.cc` terminates a hung GPU process
with that result code and accepts the `--gpu-watchdog-timeout-seconds` override.
This test-only budget accommodates cold SwiftShader compilation on shared CI
CPUs; production browser configuration is unchanged. The saved `chromium.log`
provides the GPU process diagnostic alongside the normal browser error records.

Later hosted runs exposed a different startup failure: the chart and toolbar
were visible with no GPU or JavaScript errors, but Playwright's frame-based
button stability check timed out. Initialization now waits for the final
CSS/device-pixel-sized surface before reporting Ready and avoids an immediate
duplicate frame. The preparation-overlap test checks button visibility,
geometry and hit targets with timer polling, then uses real mouse events.
Its setup is also tested with animation-frame callbacks suppressed, so moving
a frame-dependent `trial` click earlier cannot reintroduce the same failure.

The subsequent hosted run reached PNG export but exceeded its 60-second
deadline. Reproduction with the hosted Chromium 156/SwiftShader build recorded
three unfinished surface frames when export began: those frames took about
31.7 seconds to finish, export rendering/readback took another 12.9 seconds,
and PNG encoding/result transmission took about 42 milliseconds. This reproduces
GPU queue latency, but the original hosted timeout did not record per-stage
timestamps and is not itself proof of the same timing breakdown.

Comparison with figgy-web `18cdff3` (also renderer 0.17.0) identified the missing host boundary:
`app/js/bounded-studio.js` submits with `render()` and waits separately on
`BoundedCanvas.gpu_ready()`. That Promise retains no chart borrow. Python's first
backpressure fix instead awaited `first_frame_ready(&mut self)` inside its
edit/acknowledgement queue, adding GPU latency to the edit-only `fig.sync()`
contract. It has been replaced with a synchronous `frame()` submission and a
separate non-borrowing `gpu_ready()` fence. New display submissions wait for the
fence; edits and acknowledgements continue. Export and preparation wait explicitly.
The completion bridge is recorded in `scripts/wasm-host.patch`; renderer/model
sources remain identical to their published crates.

A held-completion regression sends a burst of real pointer input and checks
that submissions stay bounded while the final drag and PNG remain correct.
It also switches inspector targets while completion is held and checks that
controls immediately match the selected target, without waiting for a WASM borrow.
An edit barrier must return with accepted final settings while the GPU fence is
still held; this fails with the previous shared-queue implementation.
Validation of the replacement on Chromium 156.0.8078.4/SwiftShader: **326 tests
passed** in the complete local integration run, including native and Jupyter
interaction cases; preflight **107 passed**. The radial export took **24.1 s**:
12.1 s waiting for the one outstanding display frame, 11.9 s rendering/readback,
and approximately 0.04 s encoding/transmission. These software-GPU measurements
are not physical-GPU frame-rate or export-latency claims. No hosted CI run has
been performed at that local validation checkpoint.

The subsequent hosted run for `3f2c253` reported **293 passed, 1 failed and
32 setup errors**. The radial failure was `Browser prepare timed out after
60 seconds` in the deliberate preparation/menu/resize overlap scenario, before
its PNG export check. The setup errors came from `git apply --numstat` filtering
patch paths when fixtures lived below the checkout (`--basetemp=ci-results`).
The asset checker now parses in an isolated Git root; the checkout-local asset
suite reproduces the old errors and passes after that correction.

Until this failure is resolved, CI runs the asset suite and exact radial case
first, then the full suite. Priority and full results use separate directories
so pytest cannot delete earlier evidence. Verbose, unbuffered output identifies
the active test. Notebook diagnostics retain actual adapter/device metadata,
existing submission/fence/readback timings, host queue/request stages and the
artificial preparation gate's release time on success and failure. Failures
also print a compact diagnostic summary in the job log. Observers add no GPU
completion requests, and timeout values and behavioral assertions are unchanged.
Local validation of this diagnostic update: **112 preflight tests passed** and
**49 priority tests passed**, using a checkout-local temporary directory. The
radial trace recorded a 0.14-second artificial gate, two preparation frames
within a 26.8-second request, and approximately 0.2-1.4 ms edit barrier responses.
These are local software-adapter observations, not a reconstruction of the
preceding hosted timeout. The next hosted run must supply its own stage evidence.

A separate standalone comparison removed Jupyter from both paths and rendered
the same three-slice donut with figgy-web `18cdff3` and the Python WASM host.
Both used renderer 0.17.0, Chromium 156.0.8078.4, DPR 1 and the actual
Google/SwiftShader fallback adapter. After one cold frame, the mean of two
completed warm frames and a subsequent export with no pending display work were:

| 960 x 600 material | Web frame | Python frame | Web PNG | Python PNG |
| --- | ---: | ---: | ---: | ---: |
| Flat | 11.94 s | 11.96 s | 12.95 s | 11.20 s |
| Ceramic | 12.38 s | 13.43 s | 13.70 s | 12.78 s |

At 480 x 300, warm frames took approximately 2.8-3.6 seconds, consistent with
cost increasing with pixel count. CPU submission at 960 x 600 took only
0.25-1.3 milliseconds; export GPU readback waiting accounted for all but
37-41 milliseconds. Decoded PNG pixels were identical between hosts in all
four size/material pairs. This establishes that the slow single-frame workload
also occurs in figgy-web on this software adapter, independently of Python's
frame scheduling. It does not establish hardware-GPU latency or identify a
specific shader instruction as the bottleneck. Depth was zero and shadows were
disabled, so this case did not execute the depth raymarch or shadow path.

The export deadline is unchanged. Use the browser and bundled driver selected
by `scripts/ci_gpu_env.py` when reproducing hosted failures; a system Chromium
installation can be a different version from Playwright's CI browser.
Each shared notebook scenario records the actual browser version, executable
and driver filename in `browser-info.json` alongside its other artifacts.

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
The sdist included `docs/PREPARATION.md`; strict twine checks passed. At this
checkpoint automatic CI was paused (`workflow_dispatch` only); current PR checks
are described above.

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
Automatic CI was still disabled at that checkpoint. Pipeline disk-cache
persistence was not implemented by that change.

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

## Native editor review follow-up (2026-10-14)

The editor review fixes preserve the fitted document aspect ratio and expand a
normal window horizontally for the inspector. Closing the inspector restores
the previous chart space. Maximized/fullscreen windows show the inspector as an
overlay. Toolbar/status controls remain outside the overlay. Advanced JSON now
opens in a separate native OS window on the same renderer context; invalid
edits preserve the document and leave both windows usable.

Legend labels are edited as separate entries, preserving their renderer marks
and separators. Title, legend, axis-title and tick/axis visibility controls can
restore hidden objects through the object list. The color picker reserves its
SV marker radius between the square, hue bar and popup boundary.

Native data selection supports Esc, empty-space clicks and repeated-hit toggles.
Left/right step point indices, up/down choose another point series, and matrix
arrows step cells in the displayed axis directions. Selected decorations can be
nudged with arrows. The inspector shows the selected index, X/Y and matrix
value by reading only those hi/lo samples from GPU storage. No full source
array is retained on CPU; `selection_value_readbacks` is separate from RGBA and
PNG counters. F11 toggles fullscreen.

An installed release wheel passed **42 tests, 3 skipped** on a separate X11
screen with Openbox and llvmpipe (32.26 s). Actual mouse/key tests cover inspector
open/close dimensions, constant aspect ratio, data selection/navigation/clear,
visibility restoration, individual legend labels, the black color-picker marker,
separate settings window identity and atomic rejection/recovery, maximized and
fullscreen overlays, copy/replay, resize/reopen and identical UI/Python PNGs.
Screenshots were inspected. The three skips are the optional Playwright editor
and two opt-in Jupyter/WebGPU tests; browser verification was not rerun here.

The two selected-value tests also pass on the real Radeon 8060S/RADV adapter
(0.14 s), including source-array mutation, float64 hi/lo reconstruction, bounded
point/series/cell navigation and zero RGBA/PNG work. UI automation uses software
Vulkan because this isolated X11 screen has no DRI3 hardware presentation.
The user's review window runs separately on native Wayland/Radeon Vulkan.

A follow-up visibility review adds an always-available **Show / hide** toolbar
menu. It restores chart titles, legends and axis titles without a selected
object or open inspector. The native input test explicitly hides the title,
clears selection, closes the inspector, and restores it through this menu;
legend and X-axis-title toggles use the same route.

The extended visibility-menu input test passes (22.27 s). A bounded 20-step
native UI mutation run also completes: 5 rejected edits preserve state, 2 valid
edits, 3 resizes and 2 main-window reopenings, with the sentinel Figure unchanged.
The multi-window driver forces a pointer-motion event when returning to a window
and waits for the separate settings window to become ready before editing it.

### Readable Python export and axis navigation (2026-10-14)

Copy Python and `Figure.to_code()` now share a GPU-free exporter. Titles, axis
labels, ranges, scales, grid, legend and common series styles use Python setters;
advanced styling/layout uses readable `Figure.configure()` patches. Font sizes
convert renderer pixels to Python points at the Figure's DPI. Replaying the
user-provided snapshot reproduced its settings exactly in 36 lines, including
custom offsets. Source arrays are preserved. Native clipboard replay and exact
RGBA replay passed. Browser widgets use the same exporter after pending edits
are acknowledged; browser UI integration was not executed in this run.

The installed-wheel full suite passed **56 tests, 3 skipped** (Playwright absent,
two Jupyter integration tests opt-in). Four replay/selection tests also passed
on Radeon 8060S Vulkan. The subsequent axis-mapping correction passed **3 actual
X11 input tests**: Ctrl+wheel zooms X only, Shift+wheel zooms Y only, plain wheel
zooms both, and dragging pans. Zoom-in/out preserve the data coordinate under
the physical pointer, including log and inverted axes; the untouched axis stays
unchanged. Independent windows share the GPU while keeping their documents
separate. English instructions are displayed above the graph. Two revised
review windows were launched on Radeon with the current edits preserved.

### Default margins and public README recording (2026-10-14)

The Python hosts had reduced the renderer's left/bottom axis bands from
110/80 pixels to 65/55 pixels. Restoring the renderer defaults in both native
and notebook configuration separates the Y-axis title from numeric ticks.
A raster regression checks a clear gap after the title and native/notebook
configuration parity. The randomized campaign's valid starting canvas was
increased from 240×200 to 320×240 to fit the default axes and heatmap colorbar.

The installed-wheel full suite passed **57 tests, 3 skipped** in 44.06 s on
isolated X11/llvmpipe. Skips remain the absent Playwright dependency and two
opt-in Jupyter integration tests. The default-layout and Python replay subset
also passed on Radeon 8060S Vulkan.

The README GIF uses the automatic TopRight legend with zero offsets over a
late response peak. Actual input adjusts each axis, increases the left margin,
moves the Y title and moves the legend. Copy Python is pasted byte-for-byte
into the installed VS Code, saved and executed through its integrated terminal.
Three distinct PNGs are opened in three VS Code editor columns. The earlier
recording-only PySide6 code input helper was removed. The final GIF contains
86 frames over 14.48 seconds; captions and a pointer halo are composited over
actual windows. The checked-in clipboard code was replayed on Radeon for
three datasets, with six initial column uploads each and no style reuploads.
The recording's isolated terminal profile uses `figgy-demo $` and an editor
title containing only the active filename; personal usernames, hostnames and
temporary workspace paths are not displayed in those fields.

### Public gallery and documentation (2026-10-14)

Eight runnable Python recipes now generate the README gallery: dense signals,
scatter populations, parametric curves, logarithmic axes, model/measurement
markers, an interpolated signed field, a correlation matrix and a spectrogram.
All eight were rendered with native Radeon 8060S Vulkan and visually inspected.
Every standalone CLI exported a 960×600 PNG. An isolated X11/llvmpipe check
also opened a gallery example with `--show`, closed it through the window manager
and verified successful PNG saving. `scripts/render_gallery.py` reproduces the
images and records source links, dimensions, adapter identity and SHA-256.

The README, desktop guide, randomized validation and Linux/Windows benchmark
reports use English. Translation preserved all benchmark table measurements
and reproduction commands. Local Markdown links, Python code-block syntax,
gallery source/image pairs and image hashes/dimensions were checked. The updated
public GIF was re-recorded with the neutral terminal prompt; exact clipboard
paste, actual terminal execution and three distinct output images passed again.

### Pie/donut and stylized Python bindings (2026-10-14)

Python now exposes `Axes.pie`, `Axes.donut`, `RadialArtist` slice/value edits,
`Figure.set_radial_style`, `configure_radial`, `set_facecolor` and
`set_draw_style`. Pie/donut documents use public upstream `RadialChart` and
`RadialRenderer` on the shared native device. Native windows paint the upstream
frame to a GPU texture within egui; ordinary selection/property edits require
zero column uploads, RGBA readbacks or PNG encodes. Cartesian-axis operations
are rejected for radial Figures rather than silently changing unused settings.

The installed final wheel passed **78 tests, 3 skipped** in 52.09 s on isolated
X11/llvmpipe. This includes actual slice selection/clearing, keyboard navigation
past zero-valued slices, title/material edits, clipboard export, inspector size
preservation, maximized overlay and PNG saving. The material menu was expanded
after its default scroll height obscured lower choices during input validation.
The skips remain absent Playwright and two opt-in Jupyter/WebGPU tests.

The **19 new model/render tests** also passed on Radeon 8060S Vulkan (0.60 s).
They cover pie/donut differences, all eleven material shaders with distinct
pixel hashes, NumPy mutation independence, bounded-data validation, radial
picking/preparation, data-preserving code replay, high-DPI style replay,
backgrounds and atomic rejection. Exported radial styles clear transient
selection/hover and preserve new datasets' values, including zero-valued slices.

Milkyway accepts only Line series: scatter, marker lines and heatmaps are
rejected through public setters, raw settings and subsequent additions. The
native menu disables incompatible modes, and the browser host checks the same
series-kind rule before installation. Constellation requires marker lines.
Unknown draw-style options are explicitly checked because internally tagged
serde enums can conceal ignored fields from `serde_ignored`.

Renderer scratch-cache IDs remain namespaced per Figure. GPU style uniforms
derive their star/sketch pattern salt from stable user series IDs, allowing
identical replay across independent Figures without mixing source data.

The gallery now contains **17 actual Radeon renders**, including pie, ceramic
donut, paper/wood/hatch/pearl, Sketch handwriting, Constellation and line-only
Milkyway. Every variant was reproduced in an independent CLI process with exact
PNG SHA-256 agreement. English Markdown, example links, Python code-block syntax,
manifest hashes/dimensions, Rust formatting and browser JS syntax were checked.
Browser model/transport support for Cartesian styles was included, but actual
browser style pixels were not rerun at that checkpoint. Interactive browser
radial bindings were not yet exposed then; radial windows/PNG export required
the native backend. The current 0.3 binding supports interactive radial charts
and browser PNG export in Jupyter as well.

## Renderer 0.18 panel focus and editing regressions

Draft PR #19 adds host-owned focus for multi-panel figures. The first canvas
click selects a stable panel ID without changing plot geometry or selecting data;
subsequent clicks resolve visible base/secondary axes and series automatically.
A gutter click or Esc leaves the panel, and an unfocused grid ignores wheel zoom.
Native surface placement and input bounds now cover the whole document, and its
focus outline uses the final stage after inspector docking. Browser queued input
coordinates follow the current canvas size. Screenshots are in the editor guide.

The preceding Actions run had 428 passes and three failures: two radial text
editing waits and one numeric precision edit. Bounded annotation maps are prepared
synchronously by the renderer, so their reads and text hits no longer wait for a
material GPU frame. Background acknowledgements preserve focused form drafts,
and sidebar pointer gestures defer rebuilding controls until after the click.
Native UI input tests wait for a processed host frame rather than assuming a
fixed 100 ms delay; they do not retry or replay actions.

The installed release wheel was checked on Linux x86_64, Python 3.12.14, Rust
1.99.0, native llvmpipe, Xvfb/Openbox and headed Chromium 154 with SwiftShader.
Focused real-host coverage includes both grid hosts, direct secondary-axis/data
selection, isolated Y zoom, escape/gutter release, numeric drafts across Python
updates, radial text edit/cancel/delete and multiline/resize/format preservation,
and Cartesian inline text plus tree ownership/reveal. Native checks retain zero
RGBA readbacks/PNG display transport and unchanged source upload counts.
Workflow/assets preflight has 112 passes; formatting, locked compilation,
JavaScript syntax and installed browser asset comparisons also pass. Full Actions
integration results are reported by the PR checks, independently of local results.
