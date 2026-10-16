# Explicit GPU preparation

The wrapper exposes `Figure.prepare()` for native rendering and
`await Figure.prepare_async(timeout=180)` for a mounted WebGPU widget. Both call
the public upstream renderer APIs: Cartesian pipeline prewarming or bounded-chart
first-frame preparation. This repository contains no shader engine or renderer
source copy.

## Native

Construct the Figure, register the actual series, then call `prepare()` before
timing/drawing. For Cartesian charts it calls `Renderer.prewarm_all_observed`
and waits for submitted GPU work. Pie/donut, categorical and boxplot charts
prepare their own bounded renderer through the current document render. Both
paths complete one RGBA render of the current document. The call releases the GIL,
reuses resident columns, preserves settings/revision, and does not encode PNG.
Allocation/validation errors propagate as Python exceptions. The completed
readback is temporary, not a retained CPU copy of the original arrays.

The report contains `backend`, `ready`, `elapsed_ms`, `target_format`, observed
`stages` and `persistent_cache_supported`. Native `fig.info["preparation"]` holds
the latest successful report. Elapsed time measures this call, excluding Figure
construction and source upload, which may already initialize base pipelines.

Preparation covers resident Cartesian pipeline groups, contour-label compute,
arc scans, fit and GPU picking. It excludes streaming/nonresident engines. The
current document render prepares its own views/styles/atlases. It uses
`Rgba8Unorm`; desktop swapchains can have another format and recompile target
pipelines. Egui is initialized by the window host. New style variants, target
formats/sample counts, and driver work on first use can still cause delays.
`ready=True` means this operation completed, not a promise of zero future work.
Native Figures share one process-local renderer, so installed pipeline groups
also benefit subsequently created Figures. Per-Figure views/styles and target
formats can still require work. `fig.close()` retains that context for reuse;
`figgy.release_gpu()` explicitly releases it after all native Figures close.

## Jupyter

```python
fig, ax = figgy.subplots(backend="webgpu")
ax.plot(x, y)
display(fig.widget(auto_prepare=False))
report = await fig.prepare_async()
```

The manual widget shows a preparation status and disables editing controls until
ready. It requests no adapter and creates no browser GPU resources before the
explicit command. Initial binary buffer/asset transfer to the frontend can still
occur. The kernel remains GPU-free. Python settings changes while preparation is
deferred are applied when it starts.

`prepare_async()` waits for a mounted frontend, initializes WASM/WebGPU, uploads
the binary columns, uses `FiggyChart.prewarm_all_with_progress` for Cartesian
charts and awaits `first_frame_ready`. Radial, categorical and boxplot charts
compile their pipelines asynchronously and also await the first GPU frame.
Ready therefore requires GPU completion; preparation failures remain visible
in the status and propagate to Python. The browser shows upstream stage progress.
Preparation, menu access and redraw/picking/export operations are serialized to
protect the WASM chart.
`elapsed_ms` covers the browser request, including initialization/upload when
deferred; `prewarm_ms` separately measures prewarm plus first-frame readiness.
Kernel/comm scheduling and outbound transfer before the request are not included.
No PNG export is involved, and subsequent preparations reuse resident columns.

Default `display(fig)` still initializes automatically; explicit preparation then
warms additional resident groups. All requests require a connected frontend. A
missing frontend times out; initialization failure propagates its WebGPU error.
Closing a widget interrupts pending requests and disposes its GPU chart. The
existing temporary snapshot release/retain policy remains in effect.

## Packaging and persistence boundary

The wheel includes the CLI and preparation API. `python -m figgyplot.prepare --json`
performs a native smoke/prewarm operation and prints adapter/stage/timing data.
Its Figure is closed on exit; it is a diagnostic command, not a reliable cache
producer for later processes. There is no GPU installation hook.

**Persistent pipeline cache save/restore is not implemented.** All current reports
set `persistent_cache_supported=False`. Renderer 0.17.0's public construction
path provides no cache injection; its pipeline descriptors use `cache: None`.
Creating an unrelated wgpu cache in the wrapper would not cache those pipelines.

An upstream public API must attach an actual cache before renderer pipeline
creation for wrapper-managed disk persistence to work. wgpu 30 exposes persistent
pipeline caching for Vulkan. DX12, Metal and browser WebGPU do not expose that
same portable disk-cache path; any automatic driver/browser caches remain under
their control. A future supported path must validate GPU/driver/wgpu/renderer
identity, safely handle stale/corrupt caches, and report a real restored/missed
cache separately from successful process-local prewarming.

Ordinary pip wheel installation copies prebuilt Rust/WASM code. GPU shader machine
code is created on the target device at runtime, not embedded as a universal
installation-time artifact. CPU-only/remote-kernel installation must keep working.
