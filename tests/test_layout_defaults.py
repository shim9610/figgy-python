"""Default axis bands must leave a visible gap between Y titles and numbers."""
import json
import math

import figgy


def test_default_title_tick_separation_and_native_notebook_layout_match():
    with figgy.Figure(backend="native") as native, figgy.Figure(backend="webgpu") as notebook:
        for figure in (native, notebook):
            ax = figure.axes[0]
            ax.plot([0, 1, 2], [0, 1, 2], id="signal")
            ax.set_ylabel("Amplitude", fontsize=11)
            ax.set_xlabel("Time (s)", fontsize=11)
            ax.set_xlim(0, 2)
            ax.set_ylim(-0.15, 2.5)
        assert native.get_settings()["config"] == notebook.get_settings()["config"]
        title = json.loads(native._native.bounds_json("axis_title_left"))["rect"]
        data = json.loads(native._native.bounds_json("data_area"))["rect"]
        image = native.render_rgba()
        band = image[int(data[1])+10:int(data[1]+data[3])-10, :int(data[0]), :3]
        ink_columns = (band.max(axis=2) < 80).any(axis=0)
        separator = math.ceil(title[0] + title[2])
        # A clear vertical separator follows the title; numeric tick glyphs
        # must still exist to its right. The previous compact margins overlap.
        assert not ink_columns[separator:separator+4].any()
        assert ink_columns[separator+4:int(data[0])-8].any()
