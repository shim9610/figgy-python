"""Public appearance controls hide renderer containers and preserve resident data."""

import copy
import numpy as np
import pytest
import figgyplot as fg
from figgyplot.ticker import SignificantFormatter, TimestampFormatter


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_independent_axis_format_and_scale_do_not_edit_another_boundary(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([1, 2, 3], [2, 3, 4])
        original = copy.deepcopy(fig.get_settings()["config"]["bottom_x"])
        top = ax.secondary_xaxis("top").xaxis
        top.set_view_interval(1, 100)
        top.set_scale("log")
        top.set_major_formatter(SignificantFormatter(5, "degrees"))
        current = fig.get_settings()["config"]
        assert current["bottom_x"] == original
        assert current["top_x"]["scale"] == "Logarithmic"
        assert current["top_x"]["label_style"]["format"] == "Degrees"
        assert top.get_scale() == "log"


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_timestamp_formatter_preserves_values_domain_and_complete_format(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([1, 2, 3], [2, 3, 4], id="signal")
        before = fig.get_settings()
        uploads = fig.info.get("column_uploads")
        ax.xaxis.set_major_formatter(
            TimestampFormatter(
                "%Y-%m-%d %%Q %H:%M:%S.%f",
                unit="ms",
                timezone=540,
                fractional_digits=3,
                calendar=False,
                precision=6,
            )
        )
        after = fig.get_settings()
        assert after["series"] == before["series"]
        for field in ("min", "max", "major_spacing", "scale"):
            assert (
                after["config"]["bottom_x"][field]
                == before["config"]["bottom_x"][field]
            )
        fmt = after["config"]["bottom_x"]["label_style"]["format"]["Timestamp"]
        assert fmt == dict(
            unit="Milliseconds",
            timezone={"FixedOffsetMinutes": 540},
            label={"Pattern": "%Y-%m-%d %%Q %H:%M:%S.%f"},
            fractional={"Fixed": 3},
            tick_policy="NumericSpacing",
        )
        assert fig.info.get("column_uploads") == uploads
        with pytest.raises(ValueError):
            TimestampFormatter("%q")
        with pytest.raises(TypeError):
            TimestampFormatter(calendar="false")


@pytest.mark.parametrize("kind", ["categorical", "boxplot", "radial", "radar"])
@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_bounded_style_roundtrip_retains_categories_values_and_ids(kind, backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        if kind == "categorical":
            ax.bar(["a", "b"], [2, 3])
        elif kind == "boxplot":
            ax.boxplot([[1, 2, 4], [2, 4, 6]])
        elif kind == "radial":
            ax.pie([2, 3])
        else:
            ax.radar(["a", "b", "c"], [2, 3, 4])
        before = fig.get_settings()
        original = ax.chart.get_style()
        ax.chart.set_style(**original)
        assert fig.get_settings()[kind]["style"] == before[kind]["style"]
        if kind == "radar":
            ax.chart.set_style(linewidth=3, fill_alpha=0.5)
        elif kind == "radial":
            ax.chart.set_style(roughness=0.7, gloss=0.2)
        else:
            ax.chart.set_style(linewidth=2, edgecolor="red")
        after = fig.get_settings()
        for field in ("categories", "series", "slices"):
            if field in before[kind]:
                assert after[kind][field] == before[kind][field]
        assert after["identity"] == before["identity"]
        checkpoint = fig.get_settings()
        with pytest.raises(ValueError):
            ax.chart.set_style(unknown_renderer_key=4)
        assert fig.get_settings() == checkpoint


@pytest.mark.parametrize("side", ["right", "left", "top", "bottom"])
@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_colorbar_placement_and_stroke_are_independent_of_plot_axes(backend, side):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        points = ax.scatter([1, 2], [3, 4], c=[0, 1], id="mapped")
        before = fig.get_settings()
        bar = ax.get_colorbar()
        bar.set_layout(side=side)
        bar.set_outline(color="red", linewidth=2)
        bar.ax.yaxis.line.set(visible=False, color="blue")
        after = fig.get_settings()
        for field in ("bottom_x", "top_x", "left_y", "right_y"):
            assert after["config"][field] == before["config"][field]
        assert after["identity"] == before["identity"]
        assert after["series"] == before["series"]
        assert after["config"]["colorbar"]["side"] == side.title()
        assert bar.get_layout()["side"] == side
        assert points.get_clim() == (0, 1)
        bar.set_cmap("magma")
        assert points.get_cmap() == "Magma"
        bar.set_clim(2, 5)
        assert points.get_clim() == (2, 5)
        checkpoint = fig.get_settings()
        with pytest.raises(ValueError):
            bar.set_layout(side="inside")
        assert fig.get_settings() == checkpoint


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_marker_palettes_and_sparse_edits_keep_other_points_and_resident_sources(
    backend,
):
    with fg.Figure(backend=backend) as fig:
        points = fig.axes[0].scatter([1, 2, 3], [1, 2, 3], id="points")
        groups = fig.data.add("groups", [0, 1, 0])
        before = fig.get_settings()
        uploads = fig.info.get("column_uploads")
        points.markers.palette.set(
            [fg.MarkerStyle(color="red"), fg.MarkerStyle(marker="s", markersize=8)],
            source=groups,
        )
        points.markers[0].set(markersize=6)
        points.markers[1].set(color="blue")
        points.markers[1].set(markersize=10)
        assert points.markers[0].get_override().markersize == pytest.approx(6)
        assert points.markers[1].get_override().color == (0, 0, 1, 1)
        points.markers[1].set(color=None)
        assert points.markers[1].get_override().color is None
        assert points.markers[1].get_override().markersize == pytest.approx(10)
        points.markers.map_color(points.data.y, clim=(0, 4), cmap="gray")
        points.markers.map_size(points.data.y, domain=(0, 4), markersizes=(4, 12))
        current = fig.get_settings()["series"][0]
        assert current["x_column"] == before["series"][0]["x_column"]
        assert current["y_column"] == before["series"][0]["y_column"]
        assert (
            current["render_type"]["Scatter"]["scatter"]["point_size_map"]["domain_max"]
            == 4
        )
        assert fig.info.get("column_uploads") == uploads
        checkpoint = fig.get_settings()
        with pytest.raises(ValueError):
            fig.data.add("groups", [1, 0, 1])
        assert fig.get_settings() == checkpoint


def test_marker_value_mapping_and_point_override_affect_actual_pixels():
    with fg.Figure(backend="native", figsize=(9.6, 6), dpi=100) as fig:
        ax = fig.axes[0]
        points = ax.scatter([1, 2, 3], [1, 2, 3], s=100, id="points")
        groups = fig.data.add("groups", [0, 1, 0])
        points.markers.palette.set(
            [fg.MarkerStyle(color="red"), fg.MarkerStyle(color="green", marker="s")],
            source=groups,
        )
        points.markers.map_color(points.data.y, clim=(0, 4), cmap="gray")
        points.markers[1].set(color="blue")
        ax.set(xlim=(0, 4), ylim=(0, 4))
        image = fig.render_rgba()
        uploads = fig.info["column_uploads"]
        box = ax.get_position()
        centers = [
            (
                round((box.x0 + value / 4 * box.width) * 960),
                round((1 - box.y0 - value / 4 * box.height) * 600),
            )
            for value in (1, 2, 3)
        ]
        for (x, y), expected in zip(
            centers, [(64, 64, 64), (0, 0, 255), (191, 191, 191)]
        ):
            patch = image[y - 2 : y + 3, x - 2 : x + 3, :3].astype(int)
            assert np.any(np.max(np.abs(patch - np.array(expected)), axis=2) <= 3)
        points.set_cmap("magma")
        changed = fig.render_rgba()
        x, y = centers[1]
        assert np.any(
            np.all(changed[y - 2 : y + 3, x - 2 : x + 3, :3] == [0, 0, 255], axis=2)
        )
        for x, y in (centers[0], centers[2]):
            assert not np.array_equal(
                image[y - 2 : y + 3, x - 2 : x + 3],
                changed[y - 2 : y + 3, x - 2 : x + 3],
            )
        assert fig.info["column_uploads"] == uploads


def assert_public_replay(source, target):
    import ast

    code = source.to_code()
    tree = ast.parse(code)
    forbidden = {"configure", "configure_bounded", "configure_radial", "apply_settings"}
    assert not [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden
    ], code
    before = source.get_settings()
    uploads = target.info.get("column_uploads")
    exec(code, {"fig": target})
    after = target.get_settings()
    from figgyplot._charts import family

    kind = family(before)
    for key in [kind] if kind else ["config", "series"]:
        assert after[key] == before[key], code
    assert target.info.get("column_uploads") == uploads
    if source.backend == "native":
        np.testing.assert_array_equal(source.render_rgba(), target.render_rgba())
    exec(source.to_code(mode="exact"), {"fig": target})
    assert target.get_settings() == before


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize(
    "feature",
    [
        "mapped_points",
        "vector_points",
        "vector_grid",
        "steps",
        "baseline_fill",
        "series_fill",
        "polar",
        "radar",
        "annotations",
    ],
)
def test_public_export_renderer_feature_families(backend, feature):
    from test_renderer_018_features import populate

    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        populate(source, feature)
        populate(target, feature)
        assert_public_replay(source, target)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_all_annotation_kinds_rich_runs_and_mixed_coordinates_replay(backend):
    with fg.Figure(backend=backend, dpi=100) as source, fg.Figure(
        backend=backend, dpi=100
    ) as target:
        for fig in (source, target):
            ax = fig.axes[0]
            ax.plot([0, 1, 2], [1, 2, 0], id="line")
        ax = source.axes[0]
        note = ax.text(
            0.1,
            0.3,
            [
                fg.TextRun("한글 ", bold=True),
                fg.TextRun("A", color="red", fontsize=16),
                fg.TextRun("2", script="super"),
            ],
            coords="ratio",
            id="note",
        )
        note.set_bbox(facecolor="#ffffccaa", linewidth=2, pad=6)
        note.set_multialignment("center")
        line = ax.axhline(1, id="threshold")
        line.set_style(color="red", linewidth=2, linestyle="--")
        line.set_label("Threshold", fontsize=13, color="green")
        line.set_text([fg.TextRun("Threshold "), fg.TextRun("x", italic=True)])
        band = ax.axvspan(0.5, 0.8, id="band")
        band.set_style(color="#00ff0044")
        band.set_bounds(0.4, 0.9)
        arrow = ax.arrow(0, 0, 1, 1, id="arrow")
        arrow.set_endpoints((0.4, 0.4), (1.5, 1), coords="ratio", endcoords="data")
        arrow.set_label("Peak", color="blue", multialignment="right")
        arrow.set_style(linestyle=":", linewidth=2, head_length=10, head_width=7)
        arrow.set_visible(False)
        assert_public_replay(source, target)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_contours_labels_palette_and_resident_matrix_replay(backend):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].contourf([[0, 1, 2], [2, 1, 0], [1, 2, 3]], id="field")
        field = source.artist("field")
        field.contours.set_levels([0.5, 1.5, 2.5])
        field.contours.set_style(
            color="purple", linewidth=2, linestyle="--", colors=["red", "green", "blue"]
        )
        field.contours.set_labels(
            fontsize=10,
            color="black",
            formatter=SignificantFormatter(4, "scientific"),
            positions=[fg.ContourLabel(1, 0.8, 0.7, tangent=(1, 2))],
            spacing=70,
            background="#ffffffe6",
            padding=2,
        )
        field.set_field_fill(mode="bands", shading="interpolated", alpha=0.6)
        assert_public_replay(source, target)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("kind", ["categorical", "boxplot", "radial", "radar"])
def test_bounded_element_overrides_and_decorations_public_replay(backend, kind):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            ax = fig.axes[0]
            if kind == "categorical":
                ax.bar(["a", "b"], [2, 3])
            elif kind == "boxplot":
                ax.boxplot([[1, 2, 4], [2, 4, 6]])
            elif kind == "radial":
                ax.pie([2, 3])
                ax.chart.set_split(1, [1, 2], labels=["one", "two"])
            else:
                ax.radar(["a", "b", "c"], [2, 3, 4])
        ax = source.axes[0]
        chart = ax.chart
        if kind == "radial":
            chart.slice(0).set_style(material="paper", roughness=0.8)
            chart.slice(0).set_value_labels(
                position="inside", format="value_percent", color="purple"
            )
            chart.slice(0, detail=True).set_style(material="matte", gloss=0.2)
            chart.slice(1, detail=True).set_explode(0.1)
            chart.set_split_inner_radius(0.5)
            chart.decoration("slice_label", index=0).set_offset((2, 3))
        else:
            state = source.get_settings()[kind]
            sid = state["series"][0]["id"]
            if kind == "radar":
                chart.series(sid).set_style(
                    linewidth=2, facecolor="#ff000033", marker="s", markersize=6
                )
                chart.set_ring_spacing(1)
                chart.decoration(
                    "spoke_label", category=state["categories"][0]["id"]
                ).set_offset((2, 3))
            else:
                chart.series(sid).set_style(linewidth=2, edgecolor="red", outline=True)
                cell = chart.cell(state["categories"][0]["id"], sid)
                cell.set_color("green")
                cell.set_style(material="matte", linewidth=3, outline=True)
                cell.set_value_labels(
                    position="median_and_count" if kind == "boxplot" else "outside"
                )
                chart.decoration(
                    "value_label", category=state["categories"][0]["id"], series=sid
                ).set_offset((2, 3))
        ax.set_title([fg.TextRun("Summary ", bold=True), fg.TextRun("x", script="sub")])
        chart.decoration("title").set_offset((3, 4))
        chart.set_plot_bounds(
            (25, 50, 520, 250) if kind == "radial" else (90, 80, 300, 220)
        )
        ax.text(0.4, 0.4, "Note", coords="ratio", id="note").set_bbox(pad=3)
        assert_public_replay(source, target)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize(
    "case", ["palettes", "clean_palettes", "errors", "bins", "vector"]
)
def test_public_recipe_overwrites_a_differently_styled_destination(backend, case):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            ax = fig.axes[0]
            if case in ("palettes", "clean_palettes"):
                artist = ax.scatter([0, 1, 2], [2, 1, 3], id="data")
                source_col = fig.data.add("classes", [0, 1, 0])
                artist.markers.set_palette(
                    [fg.MarkerStyle(color="red"), fg.MarkerStyle(marker="s")],
                    source=source_col,
                )
                artist.markers.set_overrides(
                    [
                        (1, fg.MarkerStyle(color="blue")),
                        (1, fg.MarkerStyle(markersize=8)),
                    ]
                )
                artist.markers.map_size(source_col, domain=(0, 1), markersizes=(4, 12))
            elif case == "errors":
                artist = ax.errorbar(
                    [0, 1, 2], [1, 2, 3], yerr=[0.2, 0.1, 0.3], id="data"
                )
                source_col = fig.data.add("classes", [0, 1, 0])
                artist.errors.set_palette(
                    [fg.ErrorBarStyle(color="red"), fg.ErrorBarStyle(linewidth=3)],
                    source=source_col,
                )
                artist.errors[1].set(capsize=9, capthick=2)
            elif case == "bins":
                _, _, artist = ax.hist([0, 0, 1, 2, 3], id="data")
                artist.bins[0].set(
                    facecolor="red", edgecolor="black", linewidth=2, width=0.7, gap=2
                )
            else:
                artist = ax.quiver(
                    [0, 1, 2],
                    [1, 2, 3],
                    [1, 0, -1],
                    [0, 1, 0.5],
                    values=[1, 2, 3],
                    id="data",
                )
                artist.vectors.set(
                    color="green",
                    linewidth=2,
                    pivot="middle",
                    scale=15,
                    units="pixels",
                    min_length=3,
                    head_width=8,
                    head_length=10,
                )
        if case == "clean_palettes":
            source.artist("data").markers.set_palette(None)
            source.artist("data").markers.set_overrides(None)
            source.artist("data").markers.map_size(None)
        elif case == "palettes":
            target.artist("data").markers[0].set(color="yellow", markersize=20)
        elif case == "errors":
            target.artist("data").errors.palette[0].set(color="black")
        elif case == "bins":
            target.artist("data").bins[1].set(facecolor="green")
        else:
            target.artist("data").vectors.set(
                scale=0.5, units="data", pivot="tip", linewidth=3
            )
            source.artist("data").vectors.map_color(None)
        assert_public_replay(source, target)


@pytest.mark.parametrize(
    "variable",
    [
        "MarkerStyle",
        "ErrorBarStyle",
        "BinStyle",
        "ContourLabel",
        "TextRun",
        "TimestampFormatter",
    ],
)
def test_new_export_identifiers_do_not_shadow_the_figure(variable):
    with fg.Figure(backend="webgpu") as source, fg.Figure(backend="webgpu") as target:
        for fig in (source, target):
            artist = fig.axes[0].contour([[0, 1], [2, 3]], id="field")
            artist.contours.set_labels(positions=[fg.ContourLabel(0, 0.2, 0.3)])
            fig.axes[0].set_title([fg.TextRun("a", bold=True), fg.TextRun("b")])
            fig.axes[0].xaxis.set_major_formatter(TimestampFormatter())
        exec(source.to_code(variable=variable), {variable: target})
        assert source.get_settings()["config"] == target.get_settings()["config"]
        assert source.get_settings()["series"] == target.get_settings()["series"]


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_overlay_axis_and_custom_legend_replay_without_parent_edits(backend):
    with fg.Figure(backend=backend, grid=[["left", "right"]]) as source, fg.Figure(
        backend=backend, grid=[["left", "right"]]
    ) as target:
        for fig in (source, target):
            ax = fig.subplots["right"].axes
            ax.plot([0, 1, 2], [1, 2, 3], id="base")
            twin = ax.twinx(id="pressure")
            twin.plot([0, 1, 2], [10, 20, 30], label="Pressure", id="pressure_data")
            twin.legend(False)
        twin = source.subplots["right"].axes.get_overlay("pressure")
        primary = copy.deepcopy(
            source.subplots["right"].axes._config(source.get_settings())["left_y"]
        )
        twin.yaxis.set_view_interval(5, 50)
        twin.yaxis.set_scale("log")
        twin.yaxis.set_tick_params(
            direction="out", length=7, labelsize=8, right=True, labelright=True
        )
        twin.yaxis.set_ticklabel_offset((2, 3))
        twin.yaxis.set_layout_margin(40)
        twin.yaxis.line.set(color="purple", linewidth=2, linestyle="--")
        twin.yaxis.set_major_formatter(SignificantFormatter(4, "power"))
        twin.set_ylabel("Pressure (kPa)", fontsize=11, color="purple")
        twin.legend_handle.set_offset((3, 4))
        twin.legend_handle.content.set(
            text=[fg.TextRun("P", italic=True), fg.TextRun(" (kPa)")],
            multialignment="right",
        )
        assert (
            source.subplots["right"].axes._config(source.get_settings())["left_y"]
            == primary
        )
        assert_public_replay(source, target)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_renderer_unsupported_combinations_and_invalid_new_inputs_are_atomic(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.boxplot([[1, 2, 3], [2, 3, 4]])
        before, revision = fig.get_settings(), fig.revision
        for call in (
            lambda: ax.chart.set_value_labels(position="outside"),
            lambda: ax.chart.set_style(material="paper"),
            lambda: ax.chart.set_plot_bounds((0, 0, -2, 10)),
            lambda: ax.chart.cell("missing", "missing").set_color("red"),
        ):
            with pytest.raises((ValueError, AttributeError)):
                call()
            assert fig.get_settings() == before and fig.revision == revision
    with fg.Figure(backend=backend) as fig:
        artist = fig.axes[0].contour([[0, 1], [2, 3]])
        before, revision = fig.get_settings(), fig.revision
        for call in (
            lambda: artist.contours.set_labels(spacing=0),
            lambda: artist.contours.set_style(linestyle="bad"),
            lambda: artist.contours.set_labels(positions=[{"x": 1}]),
            lambda: artist.set_grid("unregistered"),
        ):
            with pytest.raises((ValueError, TypeError)):
                call()
            assert fig.get_settings() == before and fig.revision == revision


@pytest.mark.parametrize(
    "shape",
    [
        "Circle",
        "Square",
        "Triangle",
        "Diamond",
        "Cross",
        "CircleFilled",
        "SquareFilled",
        "TriangleFilled",
        "DiamondFilled",
        "TriangleDown",
        "TriangleLeft",
        "TriangleRight",
        "Plus",
        "Pentagon",
        "Hexagon",
        "Octagon",
        "Star",
        "TriangleDownFilled",
        "TriangleLeftFilled",
        "TriangleRightFilled",
        "PlusFilled",
        "CrossFilled",
        "PentagonFilled",
        "HexagonFilled",
        "OctagonFilled",
        "StarFilled",
    ],
)
def test_all_native_marker_shapes_export_public_symbols_and_fillstyle(shape):
    from figgyplot._markers import decode_marker

    marker, fillstyle = decode_marker(shape)
    with fg.Figure(backend="native") as source, fg.Figure(backend="native") as target:
        for fig in (source, target):
            fig.axes[0].scatter([0, 1, 2], [2, 1, 3], id="data")
        artist = source.artist("data")
        artist.set_marker(marker)
        if fillstyle is not None:
            artist.set_fillstyle(fillstyle)
        assert artist._body(source.get_settings())["scatter"]["point_shape"] == shape
        artist.markers.set_palette([fg.MarkerStyle(marker=marker, fillstyle=fillstyle)])
        assert_public_replay(source, target)
        code = source.to_code()
        assert f"marker={shape!r}" not in code


def test_bounded_public_style_map_covers_every_native_style_leaf():
    from figgyplot._appearance import _BOUNDED
    from figgyplot._native import default_bounded_json, default_radial_json
    import json

    def leaves(node, prefix=""):
        for key, value in node.items():
            path = prefix + key
            if isinstance(value, dict) and set(value) != set("rgba"):
                yield from leaves(value, path + "/")
            else:
                yield path

    for kind in ("categorical", "boxplot", "radar", "radial"):
        defaults = json.loads(
            default_radial_json() if kind == "radial" else default_bounded_json(kind)
        )
        assert {path for path, _ in _BOUNDED[kind].values()} == set(
            leaves(defaults["style"])
        )


@pytest.mark.parametrize("case", ["contour_labels", "polar", "standalone_colorbar"])
@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_export_explicitly_removes_optional_appearance_absent_from_source(
    case, backend
):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            if case == "contour_labels":
                fig.axes[0].contour([[0, 1], [2, 3]], id="field")
            else:
                fig.axes[0].plot([0, 1], [1, 2], id="line")
        if case == "contour_labels":
            target.artist("field").contours.set_labels()
        elif case == "polar":
            target.axes[0].set_polar_options(unit="radians", clockwise=True)
        else:
            target.axes[0].add_colorbar()
        assert_public_replay(source, target)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_line_fill_and_marker_ink_are_independent_in_public_export(backend):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].plot(
                [0, 1, 2],
                [1, 3, 2],
                marker="o",
                fill=0,
                fill_color="#0000ff44",
                color="red",
                id="line",
            )
        source.artist("line").markers.set(color="green", markersize=8)
        target.artist("line").markers.set(color="purple", markersize=12)
        assert_public_replay(source, target)
        source.artist("line").set_fill(0, color=None)
        assert (
            "fill_color"
            not in source.artist("line")._body(source.get_settings())["line"]
        )


def test_public_replay_keeps_every_panel_visible_against_independent_ink_oracles():
    import io
    from PIL import Image

    with fg.Figure(backend="native", grid=[["top"], ["bottom"]]) as fig:
        for panel, color in (("top", "red"), ("bottom", "blue")):
            ax = fig.subplots[panel].axes
            ax.plot(
                [0, 1], [0.25, 0.75], color=color, linewidth=3, id=panel + "_signal"
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        initial = fig.get_settings()
        exact = fig.to_code(mode="exact")
        for _ in range(2):
            image = fig.render_rgba()
            for panel, channel in (("top", 0), ("bottom", 2)):
                bounds = fig.subplots[panel].axes.get_panel_position().bounds
                height, width = image.shape[:2]
                left, bottom, w, h = bounds
                area = image[
                    round((1 - bottom - h) * height) : round((1 - bottom) * height),
                    round(left * width) : round((left + w) * width),
                ]
                other = [c for c in range(3) if c != channel]
                ink = (
                    (area[..., channel] > 200)
                    & (area[..., other[0]] < 100)
                    & (area[..., other[1]] < 100)
                    & (area[..., 3] > 200)
                )
                assert np.count_nonzero(ink) > 50, (panel, fig.info["adapter"])
            np.testing.assert_array_equal(
                image, np.asarray(Image.open(io.BytesIO(fig.to_png())))
            )
            exec(fig.to_code(), {"fig": fig})
            exec(exact, {"fig": fig})
            assert fig.get_settings() == initial


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("kind", ["categorical", "boxplot", "radial", "radar"])
def test_bounded_discovery_and_chained_edit_stay_on_the_selected_element(backend, kind):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        if kind == "radial":
            ax.pie([2, 3])
            assert ax.chart.get_slice_count() == 2
            element = ax.chart.slice(0)
        elif kind == "radar":
            ax.radar(["a", "b", "c"], [1, 2, 3])
            series = ax.chart.get_series()
            assert len(series) == 1
            assert list(ax.chart.get_categories().values()) == ["a", "b", "c"]
            element = ax.chart.series(next(iter(series)))
        else:
            ax.bar(["a", "b"], [2, 3]) if kind == "categorical" else ax.boxplot(
                [[1, 2, 3], [2, 3, 4]]
            )
            series, categories = ax.chart.get_series(), ax.chart.get_categories()
            element = ax.chart.cell(next(iter(categories)), next(iter(series)))
        shared = ax.chart.get_style()
        assert element.get_style() is None
        assert element.set_style(linewidth=2) is element
        assert element.set_color("purple") is element
        assert element.get_style()["linewidth"] == pytest.approx(2)
        assert ax.chart.get_style() == shared
        element.reset_style()
        assert element.get_style() is None


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_sparse_fillstyle_can_restore_shared_shape_inheritance(backend):
    with fg.Figure(backend=backend) as fig:
        points = fig.axes[0].scatter([0, 1], [1, 2])
        points.markers[0].set(marker="s", fillstyle="none", color="red")
        points.markers[0].set(fillstyle=None)
        override = points.markers[0].get_override()
        assert override.marker is None and override.fillstyle is None
        assert override.color == (1, 0, 0, 1)
