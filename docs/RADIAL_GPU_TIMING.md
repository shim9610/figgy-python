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
call's start, finish and original exception. It preserves its original timeout,
adds no retries, submits no extra GPU work, and changes no renderer sources or
WASM. Observer contract tests check call counts, return values, exception identity,
frame cancellation and screenshot behavior.
