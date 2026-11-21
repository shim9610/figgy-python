"""Measure wrapper work with a CPU notebook model; no browser or GPU timing.

Run against an installed wheel: python scripts/benchmark_wrapper_edits.py
The JSON reports warmed median latency, Python allocation peaks, and operation
counts separately. Counts are deterministic; timings are diagnostic, not gates.
"""
import copy
import json
import statistics
import time
import tracemalloc
import figgyplot as fg
from figgyplot import _document, _matplotlib

result = {}


def measure(name, operation, repetitions=9):
    operation()
    durations = []
    for _ in range(repetitions):
        t = time.perf_counter()
        operation()
        durations.append((time.perf_counter() - t) * 1000)
    tracemalloc.start()
    operation()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result[name] = {
        "median_ms": statistics.median(durations),
        "peak_python_bytes": peak,
    }


with fg.Figure(
    backend="webgpu",
    figsize=(30, 30),
    grid=[[f"p{r*5+c}" for c in range(5)] for r in range(5)],
) as fig:
    for panel in fig.subplots:
        a = fig.subplots[panel].scatter([0, 1], [1, 2], c=[1, 2], id=panel + "-data")
    bar = fig.colorbar(a, label="Value")

    def costs(name, fn):
        counts = {"snapshots": 0, "full_document_deepcopies": 0, "temporary_figures": 0}
        get = fig.get_settings
        deep = copy.deepcopy
        proxy = _matplotlib._StateFigure

        def snapshot():
            counts["snapshots"] += 1
            return get()

        def copied(value, memo=None, *args, **kwargs):
            if memo is None and isinstance(value, dict) and "schema_version" in value:
                counts["full_document_deepcopies"] += 1
            return deep(value, memo, *args, **kwargs)

        def temporary(*args, **kwargs):
            counts["temporary_figures"] += 1
            return proxy(*args, **kwargs)

        fig.get_settings = snapshot
        copy.deepcopy = copied
        _matplotlib._StateFigure = temporary
        try:
            fn()
        finally:
            fig.get_settings = get
            copy.deepcopy = deep
            _matplotlib._StateFigure = proxy
        measure(name, fn)
        result[name].update(counts)

    costs(
        "colorbar_ticks_25_panels",
        lambda: bar.ax.tick_params(labelsize=13, direction="in", length=5),
    )
    costs("colorbar_label_25_panels", lambda: bar.set_label("Value", fontsize=13))
    costs("colorbar_lookup_25_panels", lambda: fig.colorbar(a))
    costs(
        "mapped_artist_update_25_panels",
        lambda: fig.update(a.id, cmap="gray", vmin=10, vmax=20),
    )
    state = fig.get_settings()

    def stage():
        with fig.batch_update():
            fig.apply_settings(state)

    costs("batch_snapshot_25_panels", stage)
    for n in (100, 1000):
        groups = {
            str(i): {"axis": "x", "members": [str(i), str(i + 1)]}
            for i in reversed(range(n))
        }
        meta = {"groups": groups}
        measure(
            f"linked_chain_{n}", lambda: _document.tick_owners(meta, "0", "bottom_x"), 3
        )
    state = fig.get_settings()
    for n in (100, 1000):
        cfg = state["config"]
        state["identity"]["panels"] = [{"id": str(i), "overlays": []} for i in range(n)]
        cfg["subplots"] = [{"config": {"chart_area": {}}} for _ in range(n - 1)]
        state["identity"]["layout"] = {
            "grid": [[str(i) for i in range(n)]],
            "placement": {str(i): str(i) for i in range(n)},
            "row_weights": [1],
            "column_weights": [1] * n,
            "gap": 0,
            "size": [n * 100, 100],
        }
        measure(f"grid_place_{n}", lambda: _document.place_grid(state))
print(json.dumps(result, indent=2))
