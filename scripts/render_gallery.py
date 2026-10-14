"""Reproduce the README gallery using the installed native Figgy renderer."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
RECIPES = ["line_signals", "scatter_clusters", "parametric_curves", "log_scales",
           "line_markers", "heatmap_field", "correlation_matrix", "spectrogram",
           "pie_chart", "donut_chart", "sketch_style", "constellation_style", "milkyway_style"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/images/gallery")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    cases = [(name, name.replace('_', '-'), {}) for name in RECIPES]
    cases += [("material_textures", f"material-{material}", {"material": material})
              for material in ("paper", "wood", "hatch", "pearl")]
    for name, image_name, options in cases:
        recipe = importlib.import_module(name)
        image = args.output / f"{image_name}.png"
        with recipe.make_figure(**options) as fig:
            fig.savefig(image)
            area = fig.get_settings()["config"]["chart_area"]
            records.append({"source": f"examples/{name}.py", "image": image.name,
                            "canvas": [area["width"], area["height"]],
                            "adapter": fig.info["adapter"],
                            "parameters": options,
                            "sha256": hashlib.sha256(image.read_bytes()).hexdigest()})
        print(image)
    (args.output / "manifest.json").write_text(json.dumps({
        "data": "Synthetic; fixed seed 9610 where randomness is used",
        "rendering": "Native figgy-renderer output; no chart-image compositing",
        "recipes": records,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
