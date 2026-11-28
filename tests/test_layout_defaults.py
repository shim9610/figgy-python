"""Default axis bands must leave a visible gap between Y titles and numbers."""
import json
import math

import figgyplot as figgy
import pytest


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


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_tight_layout_preserves_explicit_padding_on_a_fitted_chart(backend):
    with figgy.Figure(backend=backend, dpi=72) as figure:
        figure.axes[0].boxplot([[1, 2, 3], [2, 4, 5]])
        figure.tight_layout()
        before = figure.get_settings()["config"]
        assert before["layout_state"] == "fitted"
        figure.tight_layout(pad=1)
        after = figure.get_settings()["config"]
        for side in ("bottom_x", "top_x", "left_y", "right_y"):
            assert after[side]["out_margin"] == pytest.approx(before[side]["out_margin"] + 12)
