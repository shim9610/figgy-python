# Radial GPU latency measurement

The radial screenshot timeout has a substantial rendering cost behind it.
Repeated donut frames on SwiftShader take seconds after pipeline preparation has
completed. Browser animation-frame callbacks are delayed while DOM timers continue
and the editor's geometry stays fixed. The screenshot's stability check consequently
waits for browser frames even when the element has stopped moving.

## Local measurements

Application commit `6258686`, renderer 0.18.0/model 0.12.0 and matching WASM revision
`3a0a6a33be14f2ff4dab1475d4fcec9eafa1ee04`. Linux x86_64, Chromium
154.0.8037.57, headed Xvfb/Openbox, SwiftShader, five allowed CPUs with a cgroup
quota equivalent to four CPUs. The chart is the failing scenario's default
three-slice **Flat** donut, with zero depth/tilt, no shadows and no outlines.

Times below measure queue submission to an already-requested GPU completion
fence. Duplicate fences observing one submission are counted once.

| Controlled case | Physical canvas | GPU completion |
| --- | --- | --- |
| Donut, smaller display | 480 × 300 | 3,255.2 ms |
| Donut, original display restored | 960 × 600 | 12,690.2 ms |
| Donut, subsequent property edit | 960 × 600 | 12,967.8 ms |
| Cartesian line, original display restored | 960 × 600 | 81.5 ms |
| Cartesian line, subsequent property edit | 960 × 600 | 20.9 ms |

The donut's pixel count increases fourfold and its GPU time increases 3.90 times.
An independent repeat using the checked-in profiling script measured 3,188.2 ms
at 480 × 300, 12,760.9 ms after restoring 960 × 600, and 12,143.1 ms for the
subsequent property edit. The corresponding line-chart edit took 21.0 ms.
Subsequent full-size frames remain slow. The async radial pipeline preparation
observed in the annotation scenario took 546.7 ms; synchronous pipeline creation
and shader-module calls were at most 0.2 ms, and queue submission itself was at
most 0.2 ms. The dominant measured cost is repeated GPU work, rather than a
one-time preparation delay or a slow JavaScript `submit` call. These fence times
include all work for the submission; they do not isolate individual shader
instructions or exclude driver-side work.

In the exact annotation test, full-size GPU frames took 12.47–14.27 seconds.
After Properties resized the canvas to 699 × 437, two frames took 6.43 and 6.64
seconds. The final screenshot took 13.17 seconds and passed locally. During the
first resized GPU frame, 64 timer samples observed one fixed editor rectangle and
one fixed canvas rectangle; timer intervals were 79.2–111.1 ms. Animation-frame
callbacks had gaps up to 14.14 seconds. The two resized long-animation-frame
entries had zero JavaScript blocking duration.

Machine-readable results: [measurement summary](measurements/radial-gpu-2026-10-21.json).
The full raw timings remain in the local diagnostic output and in CI artifacts
when timing observers are enabled.

## Relation to the failed CI run

