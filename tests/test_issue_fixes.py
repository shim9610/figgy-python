"""Regressions for reported issues and the renderer features behind their fixes."""
import re
import warnings
from pathlib import Path

import numpy as np
import pytest

import figgyplot as figgy
from figgyplot.figure import _color, _segments


@pytest.fixture
def plot():
    fig, ax = figgy.subplots(figsize=(6, 4), dpi=100, pool_bytes=8 * 1024**2)
    yield fig, ax
    fig.close()


def _bar_series(ax):
    bar = {"fill_color": _color("#336699"), "border_color": _color("#ffffff"),
           "border_width": 0.0, "baseline": 0.0, "gap_px": 2.0,
           "width_ratio": 1.0, "orientation": "Vertical"}
    # No public bar API yet; the bar branch of update() is still supported.
    return ax._add(np.arange(4.0), np.array([1.0, 2.0, 3.0]), {"Histogram": {"bar": bar}}, id="h")


def test_package_version_has_one_source():
    cargo = (Path(__file__).parents[1] / "Cargo.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', cargo, re.MULTILINE).group(1)
    assert figgy.__version__ == version


def test_multiple_panels_error_names_the_running_version():
    with pytest.raises(NotImplementedError, match=re.escape(f"figgyplot {figgy.__version__}")):
        figgy.subplots(1, 2, backend="native")


def test_bar_series_recolour_and_code_export(plot):
    fig, ax = plot
    _bar_series(ax)
    fig.update("h", color="#ff0000")
    bar = fig.get_settings()["series"][0]["render_type"]["Histogram"]["bar"]
    assert bar["fill_color"] == _color("#ff0000")
    assert "fig.update('h', color=" in fig.to_code()


def test_sketch_rejects_series_it_cannot_draw(plot):
    fig, ax = plot
    ax.imshow(np.random.default_rng(1).random((4, 4)), id="z")
    with pytest.raises(ValueError, match="Sketch"):
        fig.set_draw_style("sketch")
    assert "draw_style" not in fig.get_settings()["config"]

    other, other_ax = figgy.subplots(figsize=(6, 4), dpi=100)
    try:
        other_ax.plot(np.arange(5.0), np.arange(5.0))
        other.set_draw_style("sketch")
        with pytest.raises(ValueError, match="Sketch"):
            _bar_series(other_ax)
        assert len(other.get_settings()["series"]) == 1
    finally:
        other.close()


def test_unknown_font_family_is_rejected(plot):
    fig, ax = plot
    ax.plot(np.arange(3.0), np.arange(3.0))
    with pytest.raises(ValueError, match="Definitely Not A Font"):
        fig.update("chart_title", text="Title", font="Definitely Not A Font")
    assert fig.get_settings()["config"]["chart_title"]["text"]["font"] == ""
    fig.update("chart_title", font="Liberation Sans")
    fig.update("chart_title", font="")


def test_unicode_superscripts_use_the_renderer_mapping(plot):
    fig, ax = plot
    segments = _segments("10⁻³")
    assert [s["text"] for s in segments] == ["1", "0", "-", "3"]
    assert [s["superscript"] for s in segments] == [False, False, True, True]
    assert figgy.text_segments("10⁻³") == segments

    ax.plot(np.arange(3.0), np.arange(3.0))
    fig.update("chart_title", text="CO₂ 10⁻³")
    title = fig.get_settings()["config"]["chart_title"]["text"]["segments"]
    assert [s["subscript"] for s in title][2] is True
    # Code export writes the original text back, not raw segment dicts.
    assert "ax.set_title('CO₂ 10⁻³'" in fig.to_code()


def test_multi_line_title_grows_its_band_and_single_lines_keep_it(plot):
    fig, ax = plot
    ax.plot(np.arange(10.0), np.arange(10.0))
    band = fig.get_settings()["config"]["chart_title"]["top_margin"]
    for title in ("Title", "Tgy", "Response / Run 01"):
        fig.update("chart_title", text=title)
        assert fig.get_settings()["config"]["chart_title"]["top_margin"] == band

    fig.update("chart_title", text="Line one of title\nLine two of title\nLine three")
    grown = fig.get_settings()["config"]["chart_title"]["top_margin"]
    assert grown > band
    # Nothing of the title is cut off at the canvas top.
    assert not fig.render_rgba()[0, :, :3].min() < 128

    # Settings applied directly keep the margin they give.
    state = fig.get_settings()
    state["config"]["chart_title"]["top_margin"] = band
    fig.apply_settings(state)
    assert fig.get_settings()["config"]["chart_title"]["top_margin"] == band


def test_title_alignment_is_editable_and_exported(plot):
    fig, ax = plot
    ax.plot(np.arange(3.0), np.arange(3.0))
    fig.update("chart_title", text="A wide first line\nab", align="center")
    assert fig.get_settings()["config"]["chart_title"]["text"]["align"] == "Center"
    assert "align='center'" in fig.to_code()
    with pytest.raises(ValueError, match="align"):
        fig.update("chart_title", align="middle")


def test_set_xlim_without_tick_auto_keeps_configured_ticks(plot):
    fig, ax = plot
    ax.plot(np.arange(100.0), np.arange(100.0))
    fig.configure(config={"bottom_x": {"major_spacing": 25.0, "minor_count": 1}})
    ax.set_xlim_without_tick_auto(0, 100)
    config = fig.get_settings()["config"]
    for key in ("bottom_x", "top_x"):
        axis = config[key]
        assert (axis["min"], axis["max"], axis["range_locked"]) == (0.0, 100.0, True)
    assert (config["bottom_x"]["major_spacing"], config["bottom_x"]["minor_count"]) == (25.0, 1)

    # set_xlim derives readable ticks for the new range, by design.
    ax.set_xlim(0, 100)
    assert fig.get_settings()["config"]["bottom_x"]["major_spacing"] == 20.0


def test_a_fixed_range_survives_adding_a_series_until_an_explicit_fit(plot):
    fig, ax = plot
    ax.plot(np.arange(100.0), np.arange(100.0))
    ax.set_xlim_without_tick_auto(10, 50)
    ax.plot(np.arange(300.0), np.arange(300.0))
    x = fig.get_settings()["config"]["bottom_x"]
    assert (x["min"], x["max"]) == (10.0, 50.0)
    # The y range was not fixed, so it fits the new data.
    assert fig.get_settings()["config"]["left_y"]["max"] >= 299.0

    fig.fit()
    config = fig.get_settings()["config"]
    assert config["bottom_x"]["max"] >= 299.0
    assert not any(config[k]["range_locked"] for k in ("bottom_x", "top_x", "left_y", "right_y"))


def test_tick_substitution_warns_once_per_change(plot):
    fig, ax = plot
    ax.plot(np.arange(100.0), np.arange(100.0))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.render_rgba()
    assert not [w for w in caught if issubclass(w.category, figgy.RenderWarning)]

    fig.configure(config={"bottom_x": {"major_spacing": 1e-6}})
    with pytest.warns(figgy.RenderWarning, match="bottom_x"):
        fig.render_rgba()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.render_rgba()
    assert not [w for w in caught if issubclass(w.category, figgy.RenderWarning)], "reported once"
