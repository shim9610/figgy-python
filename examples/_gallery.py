"""Shared command-line handling for the standalone gallery examples."""
import argparse
from pathlib import Path

import figgyplot as figgy


def chart(title, xlabel, ylabel):
    fig, ax = figgy.subplots(backend="native", figsize=(8, 5), dpi=120)
    ax.set_title(title, fontsize=18)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    return fig, ax


def dark_theme(fig):
    """Use explicit dark chrome so star styles remain readable."""
    fig.set_facecolor("#0b0f17")
    for side in ("bottom", "top", "left", "right"):
        fig.update(f"axis_{side}", color="#c6cfdf")
        fig.update(f"tick_labels_{side}", color="#c6cfdf")
        fig.update(f"axis_title_{side}", color="#c6cfdf")
    fig.update("chart_title", color="#eef1f8")
    fig.update("legend", color="#eef1f8")
    fig.configure(config={"legend": {
        "bg_color": dict(zip("rgba", (11/255, 15/255, 23/255, 1))),
        "border_color": dict(zip("rgba", (198/255, 207/255, 223/255, 1))),
    }})


def run(make_figure, name):
    parser = argparse.ArgumentParser(description=make_figure.__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/gallery") / f"{name}.png")
    parser.add_argument("--show", action="store_true", help="Edit in a native window before saving")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with make_figure() as fig:
        if args.show:
            fig.show()
        fig.savefig(args.output)
    print(args.output)
