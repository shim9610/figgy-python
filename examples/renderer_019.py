"""Render four chart families with every built-in theme and document export."""

import argparse
from pathlib import Path
import numpy as np
import figgyplot as fg


def draw(theme, output, formats=("png",)):
    with fg.Figure(
        figsize=(11, 8),
        dpi=100,
        backend="native",
        grid=[["stem", "violin"], ["intervals", "image"]],
    ) as fig:
        ax = fig.subplots["stem"].axes
        x = np.arange(9, dtype=np.float32)
        ax.stem(x, np.sin(x * 0.6) + 1.5, label="Observations")
        ax.set_title("Stem")
        ax.set_xlabel("Sample")
        ax.set_ylabel("Value")
        ax = fig.subplots["violin"].axes
        rng = np.random.default_rng(42)
        ax.violinplot(
            [rng.normal(mean, 0.5, 240).astype(np.float32) for mean in (1, 2, 1.5)],
            showmedians=True,
        )
        ax.set_title("Violin")
        ax.set_ylabel("Distribution")
        ax = fig.subplots["intervals"].axes
        ax.waterfall(
            ["Start", "Growth", "Cost", "Recovery"],
            np.array([4, 3, -2, 1], dtype=np.float32),
            connector_color="#8b7768",
            connector_width=1.25,
        )
        ax.set_title("Waterfall")
        ax.set_ylabel("Balance")
        ax = fig.subplots["image"].axes
        y, x = np.mgrid[0:1:48j, 0:1:64j]
        image = np.stack([x, y, 1 - x], axis=-1).astype(np.float32)
        ax.imshow(image, origin="lower")
        ax.set_title("RGB image")
        fig.set_theme(theme).tight_layout()
        for format in formats:
            fig.savefig(output / ("renderer-019-" + theme + "." + format))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("renderer-019-gallery"))
    parser.add_argument(
        "--formats", nargs="+", choices=["png", "svg", "pdf"], default=["png"]
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for theme in fg.Figure.theme_names():
        draw(theme, args.output, args.formats)


if __name__ == "__main__":
    main()
