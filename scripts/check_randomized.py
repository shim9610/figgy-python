"""Seeded mutation/state fuzzing with process watchdogs and replayable artifacts.

No extra dependencies. Runs against the Python environment invoking this file.
Inputs are bounded (small arrays/canvases); this is not an OS/GPU OOM stress test.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import faulthandler
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import threading
import time

import numpy as np

EXPECTED = (
    ValueError,
    TypeError,
    RuntimeError,
    MemoryError,
    OverflowError,
    OSError,
    NotImplementedError,
)
EDGE = [
    None,
    False,
    True,
    -1,
    0,
    1,
    -1e300,
    1e300,
    -1e38,
    1e38,
    1e-40,
    float("nan"),
    float("inf"),
    float("-inf"),
    "",
    "typo",
    "\x00",
    "한글🦀",
]


def arbitrary(rng, depth=0):
    if depth < 2 and rng.random() < 0.3:
        if rng.random() < 0.5:
            return [arbitrary(rng, depth + 1) for _ in range(rng.randrange(5))]
        return {
            rng.choice(["x", "r", "font", "min", "unknown"]): arbitrary(rng, depth + 1)
            for _ in range(rng.randrange(4))
        }
    if rng.random() < 0.6:
        return rng.choice(EDGE)
    return rng.choice(
        [
            rng.uniform(-100, 100),
            rng.randint(-10000, 10000),
            "".join(rng.choices("ab09#-/α\x00", k=rng.randrange(20))),
        ]
    )


def array(rng):
    if rng.random() < 0.25:
        return arbitrary(rng)
    shape = tuple(rng.randrange(8) for _ in range(rng.randrange(4)))
    dtype = rng.choice(
        [
            "float32",
            "float64",
            "int64",
            "uint8",
            "complex128",
            "bool",
            "object",
            "U3",
            ">f4",
        ]
    )
    if dtype in ("object", "U3"):
        value = np.full(shape, rng.choice(["x", "", None]), dtype=dtype)
    else:
        value = np.asarray(
            np.random.default_rng(rng.getrandbits(32)).normal(size=shape), dtype=dtype
        )
    if value.size and value.dtype.kind == "f" and rng.random() < 0.3:
        value.flat[rng.randrange(value.size)] = rng.choice(
            [float("nan"), float("inf"), -1e300]
        )
    if value.ndim and rng.random() < 0.4:
        value = value[::-1]
    return value


def paths(node, prefix=()):
    yield prefix
    if isinstance(node, dict):
        for key, value in node.items():
            yield from paths(value, prefix + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from paths(value, prefix + (i,))


def mutate(state, rng):
    state = copy.deepcopy(state)
    path = rng.choice(list(paths(state)))
    value = arbitrary(rng)
    if not path:
        return value, {"path": [], "value": value}
    parent = state
    for key in path[:-1]:
        parent = parent[key]
    key = path[-1]
    kind = rng.choice(["replace", "replace", "replace", "delete", "extra"])
    if kind == "delete":
        del parent[key]
    elif kind == "extra" and isinstance(parent, dict):
        parent["fuzz_unknown_" + str(rng.randrange(100))] = value
    else:
        parent[key] = value
    return state, {"path": path, "kind": kind, "value": value}


def fresh(backend):
    import figgy

    fig, ax = figgy.subplots(backend=backend, figsize=(3, 2.5), dpi=80, pool_bytes=4096)
    x = np.arange(8, dtype=np.float32)
    ax.plot(x, x / 8, id="line", label="Line")
    ax.scatter(x, x / 16, id="points")
    ax.imshow(np.arange(16, dtype=np.float32).reshape(4, 4), id="matrix")
    ax.set_title("Fuzz chart")
    return fig, ax


def signature(fig):
    info = fig.info
    return (
        fig.get_settings(),
        fig.revision,
        info["columns"],
        fig._next_series,
        info.get("figure_column_bytes", info.get("transfer_snapshot_bytes")),
    )


def operation(fig, ax, rng):
    number = lambda: arbitrary(rng)
    sid = lambda: rng.choice(
        ["line", "points", "matrix", "chart_title", "", None, arbitrary(rng)]
    )
    color = lambda: rng.choice(
        ["red", "#123", "#12345678", [0.0, 0.5, 1.0], arbitrary(rng)]
    )
    name = rng.choice(
        [
            "plot",
            "scatter",
            "imshow",
            "update",
            "xlim",
            "ylim",
            "fit",
            "drag",
            "scale",
            "title",
            "code",
            "select",
            "settings",
            "construct",
        ]
    )
    if name == "construct":
        import figgy

        args = ()
        kw = {
            "backend": rng.choice(["native", "webgpu", "typo", number()]),
            rng.choice(["figsize", "dpi", "pool_bytes"]): number(),
        }

        def fn():
            temporary = figgy.Figure(**kw)
            temporary.close()
    elif name == "plot":
        args = (array(rng), array(rng))
        kw = {
            rng.choice(
                ["color", "linewidth", "linestyle", "marker", "id", "unknown"]
            ): rng.choice([color(), number(), sid()])
        }
        fn = lambda: ax.plot(*args, **kw)
    elif name == "scatter":
        args = (array(rng), array(rng))
        kw = {"s": number(), "color": color(), "id": sid()}
        fn = lambda: ax.scatter(*args, **kw)
    elif name == "imshow":
        args = (array(rng),)
        if rng.random() < 0.5:
            args = (np.random.default_rng(rng.getrandbits(32)).normal(size=(4, 4)),)
        kw = {
            rng.choice(
                ["id", "cmap", "vmin", "vmax", "origin", "extent", "interpolation"]
            ): number()
        }
        fn = lambda: ax.imshow(*args, **kw)
    elif name == "update":
        args = (sid(),)
        kw = {
            rng.choice(
                [
                    "font",
                    "fontsize",
                    "color",
                    "linewidth",
                    "offset",
                    "min",
                    "max",
                    "unknown",
                ]
            ): number()
        }
        fn = lambda: fig.update(*args, **kw)
    elif name in ("xlim", "ylim"):
        args = (number(), number())
        kw = {}
        fn = lambda: getattr(ax, "set_" + name)(*args)
    elif name == "fit":
        args = (number(),)
        kw = {}
        fn = lambda: fig.fit(*args)
    elif name == "drag":
        args = (sid(), number(), number())
        kw = {"handle": number()}
        fn = lambda: fig.drag(*args, **kw)
    elif name == "scale":
        args = (rng.choice(["linear", "log", number()]),)
        kw = {}
        fn = lambda: ax.set_xscale(*args)
    elif name == "title":
        args = (number(),)
        kw = {rng.choice(["font", "fontsize", "color", "offset", "unknown"]): number()}
        fn = lambda: ax.set_title(*args, **kw)
    elif name == "code":
        args = (number(),)
        kw = {}
        fn = lambda: fig.to_code(*args)
    elif name == "select":
        args = (sid(),)
        kw = {}
        fn = lambda: fig.select_object(*args)
    else:
        value, detail = mutate(fig.get_settings(), rng)
        return name, detail, lambda: fig.apply_settings(value)

    def describe(v):
        if isinstance(v, np.ndarray):
            return {"dtype": str(v.dtype), "shape": v.shape, "values": repr(v.tolist())}
        return repr(v)

    return (
        name,
        {
            "args": [describe(v) for v in args],
            "kwargs": {k: describe(v) for k, v in kw.items()},
        },
        fn,
    )


def worker(args):
    import figgy

    faulthandler.enable()
    if hasattr(signal, "SIGUSR1"):
        faulthandler.register(signal.SIGUSR1, all_threads=True)

    rng = random.Random(args.seed)
    directory = Path(args.artifacts)
    directory.mkdir(parents=True, exist_ok=True)
    log = open(directory / "trace.jsonl", "w", buffering=1)
    counts = Counter()
    failures = []

    def record(event):
        log.write(json.dumps(event, ensure_ascii=True, default=repr) + "\n")

    def fail(kind, detail):
        counts[kind] += 1
        if len(failures) < 20:
            failures.append({"kind": kind, **detail})

    fig, ax = fresh(args.backend)
    sentinel, _ = fresh(args.backend)
    sentinel_settings = signature(sentinel)
    sentinel_image = sentinel.render_rgba() if args.backend == "native" else None
    try:
        if args.phase == "ui":
            from randomized_desktop import exercise

            exercise(fig, rng, args.steps, counts, record, fail)
        elif args.phase == "concurrent":
            log_lock = threading.Lock()

            def exercise(index):
                local_rng = random.Random(args.seed * 1009 + index)
                local_counts = Counter()
                local_failures = []
                for i in range(args.steps):
                    if local_rng.random() < 0.35:
                        name = local_rng.choice(["read", "render", "temporary_figure"])
                        if name == "read":
                            fn = fig.get_settings
                        elif name == "render":
                            fn = (
                                fig.render_rgba
                                if args.backend == "native"
                                else fig.get_settings
                            )
                        else:

                            def fn():
                                temporary, _ = fresh(args.backend)
                                temporary.close()

                        detail = {}
                    else:
                        name, detail, fn = operation(fig, ax, local_rng)
                    event = {
                        "thread": index,
                        "index": i,
                        "operation": name,
                        "input": detail,
                    }
                    with log_lock:
                        record({"stage": "call", **event})
                    try:
                        fn()
                        local_counts["accepted"] += 1
                    except EXPECTED as e:
                        local_counts[type(e).__name__] += 1
                        if not str(e):
                            local_failures.append({"kind": "empty_error", **event})
                    except BaseException as e:
                        local_failures.append(
                            {
                                "kind": "unexpected_exception",
                                **event,
                                "exception": str(e),
                                "type": type(e).__name__,
                            }
                        )
                    with log_lock:
                        record({"stage": "returned", **event})
                return local_counts, local_failures

            with ThreadPoolExecutor(max_workers=4) as pool:
                for local_counts, local_failures in pool.map(exercise, range(4)):
                    counts.update(local_counts)
                    for failure in local_failures:
                        fail(failure["kind"], failure)
            counts["threads_joined"] = 4
        else:
            sequential(args, rng, fig, ax, counts, fail, record)
        assert signature(sentinel) == sentinel_settings
        if sentinel_image is not None:
            assert np.array_equal(sentinel_image, sentinel.render_rgba())
        counts["sentinel_unchanged"] += 1
    except BaseException as e:
        fail("fatal", {"type": type(e).__name__, "exception": str(e)})
        record({"stage": "fatal", "type": type(e).__name__, "error": str(e)})
    finally:
        fig.close()
        sentinel.close()
        if args.backend == "native":
            figgy.release_gpu()
        result = {
            "seed": args.seed,
            "phase": args.phase,
            "backend": args.backend,
            "counts": dict(counts),
            "failures": failures,
        }
        (directory / "result.json").write_text(
            json.dumps(result, indent=2, default=repr)
        )
        log.close()
    return 1 if failures else 0


def sequential(args, rng, fig, ax, counts, fail, record):
    try:
        for i in range(args.steps):
            if args.phase == "api" and rng.random() < 0.04:
                fig.close()
                record({"stage": "closed_call", "index": i})
                fn = rng.choice(
                    [
                        fig.get_settings,
                        lambda: fig.update("chart_title", text="closed"),
                        lambda: ax.plot([1, 2]),
                        fig.fit,
                        lambda: fig.show(block=False),
                    ]
                )
                try:
                    fn()
                    fail("closed_figure_accepted", {"index": i})
                except RuntimeError as e:
                    if "closed" not in str(e):
                        fail("poor_closed_error", {"index": i, "exception": str(e)})
                    counts["RuntimeError"] += 1
                fig, ax = fresh(args.backend)
                counts["closed_cycles"] += 1
                continue
            before = signature(fig)
            if args.phase == "settings":
                value, detail = mutate(before[0], rng)
                name = "apply_settings"
                fn = lambda: fig.apply_settings(value)
            else:
                name, detail, fn = operation(fig, ax, rng)
            event = {"index": i, "operation": name, "input": detail}
            record({"stage": "call", **event})
            try:
                fn()
                counts["accepted"] += 1
            except EXPECTED as e:
                counts[type(e).__name__] += 1
                if not str(e):
                    fail("empty_error", event)
                after = signature(fig)
                if after != before:
                    fail(
                        "non_atomic_rejection",
                        {
                            **event,
                            "exception": str(e),
                            "before": before,
                            "after": after,
                        },
                    )
                    fig.close()
                    fig, ax = fresh(args.backend)
                record(
                    {
                        "stage": "rejected",
                        "error": type(e).__name__ + ": " + str(e),
                        **event,
                    }
                )
                continue
            except BaseException as e:
                fail(
                    "unexpected_exception",
                    {**event, "type": type(e).__name__, "exception": str(e)},
                )
                record(
                    {
                        "stage": "unexpected",
                        **event,
                        "type": type(e).__name__,
                        "error": str(e),
                    }
                )
                if type(e).__name__ == "PanicException":
                    break
                continue
            record({"stage": "accepted", **event})
            # Every accepted document must remain replayable; f32 overflow must
            # never silently serialize a required number as JSON null.
            fig.apply_settings(fig.get_settings())
            # Verify a successful edit can be consumed, not merely serialized.
            if args.backend == "native" and rng.random() < 0.1:
                cfg = fig.get_settings()["config"]["chart_area"]
                rect = cfg if isinstance(cfg, dict) else cfg[0]
                if rect["width"] <= 512 and rect["height"] <= 512:
                    record({"stage": "render", **event})
                    fig.render_rgba()
                    counts["renders"] += 1
            if args.phase == "settings":
                fig.apply_settings(before[0])
            elif i % 50 == 49:
                fig.close()
                fig, ax = fresh(args.backend)
                counts["recreated"] += 1
        # A known valid operation must still work after random rejection chains.
        record({"stage": "recovery"})
        fig.close()
        fig, ax = fresh(args.backend)
        if args.backend == "native":
            fig.render_rgba()
            counts["renders"] += 1
        counts["recovery"] += 1
    finally:
        fig.close()


def run_one(args, seed, backend, phase):
    directory = Path(args.artifacts) / f"{backend}-{phase}-{seed}"
    directory.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        __file__,
        "--worker",
        "--seed",
        str(seed),
        "--backend",
        backend,
        "--phase",
        phase,
        "--steps",
        str(args.steps),
        "--artifacts",
        str(directory),
    ]
    start = time.monotonic()
    with (
        open(directory / "stdout.log", "w") as out,
        open(directory / "stderr.log", "w") as err,
    ):
        process = subprocess.Popen(
            command,
            stdout=out,
            stderr=err,
            env=dict(os.environ, LP_NUM_THREADS="2"),
            cwd=directory.resolve(),
        )
        try:
            code = process.wait(timeout=args.timeout)
            status = "completed" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            if hasattr(signal, "SIGUSR1"):
                process.send_signal(signal.SIGUSR1)
                time.sleep(0.1)
            process.kill()
            process.wait()
            code = process.returncode
            status = "timeout"
    result_path = directory / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    result.update(
        seed=seed,
        backend=backend,
        phase=phase,
        status=status,
        exit_code=code,
        elapsed_seconds=round(time.monotonic() - start, 3),
        artifacts=str(directory),
    )
    if status != "completed":
        trace = directory / "trace.jsonl"
        result["last_events"] = (
            trace.read_text().splitlines()[-3:] if trace.exists() else []
        )
        result["stderr_tail"] = (directory / "stderr.log").read_text()[-3000:]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--seeds", type=int, default=8)
    p.add_argument("--steps", type=int, default=500)
    p.add_argument("--backend", choices=["native", "webgpu", "both"], default="both")
    p.add_argument(
        "--phase",
        choices=["api", "settings", "concurrent", "ui", "both"],
        default="both",
    )
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--artifacts", default="randomized-results")
    p.add_argument("--report")
    args = p.parse_args()
    args.artifacts = str(Path(args.artifacts).resolve())
    if args.phase == "ui":
        if args.backend != "native":
            p.error("UI fuzzing requires --backend native")
        args.workers = 1
    if args.worker:
        return worker(args)
    backends = ["native", "webgpu"] if args.backend == "both" else [args.backend]
    phases = ["api", "settings", "concurrent"] if args.phase == "both" else [args.phase]
    tasks = [
        (s, b, k)
        for s in range(args.seed, args.seed + args.seeds)
        for b in backends
        for k in phases
    ]
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_one, args, *task) for task in tasks]
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            print(
                json.dumps(
                    {
                        k: r[k]
                        for k in ("seed", "backend", "phase", "status", "counts")
                        if k in r
                    }
                ),
                flush=True,
            )
    counts = Counter()
    for r in results:
        counts.update(r.get("counts", {}))
    report = {
        "steps_per_worker": args.steps,
        "watchdog_seconds": args.timeout,
        "counts": dict(counts),
        "workers": results,
        "passed": all(r["status"] == "completed" for r in results),
    }
    path = Path(args.report or str(Path(args.artifacts) / "summary.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
