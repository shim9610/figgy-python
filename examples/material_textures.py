"""Procedural material recipes: paper, wood, hatch and pearl."""
import argparse
from pathlib import Path
import figgyplot as figgy

MATERIALS = ("paper", "wood", "hatch", "pearl")


def make_figure(material="wood"):
    """Generate a textured donut using actual upstream procedural materials."""
    fig, ax = figgy.subplots(backend="native", figsize=(8, 5), dpi=120)
    ax.donut([40, 25, 20, 15], labels=["Search", "Direct", "Email", "Other"],
             colors=["#cf9e5e", "#719d94", "#8c4593", "#6b8eb6"],
             material=material, tilt=55, depth=0.16, shadow=True,
             inner_corner=0.045, outer_corner=0.045, gap_degrees=1.4,
             texture_strength=0.8, texture_scale=1.5,
             roughness=0.85 if material == "wood" else 0.35,
             gloss=0.1 if material == "wood" else 0.55)
    ax.set_title(f"Procedural material / {material}", fontsize=18)
    return fig


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material", choices=MATERIALS, default="wood")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    path = args.output or Path(f"output/gallery/material-{args.material}.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    with make_figure(args.material) as figure:
        if args.show:
            figure.show()
        figure.savefig(path)
    print(path)
