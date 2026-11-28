"""Regression evidence for migrated editing, numerical labels and page units."""

import copy
from io import BytesIO
from xml.etree import ElementTree

import numpy as np
import pytest
from pypdf import PdfReader
import figgyplot as fg


def body(fig):
    return next(iter(fig.get_settings()["series"][0]["render_type"].values()))


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("kind", ["bar", "box", "radar"])
def test_common_chart_editing_retains_resident_sources(backend, kind):
    with fg.Figure(backend=backend, dpi=96) as fig:
        ax = fig.axes[0]
        if kind == "bar":
            ax.bar(["A", "B"], np.array([2.25, 3.75], dtype=np.float32))
        elif kind == "box":
            ax.boxplot([[1, 2, 4], [2, 4, 6]])
        else:
            ax.radar(["A", "B", "C"], [2, 3, 4])
        initial = fig.get_settings()
        uploads = fig.info.get("column_uploads", fig.info["columns"])
        sid = next(iter(ax.chart.get_series()))
        cid = next(iter(ax.chart.get_categories()))
        ax.chart.series(sid).set_label("Edited").set_color("red")
        if kind == "radar":
            ax.chart.series(sid).set_style(
                linewidth=2, facecolor="#00ff0080", marker="s"
            )
            ax.chart.decoration("spoke_label", category=cid).set_offset((2, 3))
            assert fig.get_settings()["config"]["bottom_x"]["categories"][0][
                "label_offset"
            ] == pytest.approx([8 / 3, 4])
        else:
            cell = ax.chart.cell(cid, sid)
            cell.set_color("green").set_style(linewidth=2, outline=True)
            cell.set_value_labels(
                position="outside" if kind == "bar" else "median_and_count"
            )
            assert len(body(fig)["overrides"]) == 1
            assert cell.get_style()["linewidth"] == pytest.approx(2)
            cell.reset_style()
            assert cell.get_style() is None
            ax.chart.decoration("value_label", category=cid, series=sid).set_offset(
                (2, 3)
            )
            assert body(fig)["labels"]["offsets"][0] == pytest.approx([8 / 3, 4])
        ax.chart.decoration("title").set_offset((3, 4))
        assert fig.get_settings()["config"]["chart_title"]["offset_x"] == 4
        ax.chart.decoration("ticklabels", side="bottom").set_offset((1, 2))
        ax.chart.set_plot_bounds((70, 45, 300, 200))
        ax.chart.set_plot_bounds()
        ax.text(0.4, 0.4, "Note", coords="ratio", id="note")
        original = fig.get_settings()["config"]["annotations"]["items"][0]["kind"][
            "Text"
        ]["anchor"]["Ratio"]
        decoration = ax.chart.decoration("annotation", index=0)
        decoration.set_offset((2, 3))
        moved = fig.get_settings()["config"]["annotations"]["items"][0]["kind"]["Text"][
            "anchor"
        ]["Ratio"]
        assert moved["x"] > original["x"] and moved["y"] > original["y"]
        decoration.remove()
        assert fig.get_settings()["config"]["annotations"]["items"][0]["kind"]["Text"][
            "anchor"
        ]["Ratio"] == pytest.approx(original)
        data = ax.chart.decoration("data")
        data.set_offset((2, 3))
        data.remove()
        after = fig.get_settings()
        assert after["identity"] == initial["identity"]
        assert [
            (s["series_id"], s["x_column"], s["y_column"]) for s in after["series"]
        ] == [(s["series_id"], s["x_column"], s["y_column"]) for s in initial["series"]]
        assert fig.info.get("column_uploads", fig.info["columns"]) == uploads
        checkpoint = copy.deepcopy(after)
        with pytest.raises(AttributeError if kind == "radar" else ValueError):
            ax.chart.cell("missing", sid)
        assert fig.get_settings() == checkpoint
        if backend == "native":
            assert fig.render_rgba().size > 0


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_value_formats_follow_values_and_cell_overrides(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.bar(["A", "B"], [[2.25, 6.75], [6.75, 2.25]])
        assert body(fig)["labels"]["text"] == ["2.2", "6.8"]
        uploads = fig.info.get("column_uploads", fig.info["columns"])
        ax.chart.set_value_labels(position="outside", format="percent", decimals=2)
        assert body(fig)["labels"]["text"] == ["25%", "75%"]
        sid = next(iter(ax.chart.get_series()))
        cid = next(iter(ax.chart.get_categories()))
        ax.chart.cell(cid, sid).set_value_labels(format="category_value")
        assert "A" in body(fig)["labels"]["text"][0]
        ax.chart.clear_overrides()
        ax.chart.set_value_labels(format="value", suffix=" eV")
        assert body(fig)["labels"]["text"] == ["2.25 eV", "6.75 eV"]
        labels = copy.deepcopy(body(fig)["labels"])
        ax.chart.set_style(edgecolor="red")
        ax.set_xlim(0, 4)
        assert body(fig)["labels"] == labels
        assert fig.info.get("column_uploads", fig.info["columns"]) == uploads
        before = fig.get_settings()
        for value in (True, -1, 7, 1.5):
            with pytest.raises(ValueError):
                ax.chart.set_value_labels(decimals=value)
            assert fig.get_settings() == before


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_box_and_radar_labels_read_statistics(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.boxplot([[1, 2, 4], [2, 4, 6, 8]])
        ax.chart.set_value_labels(position="median_and_count", decimals=2, suffix=" u")
        labels = body(fig)["labels"]["text"]
        assert labels[0] == "2.00 u (n=3)"
        assert labels[1] == "5.00 u (n=4)"
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.radar(["A", "B", "C"], [1.25, 2.5, 3.75])
        ax.chart.set_value_labels(position="values", decimals=2, suffix=" u")
        assert body(fig)["labels"]["text"] == ["1.25 u", "2.50 u", "3.75 u"]


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("kind", ["bar", "box"])
def test_orientation_swaps_existing_sources_without_uploads(backend, kind):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        if kind == "bar":
            ax.bar(["A", "B"], [2, 4])
        else:
            ax.boxplot([[1, 2, 4], [2, 3, 5]])
        before = fig.get_settings()
        uploads = fig.info.get("column_uploads", fig.info["columns"])
        ax.chart.set_orientation("horizontal")
        assert (
            fig.get_settings()["config"]["left_y"]["categories"]
            == before["config"]["bottom_x"]["categories"]
        )
        if backend == "native":
            fig.render_rgba()
        ax.chart.set_orientation("vertical")
        assert fig.get_settings()["series"] == before["series"]
        assert fig.info.get("column_uploads", fig.info["columns"]) == uploads


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("preset", fg.styles.available())
def test_family_preset_fields_and_extracted_styles_are_applied(backend, preset):
    with fg.Figure(backend=backend, style=preset, dpi=72) as fig:
        ax = fig.axes[0]
        ax.bar(["A", "B"], [2, 4])
        token = fg.styles.preset(preset)
        patch = (
            token.appearance.get("bounded", {}).get("categorical", {}).get("style", {})
        )
        for key, value in patch.items():
            assert body(fig)["style"][key] == pytest.approx(value)
        ax.chart.set_style(linewidth=2, edgecolor="red", outline=True)
        extracted = fig.extract_style()
        with fg.Figure(backend=backend, dpi=144) as target:
            target.axes[0].bar(["X", "Y"], [20, 40])
            target.apply_style(extracted, strict=True)
            assert target.axes[0].chart.get_style()["linewidth"] == pytest.approx(2)
            assert target.axes[0].chart.get_categories() == {
                "category_0": "X",
                "category_1": "Y",
            }


@pytest.mark.parametrize("dpi", [72, 96, 120, 144])
@pytest.mark.parametrize("kind", ["line", "pie", "subplot"])
def test_native_vector_pages_keep_figure_inches_at_every_resolution(dpi, kind):
    size = (8, 6) if kind == "subplot" else (4, 3)
    with fg.Figure(backend="native", figsize=size, dpi=dpi) as fig:
        if kind == "pie":
            fig.axes[0].pie([2, 3])
        elif kind == "subplot":
            fig.set_layout([["left", "right"]])
            fig.subplots["left"].plot([0, 1], [1, 2])
            fig.subplots["right"].plot([0, 1], [2, 1])
        else:
            fig.axes[0].plot([0, 1], [1, 2])
        for scale in (1, 2):
            root = ElementTree.fromstring(fig.export("svg", scale=scale))
            assert float(root.attrib["width"].removesuffix("pt")) == pytest.approx(
                size[0] * 72
            )
            assert float(root.attrib["height"].removesuffix("pt")) == pytest.approx(
                size[1] * 72
            )
            page = PdfReader(BytesIO(fig.export("pdf", scale=scale))).pages[0]
            assert float(page.mediabox.width) == pytest.approx(size[0] * 72)
            assert float(page.mediabox.height) == pytest.approx(size[1] * 72)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_custom_label_text_survives_color_only_cell_edits(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.bar(["A", "B"], [2, 4])
        state = fig.get_settings()
        state["series"][0]["render_type"]["CategoryBars"]["labels"]["text"] = [
            "Custom A",
            "Custom B",
        ]
        fig.apply_settings(state)
        sid = next(iter(ax.chart.get_series()))
        cid = next(iter(ax.chart.get_categories()))
        ax.chart.cell(cid, sid).set_color("red").set_style(outline=True)
        ax.scatter([0, 1], [1, 2], id="unrelated")
        assert body(fig)["labels"]["text"] == ["Custom A", "Custom B"]
        ax.chart.set_value_labels(decimals=2, suffix=" u")
        assert body(fig)["labels"]["text"] == ["2 u", "4 u"]


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_new_category_panel_inherits_family_defaults_without_resetting_another(backend):
    token = fg.StyleToken(
        dict(bounded=dict(categorical=dict(group_width=0.6, label_decimals=2)))
    )
    with fg.Figure(backend=backend, grid=[["first", "second"]], style=token) as fig:
        a = fig.subplots["first"].axes
        b = fig.subplots["second"].axes
        a.bar(["A", "B"], [2.25, 3.75])
        a.chart.set_group_width(0.4)
        b.bar(["X", "Y"], [4.25, 5.75])
        state = fig.get_settings()
        assert state["config"]["bar_groups"]["group_width"] == pytest.approx(0.4)
        assert state["config"]["subplots"][0]["config"]["bar_groups"][
            "group_width"
        ] == pytest.approx(0.6)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_radar_optional_fill_opacity_and_unsupported_emphasis_are_explicit(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.radar(["A", "B", "C"], [1, 2, 3], style={"fill_opacity": 0.6})
        assert body(fig)["style"]["fill_opacity"] == pytest.approx(0.6)
        assert ax.chart.get_style()["fill_alpha"] == pytest.approx(0.6)
        before = fig.get_settings()
        with pytest.raises(ValueError, match="selection rings"):
            ax.chart.set_style(emphasis_brightness=0.2)
        assert fig.get_settings() == before
