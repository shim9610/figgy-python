"""Readable exports must replay actual documents, not merely parse as Python."""
import ast
import copy

import figgy
import pytest


@pytest.mark.parametrize("variable", ["fig", "restored", "ax", "text_segments"])
@pytest.mark.parametrize("dpi", [72, 120, 192])
def test_readable_setters_replay_rich_layout_and_styles(variable, dpi):
    with figgy.Figure(backend="webgpu", dpi=dpi) as source, figgy.Figure(backend="webgpu", dpi=dpi) as target:
        for figure in (source, target):
            figure.axes[0].plot([1, 10, 100], [2, 20, 200], id="signal", label="Signal")
        ax = source.axes[0]
        ax.set_title('Title "quoted"\n한글 🧪', fontsize=18, visible=False, offset=(12.5, -3))
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Amplitude", color="purple", font="DejaVu Serif")
        ax.set_xlim(.5, 150)
        ax.set_xscale("log")
        ax.legend()
        state = source.get_settings()
        state["config"]["chart_title"]["text"]["segments"][0]["bold"] = True
        state["config"]["top_x"]["max"] = 200
        state["config"]["left_y"]["label_style"]["font_size"] = 17.25
        state["series"][0]["render_type"]["Line"]["line"]["line_width"] = 4.25
        source.apply_settings(state)
        state = source.get_settings()
        target.axes[0].set_title("Unrelated", fontsize=40, color="orange")
        code = source.to_code(variable)
        ast.parse(code)
        assert ".set_title(" in code and "fontsize=18.0" in code
        assert ".set_xlabel('Time (s)'" in code and ".set_ylabel('Amplitude'" in code
        assert "json.loads" not in code and "import json" not in code
        before = copy.deepcopy(source.get_settings())
        columns = dict(target._native.columns)
        exec(code, {variable: target})
        assert target.get_settings() == state
        assert source.get_settings() == before
        assert target._native.columns == columns


def test_invalid_export_variable_and_configure_are_atomic():
    with figgy.Figure(backend="webgpu") as figure:
        figure.axes[0].plot([0, 1], [1, 0], id="signal")
        before = figure.get_settings()
        for variable in ("fig.axes[0]", "class", 1):
            with pytest.raises(ValueError, match="identifier"):
                figure.to_code(variable)
        with pytest.raises(ValueError, match="unknown series"):
            figure.configure(config={"chart_title": {"visible": False}}, series={"missing": {}})
        with pytest.raises(ValueError, match="source columns"):
            figure.configure(series={"signal": {"x_column": "other"}})
        assert figure.get_settings() == before
