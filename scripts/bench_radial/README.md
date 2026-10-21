# Independent radial workload benchmark

This executable calls the published renderer 0.18.0 `RadialRenderer::prepare`
and `RadialFrame::draw` directly through native wgpu/Vulkan. It does not load
figgyplot, Python, WASM, Jupyter, a window manager or a browser. The production
shader and uniforms come from the locked registry dependency, without patches.
The fixed chart is a Flat donut with no depth, tilt, shadows, outlines, labels,
annotations or interaction animation. No changes to chart data occur between
measured frames; the prepared GPU frame remains resident.

```sh
cargo build --release --locked --manifest-path scripts/bench_radial/Cargo.toml
VK_DRIVER_FILES=/path/to/vk_swiftshader_icd.json \
  target/release/figgy-radial-bench --output /tmp/radial-swiftshader-new.jsonl
VK_DRIVER_FILES=/path/to/lvp_icd.json \
  target/release/figgy-radial-bench --output /tmp/radial-lavapipe-new.jsonl
```

Use `$CARGO_TARGET_DIR/release/figgy-radial-bench` when setting `CARGO_TARGET_DIR`.
Output files must not already exist. Each JSONL row is flushed immediately.
`--cases WIDTHxHEIGHT:SLICES,...` changes the default
`480x300:3,960x600:3,480x300:12`; `--frames N` includes one first-use draw and
N-1 warm draws per case. A clear-only pass precedes each case. Preparation and
annotation uploads finish before measured submissions. The first-use pass can
include deferred driver compilation, even after pipeline construction returns.

The environment row records the actual adapter, enabled query capabilities,
driver selector, CPU quota, timestamp period and pipeline construction time.
Frame rows separate CPU encoding, CPU submission, submission-to-completion wall
time, and pass timestamps. Query readback mapping happens after wall timing.
Pass timestamps measure the driver's render-pass interval, including attachment
operations; they are not instruction timings. On a CPU software driver these
are software execution timestamps, not physical GPU cycles. Pass boundaries
exclude query resolve/copy, which remain inside the wall-time measurement.

## Work quantities

Where supported, a pipeline statistics query measures actual fragment shader
invocations. The shader uses one fullscreen triangle and single-sample rendering;
its own antialiasing loop evaluates four scene samples per pixel. In this fixed
style, every scene sample's main sector loop calls `hit_pixel` for every slice.
The JSON records these **logical** workloads:

- pixels: width × height;
- scene samples: pixels × 4;
- main-loop sector hit calls: pixels × 4 × slices.

These counts are source-level workloads, not measured dynamic instruction counts
or FLOPs. They exclude other loops, texture loads, helper lanes and driver work.
`hit_pixel` has early returns, and the driver can optimize expressions. A single
hit call therefore does not have a fixed arithmetic cost. Flat depth-zero charts
take the direct plane-intersection path; the shader's 128-step depth raymarch
must not be included in their workload count.

Unsupported hardware counters remain `null`, never inferred from logical counts.
`--no-queries` disables both optional query features for an overhead control.
Compare otherwise identical fresh runs, and separate first-use and warm frames.
The executable fails on device, query, submission or readback errors.

## Interpreting software results

SwiftShader and lavapipe run GPU APIs on a CPU. They implement different shader
compilers, vectorization and scheduling; they do not simulate the cycles of a
particular physical GPU. Work counts and timestamps support same-environment
comparisons and help isolate scaling. They cannot be converted into a GPU's FPS
using its advertised TFLOPS. Physical performance also depends on branch
divergence, occupancy, register pressure, special functions, bandwidth and the
target compiler. Run this same Vulkan benchmark on the target adapter for a
defensible hardware measurement; this checkout has not measured a physical GPU.

Results and CI evidence: [radial measurement report](../../docs/RADIAL_GPU_TIMING.md).
