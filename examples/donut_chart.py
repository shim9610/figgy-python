"""A raised ceramic donut with rounded corners, bevel and shadow."""
import figgyplot as figgy
from _gallery import run


def make_figure():
    """Render a 3D donut; camera tilt and depth are explicit style choices."""
    fig, ax = figgy.subplots(backend="native", figsize=(8, 5), dpi=120)
    ax.donut([40, 25, 20, 15], labels=["Search", "Direct", "Email", "Other"],
             colors=["#3384f5", "#a5d848", "#ff973e", "#30c0e6"],
             inner_radius=0.5, material="ceramic", tilt=55, depth=0.16,
             inner_corner=0.045, outer_corner=0.045, bevel=0.025,
             gap_degrees=1.4, shadow=True)
    ax.set_title("Traffic sources / ceramic", fontsize=18)
    return fig


if __name__ == "__main__":
    run(make_figure, "donut-chart")
