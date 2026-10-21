#!/usr/bin/env python3
"""Measure description transport cost without rendering or GPU timing claims."""
import argparse
import copy
import json
import platform
import statistics
import time
from pathlib import Path

import figgyplot as fg
from figgyplot._native import editor_catalog_json


def measure(counts=(10, 50, 200, 500), repeats=5):
    with fg.Figure(backend="webgpu", id="catalog-benchmark") as fig:
        fig.axes[0].scatter([0, 1], [1, 2], id="sample")
        base = fig.get_settings()
    rows = []
    for count in counts:
        state = copy.deepcopy(base)
        template = state["series"][0]
        state["series"] = []
        for index in range(count):
            item = copy.deepcopy(template)
            item.update(series_id=f"s{index}", x_column=f"s{index}/x", y_column=f"s{index}/y")
            state["series"].append(item)
        # These are typed description fixtures, not uploaded/rendered data.
        source = json.dumps(state, separators=(",", ":"))
        for mode, kwargs in (
            ("full", {}),
            ("compact", {"compact": True}),
            ("selected", {"object_id": "series/s0"}),
        ):
            timings = []
            for _ in range(repeats):
                start = time.perf_counter_ns()
                result = editor_catalog_json(source, **kwargs)
                timings.append((time.perf_counter_ns() - start) / 1e6)
            rows.append(dict(series=count, mode=mode, settings_bytes=len(source.encode()),
                             catalog_bytes=len(result.encode()), median_ms=round(statistics.median(timings), 3),
                             samples_ms=[round(v, 3) for v in timings]))
    return {"renderer": "0.18.1", "python":platform.python_version(), "machine":platform.machine(), "repeats":repeats,
            "scope": "typed metadata only; no GPU rendering or data uploads", "results": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    result = json.dumps(measure(repeats=args.repeats), indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")