[Run 39483971647](https://github.com/shim9610/figgy-python/actions/runs/39483971647)
used Chromium 156.0.8078.4 with SwiftShader. Its failure-time log showed seven
submitted GPU frames, six completed frames, no pending edits and no frame error.
The screenshot timed out in the element-stability wait after about 30 seconds.
The local measurements identify a GPU/frame-callback bottleneck consistent with
that failure, but are not an exact Chromium 156 reproduction: this workspace's egress policy denied
that browser's download. CI now enables the same observers and runs the last
failed radial annotation scenario in the priority gate before the full suite.
Its new result must be checked independently.

### Chromium 156 CI evidence

[Instrumented run 39532891415](https://github.com/shim9610/figgy-python/actions/runs/39532891415/job/119002780365)
at `ce0ae90` failed the priority gate with **48 passed, 1 failed**; the full
suite did not run. The radial annotation case reached its final screenshot after
its functional assertions. On Chromium 156.0.8078.4/SwiftShader, the first
960 × 600 submission completed in 32,709.8 ms; the next five took
29,335.4, 29,439.9, 29,523.5, 29,482.0 and 29,314.7 ms. Pipeline preparation
took 683.8 ms, and CPU submission took at most 0.2 ms. These are wall times to
existing completion fences, not pure shader timings.

The final screenshot started at page time 158,656.9 ms. Submission 6 completed
at 187,807.9 ms, 29,151.0 ms after capture began. The host then submitted the
resized 699 × 437 surface at 188,020.6 ms. The screenshot failed at 188,668.1 ms,
after 30,011.4 ms, in Playwright's element-stability wait. The complete recorded
geometry had remained unchanged for 30,518.2 ms. Browser animation-frame callbacks
had a maximum 32,749.8 ms gap while DOM timer sampling continued (maximum gap
515.3 ms over the whole run). At failure there were no pending edits or frame
errors, but the latest display frame had not completed.

The screenshot's stability check compares rectangles in successive animation
frames. Fixed DOM geometry alone cannot satisfy it while those callbacks are
delayed. Edit `flush()`/Python `sync()` only acknowledges edits; neither is a
promise that the current display has finished. The capture helper now waits for
the host queue, edits, dirty state, current physical canvas size and pending
display frame to settle using 100 ms DOM polling. Display errors fail immediately.
This readiness wait has a separate bounded 180-second software-rendering budget;
the original screenshot deadline remains unchanged at 30 seconds. Timing marks
report readiness time separately from screenshot time. No retry or assertion
removal is involved, and production synchronization APIs are unchanged.

The corrected exact native/browser annotation test passed locally on Chromium
154 in 135.81 seconds. Its final display-readiness wait took 12,997.1 ms, followed
by a successful 215.2 ms screenshot. The inline-text screenshot took 352.6 ms.
Observer/readiness contracts pass (9 cases); workflow/assets preflight passes
(117 cases). This local outcome does not establish the next hosted CI outcome.

Raw evidence: [CI measurements](measurements/radial-ci-39532891415.json).

## Independent renderer workload benchmark

The [standalone Rust benchmark](../scripts/bench_radial/README.md) directly uses
the published renderer's production radial pass and resident data, without
Python, WASM, a browser, UI or screenshot capture. All cases use Flat donuts,
zero depth/tilt and no shadows, outlines, labels or interaction animation.
The local native Vulkan runs used the same CPU quota, sequentially.

| Canvas / slices | Logical scene samples | Logical main-loop hit calls | SwiftShader warm pass mean | lavapipe warm pass mean |
| --- | ---: | ---: | ---: | ---: |
| 480 × 300 / 3 | 576,000 | 1,728,000 | 1,618.3 ms | 25.6 ms |
| 960 × 600 / 3 | 2,304,000 | 6,912,000 | 6,668.9 ms | 128.0 ms |
| 480 × 300 / 12 | 576,000 | 6,912,000 | 4,647.2 ms | 92.0 ms |

Times are native driver render-pass timestamps, with two warm samples per case
after one first-use draw. Clear-only passes are recorded separately. They exclude
query readback mapping and Python/browser scheduling. They include attachment
operations and software driver execution. This confirms expensive SwiftShader
radial work outside the application; it does not reconstruct Chromium/Dawn's
exact compilation and presentation path.

SwiftShader exposes timestamps but **does not expose pipeline statistics queries**
on this adapter. lavapipe exposes both: measured fragment invocations are exactly
144,000 at 480 × 300 and 576,000 at 960 × 600, and zero for clear-only passes.
Source-level work is then pixels × 4 antialiasing samples × slices for the main
hit-test loop. This is not a FLOP or machine-instruction count. Even identical
6,912,000-hit workloads have different timings at different pixel/slice ratios.
Software-driver timings differ by about 52 times in the 960 × 600 case; neither
simulates the cycles, compiler or memory system of a particular physical GPU.
Work/time measurements therefore cannot justify a TFLOPS-to-FPS conversion.

An additional SwiftShader 480 × 300 / 3-slice run with optional queries disabled
still took 1,730.7 and 1,714.0 ms for its two warm frames (wall time). The
seconds-long workload therefore also occurs without timestamp instrumentation;
these few samples do not establish a precise query overhead percentage.

Raw results: [SwiftShader](measurements/radial-independent-swiftshader-2026-10-21.jsonl),
[lavapipe](measurements/radial-independent-llvmpipe-2026-10-21.jsonl) and
[queries disabled](measurements/radial-independent-swiftshader-noqueries-2026-10-21.jsonl).

The pinned upstream [radial fragment shader](https://github.com/shim9610/figgy/blob/3a0a6a33be14f2ff4dab1475d4fcec9eafa1ee04/crates/renderer/src/radial.wgsl)
executes a scene calculation for every pixel and antialiasing sample; the
[renderer uniforms](https://github.com/shim9610/figgy/blob/3a0a6a33be14f2ff4dab1475d4fcec9eafa1ee04/crates/renderer/src/radial.rs)
request a 2 × 2 sampling grid. The scaling measurements point to this rendering
path as the performance target. A flat-chart fast path and early rejection of
background pixels are candidates for upstream profiling. GPU instruction-level
attribution and physical-GPU performance have not been measured here.

## Reproduction

Use an installed wheel matching the checkout, the repository's Jupyter test
runtime, an X11 display/window manager and the desired Chromium/SwiftShader ICD.
Keep the same browser arguments as the CI fixture. Then run:

```sh
FIGGY_TEST_TIMING=1 python -m pytest -v \
  'tests/test_interaction_parity.py::test_annotation_drawing_editing_and_cancel_in_both_hosts[radial]'
python scripts/profile_radial_gpu.py --output /tmp/figgy-radial-profile-new
```

`FIGGY_TEST_TIMING=1` adds bounded observer histories for pipeline calls, existing
queue submissions/fences, existing animation-frame callbacks, DOM timer/geometry
samples and long-task/frame entries. The screenshot wrapper records the existing
call's start, finish and original exception after explicit display readiness.
It preserves its original screenshot timeout,
adds no retries, submits no extra GPU work, and changes no renderer sources or
WASM. Observer contract tests check call counts, return values, exception identity,
frame cancellation and screenshot behavior.
