"""Explicit local GPU setup: python -m figgyplot.prepare."""
import argparse
import json
from .figure import Figure

def main():
    parser = argparse.ArgumentParser(description="Prepare this machine's native GPU shaders and pipelines")
    parser.add_argument("--json", action="store_true", help="print the preparation report as JSON")
    args = parser.parse_args()
    if not args.json:
        print("Preparing local GPU shaders and pipelines…", flush=True)
    with Figure(backend="native") as figure:
        report = figure.prepare()
        report["adapter"] = figure.info["adapter"]
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"GPU ready in {report['elapsed_ms']:.0f} ms ({report['adapter']['name']})")
        if not report.get("persistent_cache_supported"):
            print("This build does not persist pipeline binaries; readiness applies to the current process.")

if __name__ == "__main__":
    main()
