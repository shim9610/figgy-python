"""Open or export a timeline, a signal with a zoom inset and two diagrams."""

import argparse
from pathlib import Path

import numpy as np

import figgyplot as fg


def plot_timeline(ax):
    tasks = ax.range_bars(
        [0, 1, 2, 3], [0, 3, 7, 10], [3, 7, 10, 12],
        labels=["Design", "Build", "Test", "Release"],
        timeline=True,
        progress=np.array([1, 0.75, 0.25, 0], dtype=np.float32),
        remaining_opacity=0.32,
        id="tasks",
    )
    ax.range_links(tasks, [(0, 1), (1, 2), (2, 3)], id="dependencies")
    ax.set_title("Project timeline")
    ax.set_xlabel("Project day")
    ax.set_xlim(-0.5, 12.5)


def plot_signal(ax):
    time = np.linspace(0, 9, 360, dtype=np.float32)
    signal = np.exp(-time / 3) * np.cos(5 * time)
    ax.plot(time, signal, id="signal")
    ax.set_title("Damped signal")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")

    zoom = ax.inset_axes([0.53, 0.47, 0.44, 0.49], id="zoom")
    zoom.plot(time, signal, id="zoom-signal")
    return zoom


def plot_spectrum(ax):
    levels = [
        dict(id="ground", column="S", energy=0),
        dict(id="p", column="P", energy=1.9),
        dict(id="s", column="S", energy=4.1),
        dict(id="d", column="D", energy=4.5),
    ]
    energies = {level["id"]: level["energy"] for level in levels}
    transitions = [
        dict(id=f"{upper}-{lower}", lower=lower, upper=upper,
             wavelength=1239.84 / (energies[upper] - energies[lower]))
        for upper, lower in [("p", "ground"), ("s", "p"), ("d", "p")]
    ]
    diagram = ax.energy_levels(
        levels, transitions=transitions, id="spectrum",
        wavelength_labels=dict(unit="nm", decimals=1, fontsize=9),
    )
    diagram.set_wavelength_colors("nm")
    ax.set_title("Illustrative energy levels")
    ax.set_ylabel("Energy (eV)")


def plot_reaction(ax):
    vertices = [
        dict(id="electron", role="incoming", label="e⁻"),
        dict(id="positron", role="incoming", label="e⁺"),
        dict(id="annihilate", role="internal"),
        dict(id="pair", role="internal"),
        dict(id="muon", role="outgoing", label="μ⁻"),
        dict(id="antimuon", role="outgoing", label="μ⁺"),
    ]
    propagators = [
        dict(id=edge_id, source=source, target=target, particle=particle)
        for edge_id, source, target, particle in [
            ("electron-leg", "electron", "annihilate", "fermion"),
            ("positron-leg", "positron", "annihilate", "antifermion"),
            ("photon", "annihilate", "pair", "photon"),
            ("muon-leg", "pair", "muon", "fermion"),
            ("antimuon-leg", "pair", "antimuon", "antifermion"),
        ]
    ]
    diagram = ax.feynman(vertices, propagators, direction="left-to-right", id="reaction")
    diagram.propagator("photon").set_label("γ")
    ax.set_title("Electron–positron annihilation")


def make_figure(backend="native", theme="warm-paper"):
    fig = fg.Figure(
        figsize=(12, 9), dpi=110, backend=backend,
        grid=[["signal", "timeline"], ["energy", "reaction"]],
    )
    try:
        plot_timeline(fig.subplots["timeline"].axes)
        zoom = plot_signal(fig.subplots["signal"].axes)
        plot_spectrum(fig.subplots["energy"].axes)
        reaction = fig.subplots["reaction"].axes
        plot_reaction(reaction)
        zoom.set_xlim(1.0, 2.4)
        zoom.set_ylim(-0.65, 0.75)
        zoom.subplot.set_inset_marker(linewidth=0.75)
        reaction.set_xlim(-0.1, 1.1)
        reaction.set_ylim(0.25, 0.75)
        return fig.set_theme(theme).tight_layout()
    except Exception:
        fig.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/renderer-019-editing"))
    parser.add_argument("--theme", choices=fg.Figure.theme_names(), default="warm-paper")
    parser.add_argument("--formats", nargs="+", choices=["png", "svg", "pdf"], default=["png"])
    parser.add_argument("--show", action="store_true", help="Edit in a native window before saving.")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    with make_figure(theme=args.theme) as fig:
        if args.show:
            fig.show()
        for extension in args.formats:
            fig.savefig(args.output / f"renderer-019-editing.{extension}")


if __name__ == "__main__":
    main()
