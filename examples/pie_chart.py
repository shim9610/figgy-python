"""A native pie with outside labels and an individually exploded slice."""
import figgy
from _gallery import run


def make_figure():
    """Render a bounded categorical pie with the upstream radial renderer."""
    fig, ax = figgy.subplots(backend="native", figsize=(8, 5), dpi=120)
    ax.pie([40, 25, 20, 15], labels=["Search", "Direct", "Email", "Other"],
           colors=["#3384f5", "#a5d848", "#ff973e", "#30c0e6"],
           explode=[0.04, 0, 0, 0], material="matte", gap_degrees=1.4)
    ax.set_title("Traffic sources", fontsize=18)
    return fig


if __name__ == "__main__":
    run(make_figure, "pie-chart")
