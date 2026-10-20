# Process-wide native GPU sharing

The first native Figure creates one process-local GPU instance, adapter, device,
queue and `figgy-renderer 0.18.0` renderer (`figgyplot 0.3.0`, model `0.12.0`).
Later Figures register independent charts in that renderer and allocate their
columns in its resident pool.
There is no renderer source copy and no change to the borrowed f32/f64 → hi/lo
upload path. Cartesian input arrays are not retained in a permanent native CPU cache.

Pies/donuts, categorical bars and boxplots share this device/queue but use their
upstream bounded renderers. Their bounded models retain category or summary
values on CPU and use no Cartesian source columns. Pies/donuts retain at most
64 slice values per group. Window previews draw to a GPU texture without
RGBA/PNG transfer; native export uses explicit readback.

Each Figure owns its document, revision, metadata, chart id, column ownership and
offscreen export target. Window views reference that document weakly. Each window
owns its own surface, axes/view, egui resources and per-frame render pass. Shared
pipelines are reusable for compatible render-target formats/sample counts;
different formats, exports and new style variants can still cause compilation.
This does not merge multiple window swapchains into one render pass.

## Data identity and ownership

Column **and series** ids are namespaced internally per Figure. This includes
matrix columns, errorbar references, mapped-style index columns and picked-data
identities. Public SSOT, `get_settings`, Copy Python and picking results keep
local ids. Stylized GPU uniforms use local series IDs for their deterministic
pattern salt, while scratch caches retain the namespaced IDs. Independent
Figures therefore replay identical stars/handwriting without sharing data.
Two Figures can both use `signal` without overwriting data or renderer
scratch-cache entries. Uploading the same NumPy array into another Figure still
creates a new column; array identity/content deduplication is not implemented.

The first Figure's `pool_bytes` sets shared initial capacity. Later values do not
create or reserve separate pools. Allocations grow the resident pool as needed,
within the adapter's **single storage-buffer binding limit**. Aggregate columns
from all Figures count toward that ceiling, even when total physical VRAM is
larger. Shared GPU memory has no automatic stream/downsample/chunk transition.

Closing a window preserves its Figure. `fig.close()` releases its export target
and collects its retired chart/columns; other Figures remain valid. Garbage
collection queues an ownership record without waiting for the GPU lock and the
next renderer operation collects it. Failed new uploads roll back their columns
without deleting another Figure's data or changing its SSOT. Live Figure data is
never automatically evicted; allocation errors retain the existing resident-mode
error reporting.

Freed column space is reusable. The shared pool's allocated capacity, pipeline
resources and bounded renderer scratch caches can remain resident: freeing slots
does not necessarily return VRAM to the driver. The context persists when all
Figures close so sequential plotting reuses initialization and pipelines.

```python
fig.close()                    # close all other native Figures as well
released = figgy.release_gpu()  # True if released, False if none was initialized
```

`release_gpu()` refuses while a native Figure or constructor retains the context.
It waits for GPU work, then drops the retained context, pool and caches. Later
construction creates a new context. It does not affect WebGPU figures. GPU
resources are process-local; use multiprocessing spawn rather than inheriting
live resources through fork. No GPU selection/per-adapter context registry is
exposed yet: all native Figures use the adapter chosen at first initialization.

## Synchronization and diagnostics

Operations acquire the Figure document mutex, then the shared renderer mutex.
Preparation, picker submission, recording, exports and device error scopes are
serialized so two Python threads cannot interleave mutable renderer state.
GPU-heavy calls release the GIL; mutex waits use PyO3's GIL-aware lock operation.
Python GC never waits for that renderer lock from a destructor.

`fig.info` exposes `gpu_context_id`, `figure_id`, `gpu_sharing="process"` and
`active_figures` so reuse and ownership are inspectable. Pool capacity/used bytes
are global; upload/readback/PNG counters and `figure_column_bytes` are per Figure.
`known_gpu_bytes` combines shared renderer resources and this Figure's export
target; do not add it across Figures as independent VRAM. Window info exposes the
same context/Figure ids. Desktop cached styles refresh when pool growth changes
its generation.

Jupyter remains a separate browser GPU domain, using an upstream `FiggyChart`
for Cartesian charts or `FiggyBoundedChart` for radial, categorical and boxplot
documents. Each view owns its browser GPU resources. Native global sharing does
not share kernel/browser memory or alter notebook binary transfers. Disk shader-cache persistence is also
separate and remains unsupported by the current renderer API.

The historical [0.2 first-frame experiment](../benchmarks/FIRST_FRAME_REUSE_RESULTS.md) measures
new Figures without explicit preparation, including upload/fit and completed
RGBA readback. It separates process-first, reset-following and shared-following
costs; constructor timing alone is not treated as first-frame performance.
Those recorded timings have not been remeasured for the 0.3 binding here.
