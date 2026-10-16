# Randomized input, state and concurrency validation

This is a historical campaign report for the checkpoint below. Its call counts,
wheel contents and timing results have not been rerun or relabeled as results
for `figgyplot 0.3.0` / renderer `0.17.0` / model `0.11.0`. Current pull-request
checks are enabled in [PR tests](../.github/workflows/pr-tests.yml); current host
coverage is described in [host validation](HOST_VALIDATION.md).

2026-10-14, Linux x86_64, public `figgy-renderer 0.16.1`. Native checks used
Vulkan llvmpipe; notebook checks used actual JupyterLab, headed Chromium and
SwiftShader WebGPU. These are not Windows/macOS hardware results.

## Cause of the long-running case

[Upstream issue #6](https://github.com/shim9610/figgy/issues/6) includes a GPU-free
Rust reproduction and native stack/CPU evidence. The reproduction is also in
[scripts/repro_upstream_colorbar](../scripts/repro_upstream_colorbar/).

At the recorded renderer 0.16.1 checkpoint, upstream `Config::validate()` accepted
a heatmap with
`chart_title.top_margin = -1e38`. On a 320×240 canvas, `data_area()` height
saturates at `u32::MAX`, and `draw_colorbar_strip()` attempts approximately
4.3 billion CPU bands. Native stacks at 25/50/75/100 seconds remained in
rectangle drawing within axis/decoration CPU rasterization. CPU user time
continued rising while GPU threads waited. An external test watchdog terminated
the process at 110 seconds. This is a finite but pathological CPU loop; the
earlier explanation of a GPU submission/readback deadlock was incorrect.

Production code has **no 30-second submission or 1-second readback limit**.
Existing GPU completion and mapping-callback waits remain intact. Long legitimate
renders are not interrupted at an arbitrary deadline. User-configurable notebook
comm timeouts such as `prepare_async(timeout=...)` are separate and do not
forcibly stop browser rendering.

The binding workaround rejected negative title margins with `ValueError`
before commit. That guard remains in the binding; common-model
`Config::validate()` checks other layout rules. Use
`offset_y` to move a title upward. No arbitrary 8192-pixel font/line cap was
introduced; existing canvas-size limits remain.

## Method and results

`scripts/check_randomized.py` uses fixed seeds to generate:

- Mutations/deletions throughout the nested settings tree and unknown fields.
- NaN/Inf, extreme finite numbers, Unicode/NUL, invalid types and array ranks,
  noncontiguous arrays, different dtypes and invalid API arguments/IDs/backends.
- Random sequences of construction, series addition, edits, fit, limits,
  selection, dragging, serialization, close and recreation.
- Four-thread mixtures of shared-Figure reads/edits/rendering and independent
  Figure creation/closure.

Workers run in separate processes. Watchdog failures preserve stacks, the last
call and seed. A watchdog expiry alone is not classified as a deadlock or GPU
fault. Bounded test arrays/canvases constrain test resource use; they do not
implement product downsampling or streaming.

Seeds 0–31 covered native and the GPU-free notebook model: 128 sequential
workers × 500 calls and 64 concurrent workers × 4 threads × 500 calls, totaling
**192,000 calls**. All 192 processes completed, with zero watchdog expiries.
The slowest worker took 17.501 seconds. See the
[aggregate JSON](../reports/randomized-model.json).

| Outcome | Calls |
| --- | ---: |
| Accepted | 58,193 |
| ValueError | 100,666 |
| TypeError | 23,493 |
| RuntimeError | 9,501 |
| OverflowError | 147 |

Rejected sequential calls must preserve settings, revision, column count/bytes
and the next ID. Accepted settings must remain replayable. A separate sentinel
Figure's settings and native RGBA output were also checked. All 256 worker
threads exited, and all 128 sequential workers recovered after errors.
Completed RGBA checks do not measure display FPS or input latency.

## Other issues found and fixed

- Failed `imshow()` calls previously changed colorbar/axis state early. Upload,
  registration, fit and heatmap bounds now form a document transaction;
  failures restore columns, settings and revision.
- Finite JSON numbers could overflow renderer f32 fields into Inf and serialize
  as `null`. Model conversion and serialization round trips are now checked
  before GPU work.
- Finite source values unrepresentable as hi/lo, and wholly NaN/Inf arrays, are
  rejected clearly. Existing f32 input and hi/lo encoding are preserved.
- Non-string targets/code variables no longer expose internal `AttributeError`.
- Notebook calls to native selection/drag methods raise `RuntimeError` with
  backend/browser guidance.
- Invalid `show(block=...)`, widget backend/auto_prepare and nonfinite async
  timeouts are rejected before dispatch. Missing-widget/response timeouts have
  contextual messages.
- Browser recovery now clears stale error text when valid settings are installed;
  checks verify this after every recovery.

Regression checks live in `tests/test_invalid_state.py`. A real GPU column
allocation failure also verifies that the existing chart/pool survives and can
render afterward.

## Actual hosts and installed package

Real X11 events exercise selection, dragging, toolbar clicks, full-settings edits,
resizing and close/reopen. Normal redraw/drag must not increase column uploads,
RGBA readbacks or PNG encodes. Notebook checks use the actual JSON editor and
kernel revision acknowledgements, then compare browser/kernel settings.

Desktop seeds 0–3 completed **320 actions**: 89 invalid settings rejections,
44 resizes, 44 close/reopen cycles and 76 pointer actions. Across 6,850 surface
submissions, ordinary interaction caused zero column reuploads, RGBA readbacks
or PNG encodes. Xvfb scale factor was 1.0.

An installed-wheel notebook run used seed 9610 for **300 edits**: 279 rejected
and 21 accepted. Settings and error state were checked after every recovery;
browser/kernel settings matched. Initial upload stayed at two columns/2,048
bytes, with zero PNG generation during editing. Subsequent explicit browser and
kernel PNG exports also passed.

At that validation checkpoint, a final wheel installed into a separate venv
passed **42 tests, zero skips** in 127.99 seconds. This included actual native
surfaces, the kernel PNG editor and JupyterLab WASM/WebGPU with automatic and
explicit preparation. Native extension, JS and the 8,112,575-byte WASM asset
loaded from site-packages. Later editor checks are recorded in
[host validation](HOST_VALIDATION.md).

[Host aggregate JSON](../reports/randomized-hosts.json) records installed-wheel
results. Regular notebook regression retains 100,000 samples; the 300-edit
settings mutation run uses 256 samples/two columns/2,048 bytes.

## Reproduce

```sh
# Use an installed wheel or a maturin develop environment.
python scripts/check_randomized.py --seeds 32 --steps 500 --timeout 90 \
  --artifacts randomized-results/model

# Linux X11 with DISPLAY, xdotool and xclip available.
python scripts/check_randomized.py --backend native --phase ui \
  --seeds 4 --steps 80 --timeout 120 --artifacts randomized-results/desktop

# JupyterLab, Playwright, Chromium and WebGPU available.
FIGGY_TEST_JUPYTER=1 FIGGY_TEST_HEADFUL=1 FIGGY_FUZZ_BROWSER=1 \
  python -m pytest -q tests/test_jupyter_webgpu.py -k True

python -m pytest -q tests/test_invalid_state.py
```

Reproduce one seed with, for example,
`--seed N --seeds 1 --backend native --phase concurrent`. Inputs are reproducible;
thread scheduling can vary. This campaign does not prove deadlock absence for
all inputs/drivers. Actual VRAM exhaustion, large OS-memory exhaustion, all
browsers and Windows/macOS hardware were outside its scope. Automated CI was
disabled at this checkpoint; the current PR workflow is enabled.
