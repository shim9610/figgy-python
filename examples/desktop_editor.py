"""Run with python examples/desktop_editor.py to edit a 100,000-sample chart."""

import numpy as np
import figgy


def make_figure():
    x = np.linspace(0, 20, 100_000, dtype=np.float32)
    fig, ax = figgy.subplots(backend="native", figsize=(8, 5), dpi=200)
    ax.plot(x, 0.55 * np.cos(x), color="#1f77b4", linewidth=1.5, id="series_0")

    ax.set_title("Interactive editor / 100,000 samples", fontsize=10.00000044)
    ax.set_xlabel("Time (s)", fontsize=7.92, offset=(-664.5508, 9.5390625))
    ax.set_ylabel("Amplitude", fontsize=7.92, offset=(-3.9570312, -16.953125))
    ax.set_xlim(4.269222693348666, 17.61289720702659)
    ax.set_ylim(-0.6391470403355028, 1.5656167559239809)
    ax.legend(visible=False)

    # Keep the layout adjusted in the interactive editor.
    fig.configure(
        config={
            "top_x": {"major_spacing": 5.0},
            "bottom_x": {"major_spacing": 5.0, "out_margin": 85.50391},
            "left_y": {
                "major_spacing": 0.2,
                "label_style": {
                    "label_offset_x": 3.859375,
                    "label_offset_y": -1.9804688,
                },
                "out_margin": 148.73438,
            },
            "right_y": {"major_spacing": 0.2},
        },
    )
    return fig


if __name__ == "__main__":
    fig = make_figure()
    try:
        fig.show()  # Blocking main-thread event loop; click an object to open its properties.
    finally:
        fig.close()
