"""Public object/argument contracts, independently compared with Matplotlib."""

import copy

import numpy as np
import pytest
import figgyplot as fg


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_title_axis_and_spine_objects_expose_public_style_methods(backend):
    with fg.Figure(backend=backend, dpi=100) as fig:
        ax = fig.axes[0]
        ax.plot([0, 1], [1, 2], id="signal")
        ax.title.set_text("Public title")
        ax.title.set_fontsize(19)
        ax.title.set_color("red")
        ax.title.set_fontweight("bold")
        ax.xaxis.set_label_text("Time", fontsize=11)
        ax.yaxis.set_label_text("Value", color="purple")
        ax.spines["top"].set_visible(False)
        assert ax.get_title() == "Public title"
        assert ax.get_xlabel() == "Time" and ax.get_ylabel() == "Value"
        assert ax.title.get_fontsize() == pytest.approx(19)
        assert ax.title.get_color() == (1.0, 0.0, 0.0, 1.0)
        assert not ax.spines["top"].get_visible()
        assert all(
            s["bold"]
            for s in fig.get_settings()["config"]["chart_title"]["text"]["segments"]
        )


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_tick_params_points_direction_labels_and_visibility(backend):
    with fg.Figure(backend=backend, dpi=144) as fig:
        ax = fig.axes[0]
        ax.plot([0, 1], [1, 2])
        ax.tick_params(
            axis="x",
            which="major",
            direction="out",
            length=7,
            labelsize=11,
            labelcolor="red",
            top=False,
            labeltop=False,
        )
        state = fig.get_settings()["config"]
        assert state["bottom_x"]["major_tick_length"] == 14
        assert state["bottom_x"]["label_style"]["font_size"] == 22
        assert state["bottom_x"]["tick"] == "Outside"
        assert state["top_x"]["tick"] == "None"
        assert not state["top_x"]["label_style"]["label_visible"]
        assert state["left_y"]["label_style"]["font_size"] != 22
        before, revision = fig.get_settings(), fig.revision
        with pytest.raises(NotImplementedError):
            ax.tick_params(pad=10)
        assert fig.get_settings() == before and fig.revision == revision


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_resize_in_inches_preserves_data_and_panel_identity(backend):
    with fg.Figure(
        backend=backend, dpi=100, figsize=(8, 5), grid=[["one", "two"]]
    ) as fig:
        fig.subplots["one"].plot([0, 1], [2, 3], id="signal")
        ids = copy.deepcopy(fig.get_settings()["identity"]["panels"])
        uploads = fig.info.get("column_uploads")
        fig.set_size_inches(12, 6)
        np.testing.assert_array_equal(fig.get_size_inches(), [12, 6])
        assert fig.get_settings()["identity"]["panels"] == ids
        assert fig.info.get("column_uploads") == uploads
        assert fig.subplots["two"].axes.id == "two"


def test_supported_calls_match_matplotlib_public_object_properties():
    from matplotlib.figure import Figure

    reference = Figure(figsize=(8, 5), dpi=100)
    ra = reference.subplots()
    with fg.Figure(figsize=(8, 5), dpi=100, backend="webgpu") as candidate:
        ca = candidate.axes[0]
        for ax in [ra, ca]:
            ax.plot([0, 1], [1, 2])
            ax.title.set_text("Title")
            ax.title.set_fontsize(18)
            ax.xaxis.set_label_text("Time")
            ax.yaxis.set_label_text("Value")
            ax.spines["top"].set_visible(False)
            ax.tick_params(
                axis="x", direction="out", length=7, labelsize=11, labelcolor="red"
            )
        assert ca.get_title() == ra.get_title()
        assert ca.get_xlabel() == ra.get_xlabel()
        assert ca.get_ylabel() == ra.get_ylabel()
        assert ca.title.get_fontsize() == ra.title.get_fontsize()
        assert ca.spines["top"].get_visible() == ra.spines["top"].get_visible()
        candidate.set_size_inches(12, 6)
        reference.set_size_inches(12, 6)
        np.testing.assert_array_equal(
            candidate.get_size_inches(), reference.get_size_inches()
        )


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_public_style_batch_commits_once_and_rolls_back_failed_edits(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([0, 1], [1, 2])
        revision = fig.revision
        with fig.batch_update():
            ax.title.set_text("Batched")
            ax.xaxis.set_label_text("Time")
            ax.tick_params(length=8)
            assert fig.revision == revision
        assert fig.revision == revision + 1
        before = fig.get_settings()
        revision = fig.revision
        with pytest.raises(ValueError):
            with fig.batch_update():
                ax.title.set_text("Rolled back")
                ax.spines["top"].set(visible=False, unsupported=True)
        assert fig.get_settings() == before and fig.revision == revision
        with pytest.raises(RuntimeError):
            with fig.batch_update():
                ax.plot([0, 1], [4, 5])
        assert fig.get_settings() == before and fig.revision == revision


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_standard_plot_aliases_and_returned_text_match_matplotlib(backend):
    from matplotlib.figure import Figure

    reference = Figure(dpi=120).subplots()
    with fg.Figure(backend=backend, dpi=120) as fig:
        actual = fig.axes[0]
        for ax in (reference, actual):
            (line,) = ax.plot(
                [0, 1],
                [2, 4],
                lw=2.5,
                ls="--",
                ms=7,
                c="C2",
                marker="s",
                alpha=0.4,
                gid="signal",
            )
            title = ax.set_title("Title", fontsize=18, fontweight="bold")
            title.set_color("magenta")
            xlabel = ax.set_xlabel("Time", fontsize=12)
            xlabel.set_text("Time (s)")
        left = reference.get_lines()[0]
        right = actual.get_lines()[0]
        assert right.get_gid() == left.get_gid() == "signal"
        assert right.get_linewidth() == pytest.approx(left.get_linewidth(), rel=1e-6)
        assert right.get_markersize() == pytest.approx(left.get_markersize(), rel=1e-6)
        assert right.get_marker() == left.get_marker()
        assert right.get_linestyle() == left.get_linestyle()
        from matplotlib.colors import to_rgba

        np.testing.assert_allclose(
            right.get_color(), to_rgba(left.get_color(), left.get_alpha())
        )
        assert actual.get_xlabel() == reference.get_xlabel()
        assert actual.title.get_fontsize() == reference.title.get_fontsize()
        np.testing.assert_array_equal(
            actual.title.get_color(), to_rgba(reference.title.get_color())
        )


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_scatter_size_arrays_are_point_areas_like_matplotlib(backend):
    from matplotlib.figure import Figure

    sizes = np.array([0.0, 4.0, 16.0, 64.0])
    ref = Figure().subplots().scatter([0, 1, 2, 3], [1, 2, 3, 4], s=sizes)
    with fg.Figure(backend=backend, dpi=144) as fig:
        artist = fig.axes[0].scatter([0, 1, 2, 3], [1, 2, 3, 4], s=sizes)
        mapping = artist._body(fig.get_settings())["scatter"]["point_size_map"]
        t = np.clip(
            (sizes - mapping["domain_min"])
            / (mapping["domain_max"] - mapping["domain_min"]),
            0,
            1,
        )
        radii = np.sqrt(
            mapping["min_px"] ** 2
            + (mapping["max_px"] ** 2 - mapping["min_px"] ** 2) * t
        )
        # Read Matplotlib's actual public sizes, then derive the renderer radii.
        np.testing.assert_allclose(
            radii, np.sqrt(ref.get_sizes()) * fig.dpi / 144, rtol=1e-6
        )
        before, revision = fig.get_settings(), fig.revision
        with pytest.raises(ValueError):
            fig.axes[0].scatter([0, 1], [1, 2], s=[-1, 4])
        assert fig.get_settings() == before and fig.revision == revision


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_text_coordinates_and_annotation_handles_use_public_arguments(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([0, 1], [1, 2])
        note = ax.text(
            0.2,
            0.8,
            "Corner",
            transform=ax.transAxes,
            fontweight="bold",
            fontfamily="DejaVu Sans",
        )
        np.testing.assert_allclose(note.get_position(), (0.2, 0.8))
        anchor = next(iter(note._find(fig.get_settings())[2]["kind"].values()))[
            "anchor"
        ]
        assert anchor["Ratio"] == pytest.approx(dict(x=0.2, y=0.2))
        note.set_position((0.3, 0.7))
        note.set_text("Moved")
        note.set_fontsize(13)
        assert note.get_text() == "Moved" and note.get_fontsize() == pytest.approx(13)
        linked = ax.annotate(
            "Peak",
            xy=(1, 2),
            xytext=(0.4, 0.8),
            textcoords="axes fraction",
            arrowprops={"arrowstyle": "->", "color": "red"},
        )
        linked.set_position((0.6, 0.7))
        state = fig.get_settings()
        arrow = next(iter(linked.arrow_patch._find(state)[2]["kind"].values()))
        assert arrow["to"]["Data"] == dict(x=1.0, y=2.0)
        assert arrow["from"]["Ratio"] == pytest.approx(dict(x=0.6, y=0.3))
        before, revision = fig.get_settings(), fig.revision
        with pytest.raises(NotImplementedError):
            ax.annotate("bad", xy=(1, 2), arrowprops={"connectionstyle": "arc3"})
        assert fig.get_settings() == before and fig.revision == revision


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_regular_locator_grid_legend_position_and_limits_match_public_contract(backend):
    from matplotlib.figure import Figure
    from matplotlib.ticker import MultipleLocator

    ref = Figure(dpi=100).subplots()
    with fg.Figure(backend=backend, dpi=100) as fig:
        ax = fig.axes[0]
        for candidate in (ref, ax):
            candidate.plot([0, 1], [2, 4], label="Data")
            candidate.set_xlim(2, -2)
            candidate.set_ylim((1, 5))
            candidate.xaxis.set_major_locator(MultipleLocator(0.5))
            candidate.grid(
                True, axis="y", which="minor", color="red", linewidth=2, linestyle=":"
            )
            candidate.legend(loc="lower left", fontsize=12, framealpha=0.5)
            candidate.set_position((0.2, 0.25, 0.6, 0.5))
        assert ax.get_xlim() == ref.get_xlim() and ax.get_ylim() == ref.get_ylim()
        assert ax.xaxis_inverted() == ref.xaxis_inverted()
        np.testing.assert_allclose(
            ax.get_position().bounds, ref.get_position().bounds, atol=1e-6
        )
        np.testing.assert_allclose(
            ax.get_legend().get_frame().get_facecolor(),
            ref.get_legend().get_frame().get_facecolor(),
        )
        state = fig.get_settings()["config"]
        assert state["bottom_x"]["major_spacing"] == pytest.approx(0.5)
        assert state["grid"]["show_minor_y"]
        assert state["grid"]["minor_y_width"] == pytest.approx(2 * 100 / 72)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_colorbar_public_handle_keeps_mappable_and_scale_connected(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        points = ax.scatter([1, 2], [3, 4], c=[10, 20])
        bar = fig.colorbar(points, ax=ax, label="Temperature")
        points.set_cmap("magma")
        points.set_clim((5, 25))
        bar.ax.tick_params(labelsize=11)
        assert points.get_cmap() == "Magma" and points.get_clim() == (5, 25)
        assert bar.ax.yaxis.label.get_text() == "Temperature"
        assert fig.get_settings()["config"]["colorbar"]["axis"]["label_style"][
            "font_size"
        ] == pytest.approx(11 * fig.dpi / 72)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("variable", ["fig", "_ax", "text_segments", "MultipleLocator"])
def test_default_export_uses_public_calls_and_replays_styles_and_pixels(
    backend, variable
):
    with fg.Figure(backend=backend, dpi=120) as source, fg.Figure(
        backend=backend, dpi=120
    ) as target:
        for fig in (source, target):
            ax = fig.axes[0]
            ax.plot([0, 1, 2], [2, 1, 4], marker="o", id="signal", label="Signal")
        ax = source.axes[0]
        ax.set_title("Public API", fontsize=18, fontweight="bold")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.set_xlim(-0.5, 2.5)
        ax.set_ylim(0, 5)
        ax.tick_params(axis="x", direction="out", labelsize=10)
        ax.spines["top"].set_visible(False)
        ax.grid(False, axis="x")
        ax.legend(loc="lower left", fontsize=12, framealpha=0.5)
        target.axes[0].set_title("Stale", fontsize=35, color="red")
        target.axes[0].tick_params(axis="y", labelsize=20)
        target.set_facecolor("black")
        source_state = source.get_settings()
        target_id = target.id
        uploads = target.info.get("column_uploads")
        revision = target.revision
        code = source.to_code(variable)
        assert ".tick_params(" in code and ".spines[" in code
        assert ".set_title(" in code and ".set_xlabel(" in code
        assert ".configure(" not in code and ".apply_settings(" not in code
        assert "render_type" not in code and "point_size" not in code
        exec(code, {variable: target})
        accepted = target.get_settings()
        assert accepted["config"] == source_state["config"]
        assert accepted["series"] == source_state["series"]
        assert target.id == target_id
        assert source.get_settings() == source_state
        assert target.info.get("column_uploads") == uploads
        assert target.revision == revision + 1
        if backend == "native":
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())
        # Exact mode still has the full identity/metadata oracle.
        exec(source.to_code(variable, mode="exact"), {variable: target})
        assert target.get_settings() == source_state


def test_batch_nested_savepoint_and_retirement_are_based_on_final_state():
    with fg.Figure(backend="webgpu") as fig:
        ax = fig.axes[0]
        ax.plot([0, 1], [2, 3])
        ax.text(0.2, 0.3, "Keep", id="note")
        original = fig.get_settings()
        revision = fig.revision
        with fig.batch_update():
            fig.clear_annotations()
            ax.text(0.4, 0.5, "Moved", id="note")
            try:
                with fig.batch_update():
                    ax.set_title("Must roll back")
                    raise ValueError("cancel")
            except ValueError:
                pass
        accepted = fig.get_settings()
        assert accepted["config"]["chart_title"] == original["config"]["chart_title"]
        assert "annotation/note" not in accepted["identity"]["retired"]
        assert fig.revision == revision + 1


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_common_histogram_and_error_styles_export_without_renderer_fields(backend):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            ax = fig.axes[0]
            ax.stairs([2, 4, 3], [0, 1, 2, 3], id="histogram")
            ax.errorbar([0.5, 1.5, 2.5], [2, 4, 3], yerr=[0.2, 0.3, 0.4], id="errors")
        code = source.to_code()
        assert ".configure(" not in code and "render_type" not in code
        source.artist("histogram").set_edgecolor("red")
        source.artist("errors").set_errorbar_style(
            color="purple", width=2, capsize=4, capthick=1
        )
        exec(source.to_code(), {"fig": target})
        assert target.get_settings()["series"] == source.get_settings()["series"]
        if backend == "native":
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())


def test_cpu_export_canonicalization_matches_the_accepted_f32_serialization():
    import json
    from figgyplot._native import canonical_style_state_json

    with fg.Figure(backend="webgpu") as fig:
        fig.axes[0].plot([0, 1], [2, 3], lw=2.5)
        state = fig.get_settings()
        assert json.loads(canonical_style_state_json(json.dumps(state))) == state


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("family", ["categorical", "boxplot", "radar", "radial"])
def test_common_bounded_appearance_uses_named_controls_and_preserves_values(
    backend, family
):
    def build(fig, offset):
        ax = fig.axes[0]
        if family == "categorical":
            ax.bar(["A", "B"], [2 + offset, 4 + offset])
        elif family == "boxplot":
            ax.boxplot(
                [
                    [1 + offset, 2 + offset, 3 + offset],
                    [2 + offset, 4 + offset, 5 + offset],
                ]
            )
        elif family == "radar":
            ax.radar(["A", "B", "C"], [2 + offset, 4 + offset, 3 + offset])
        else:
            ax.donut([2 + offset, 4 + offset])
        ax.set_title("Chart")

    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        build(source, 0)
        build(target, 0)
        source.axes[0].chart.set_label_style(fontsize=12)
        source.axes[0].title.set_fontweight("bold")
        target.axes[0].chart.set_label_style(fontsize=18, color="red")
        before = source.get_settings()
        code = source.to_code()
        assert ".configure_" not in code and ".apply_settings(" not in code
        exec(code, {"fig": target})
        assert target.get_settings()[family] == before[family]
        if backend == "native":
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())
        # Appearance export does not overwrite a second dataset.
        with fg.Figure(backend=backend) as other:
            build(other, 10)
            data_key, value_key = (
                ("slices", "value") if family == "radial" else ("series", "values")
            )
            values = [s[value_key] for s in other.get_settings()[family][data_key]]
            exec(code, {"fig": other})
            assert [
                s[value_key] for s in other.get_settings()[family][data_key]
            ] == values


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_export_preserves_an_editor_accepted_unresolved_font(backend):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].plot([0, 1], [2, 3], id="signal", label="Signal")
            fig.axes[0].set_title("Title")
            fig.axes[0].legend()
        # The renderer/editor preserves a typed name while resolving fallback;
        # the strict Python font setter must not make the resulting code fail.
        source.configure(
            config={
                "chart_title": {"text": {"font": "Unresolved trial family"}},
                "legend": {"content": {"font": "Unresolved trial family"}},
            }
        )
        exec(source.to_code(), {"fig": target})
        assert target.get_settings()["config"] == source.get_settings()["config"]
        if backend == "native":
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())


@pytest.mark.parametrize(
    "c,alpha",
    [
        ("steelblue", None),
        ("red", 0.5),
        (["red", "blue"], None),
        ([(1, 0, 0, 1), (0, 0, 1, 0.5)], None),
    ],
)
@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_scatter_c_accepts_explicit_matplotlib_color_forms(backend, c, alpha):
    from matplotlib.figure import Figure

    reference = Figure().subplots().scatter([0, 1], [1, 2], c=c, alpha=alpha)
    with fg.Figure(backend=backend) as fig:
        artist = fig.axes[0].scatter([0, 1], [1, 2], c=c, alpha=alpha, s=100)
        state = fig.get_settings()
        body = artist._body(state)["scatter"]
        assert not state["config"].get("colorbar")
        overrides = body.get("point_style_overrides", [])
        colors = (
            [tuple(item["point_color"][k] for k in "rgba") for item in overrides]
            if overrides
            else [tuple(body["point_color"][k] for k in "rgba")]
        )
        np.testing.assert_allclose(
            colors, reference.get_facecolors(), rtol=1e-6, atol=1e-7
        )
        reference.set_alpha(0.25)
        artist.set_alpha(0.25)
        updated = artist._body(fig.get_settings())["scatter"]
        updated_colors = [
            tuple(item["point_color"][k] for k in "rgba")
            for item in updated.get("point_style_overrides", [])
        ] or [tuple(updated["point_color"][k] for k in "rgba")]
        np.testing.assert_allclose(
            updated_colors, reference.get_facecolors(), rtol=1e-6, atol=1e-7
        )
        if backend == "native":
            pixels = fig.render_rgba()
            assert np.count_nonzero(np.any(pixels[:, :, :3] < 220, axis=2)) > 500
        before, revision, uploads = (
            fig.get_settings(),
            fig.revision,
            fig.info.get("column_uploads"),
        )
        with pytest.raises(NotImplementedError):
            fig.axes[0].scatter([0, 1], [1, 2], c=[1, 2], alpha=0.5)
        assert fig.get_settings() == before and fig.revision == revision
        assert fig.info.get("column_uploads") == uploads
        mapped = fig.axes[0].scatter([0, 1], [1, 2], c=[1, 2])
        before = fig.get_settings()
        with pytest.raises(NotImplementedError):
            mapped.set_alpha(0.5)
        assert fig.get_settings() == before


def test_css_named_cycle_grayscale_and_short_colors_match_matplotlib():
    from matplotlib.colors import CSS4_COLORS, to_rgba
    from figgyplot.figure import _color

    for value in [
        *CSS4_COLORS,
        "g",
        "c",
        "m",
        "y",
        "C0",
        "C12",
        "0.5",
        ".25",
        "SteelBlue",
    ]:
        np.testing.assert_array_equal(
            tuple(_color(value)[k] for k in "rgba"), to_rgba(value)
        )


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_markers_can_be_added_to_a_resident_line_through_artist_set(backend):
    from matplotlib.figure import Figure

    (reference,) = Figure().subplots().plot([0, 1, 2], [1, 3, 2])
    with fg.Figure(backend=backend) as fig:
        (line,) = fig.axes[0].plot([0, 1, 2], [1, 3, 2], id="signal")
        assert line.get_marker() == reference.get_marker()
        assert fig.artist("signal") is line
        assert fig.axes[0].lines[0] is line
        before = fig.get_settings()
        uploads = fig.info.get("column_uploads")
        revision = fig.revision
        reference.set(marker="s", markersize=7)
        line.set(marker="s", ms=7)
        assert line.get_marker() == reference.get_marker()
        assert line.get_markersize() == pytest.approx(
            reference.get_markersize(), rel=1e-6
        )
        assert (
            fig.info.get("column_uploads") == uploads and fig.revision == revision + 1
        )
        assert fig.get_settings()["config"] == before["config"]
        assert [
            s[k] for s in fig.get_settings()["series"] for k in ("x_column", "y_column")
        ] == [s[k] for s in before["series"] for k in ("x_column", "y_column")]
        if backend == "native":
            assert fig.render_rgba().shape == (600, 960, 4)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_secondary_locator_preserves_primary_automatic_tick_policy(backend):
    from matplotlib.figure import Figure
    from matplotlib.ticker import MultipleLocator

    reference = Figure().subplots()
    reference.set_xlim(0, 2)
    primary = reference.xaxis.get_major_locator()
    reference.secondary_xaxis("top").xaxis.set_major_locator(MultipleLocator(0.25))
    assert reference.xaxis.get_major_locator() is primary
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([0, 1, 2], [1, 3, 2])
        ax.set_xlim(0, 2)
        before = fig.get_settings()
        ax.secondary_xaxis("top").xaxis.set_major_locator(MultipleLocator(0.25))
        after = fig.get_settings()
        assert after["config"]["bottom_x"] == before["config"]["bottom_x"]
        assert (
            after["identity"]["tick_modes"]["main"]["bottom_x"]
            == before["identity"]["tick_modes"]["main"]["bottom_x"]
            == "Auto"
        )
        assert after["identity"]["tick_modes"]["main"]["top_x"] == "Fixed"


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_primary_locator_and_formatter_preserve_an_independent_boundary(backend):
    from figgyplot.ticker import MultipleLocator, SignificantFormatter

    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([0, 1, 2], [1, 3, 2])
        ax.set_ylim(0, 4)
        ax.configure(
            right_y={"scale": "Logarithmic", "min": 1, "max": 100, "major_spacing": 1}
        )
        before = fig.get_settings()
        ax.yaxis.set_major_locator(MultipleLocator(2))
        ax.yaxis.set_major_formatter(SignificantFormatter(4, style="scientific"))
        after = fig.get_settings()
        assert after["config"]["right_y"] == before["config"]["right_y"]
        assert after["config"]["left_y"]["major_spacing"] == 2
        assert after["config"]["left_y"]["label_style"]["format"] == "Scientific"


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_colorbar_locator_preserves_plot_axes_tick_intent_and_norm(backend):
    from matplotlib.ticker import MultipleLocator

    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        points = ax.scatter([0, 1], [1, 2], c=[10, 20])
        ax.set_ylim(0, 3)
        bar = fig.colorbar(points, ax=ax)
        before = fig.get_settings()
        bar.ax.yaxis.set_major_locator(MultipleLocator(0.5))
        after = fig.get_settings()
        for side in ("bottom_x", "top_x", "left_y", "right_y"):
            assert after["config"][side] == before["config"][side]
        assert after["identity"] == before["identity"]
        assert after["config"]["colorbar"]["axis"]["major_spacing"] == 0.5
        assert points.get_clim() == (10, 20)


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("cmap", ["viridis", "magma", "turbo", "gray", "RdBu"])
def test_every_builtin_colormap_exports_and_constructs_widgets(backend, cmap):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].scatter(
                [0, 1, 2], [1, 3, 2], c=[0, 1, 2], cmap=cmap, id="mapped"
            )
        source.artist("mapped").set_cmap(source.artist("mapped").get_cmap())
        code = source.to_code()
        exec(code, {"fig": target})
        assert target.get_settings()["config"] == source.get_settings()["config"]
        assert target.get_settings()["series"] == source.get_settings()["series"]
        if backend == "webgpu":
            widget = source.widget()
            assert widget.state.get("code_error", "") == ""
            assert widget.state.get("code_mode", "api") == "api"
        else:
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("notation", ["Degrees", "Radians", {"Timestamp": {}}])
def test_angle_and_timestamp_notation_remains_in_explicit_advanced_export(
    backend, notation
):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].plot([0, 1, 2], [1, 3, 2], id="signal")
        source.axes[0].configure(bottom_x={"label_style": {"format": notation}})
        exec(source.to_code(), {"fig": target})
        assert target.get_settings()["config"] == source.get_settings()["config"]
        if backend == "native":
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_editor_export_failure_keeps_chart_and_exact_recovery_available(
    backend, monkeypatch
):
    from figgyplot import _api_codegen
    from figgyplot.editor import EditorSession

    def unavailable(*args, **kwargs):
        raise ValueError(
            "simulated code export failure\nraise RuntimeError('not executable code')"
        )

    with fg.Figure(backend=backend) as fig, fg.Figure(backend=backend) as target:
        for item in (fig, target):
            item.axes[0].plot([0, 1], [1, 2], id="signal")
        before = fig.get_settings()
        monkeypatch.setattr(_api_codegen, "settings_to_api_code", unavailable)
        payload = (
            fig.widget().state if backend == "webgpu" else EditorSession(fig).snapshot()
        )
        assert payload["settings"] == before
        assert (
            payload["code_mode"] == "exact"
            and "simulated code export failure" in payload["code_error"]
        )
        exec(payload["code"], {"fig": target})
        assert target.get_settings() == before


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_auto_and_log_locators_preserve_ranges_and_explicit_formatting(backend):
    from figgyplot.ticker import AutoLocator, LogLocator, SignificantFormatter

    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([0, 1, 2], [1, 3, 2])
        ax.set_yscale("log")
        ax.set_ylim(1, 100)
        ax.yaxis.set_major_locator(LogLocator(100))
        state = fig.get_settings()
        assert state["config"]["left_y"]["major_spacing"] == 2
        assert state["identity"]["tick_modes"]["main"]["left_y"] == "Fixed"
        assert ax.yaxis.get_major_locator().base == 100
        ax.yaxis.set_major_formatter(SignificantFormatter(4, style="scientific"))
        label = fig.get_settings()["config"]["left_y"]["label_style"]
        ax.yaxis.set_major_locator(AutoLocator())
        assert ax.get_ylim() == (1, 100)
        assert fig.get_settings()["config"]["left_y"]["label_style"] == label
        assert fig.get_settings()["identity"]["tick_modes"]["main"]["left_y"] == "Auto"


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("primary_log", [False, True])
def test_independent_boundary_scales_export_without_reinterpreting_locators(
    backend, primary_log
):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].plot([0, 1, 2], [1, 3, 2], id="signal")
        ax = source.axes[0]
        ax.set_ylim(1, 100)
        if primary_log:
            ax.set_yscale("log")
        ax.configure(
            right_y={
                "scale": "Linear" if primary_log else "Logarithmic",
                "min": 1,
                "max": 100,
                "major_spacing": 10 if primary_log else 1,
            }
        )
        code = source.to_code()
        exec(code, {"fig": target})
        assert target.get_settings()["config"] == source.get_settings()["config"]
        assert target.get_settings()["series"] == source.get_settings()["series"]
        if backend == "native":
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_default_export_omits_proven_native_no_op_style_calls(backend):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].plot([0, 1, 2], [1, 3, 2], id="signal")
        source.axes[0].set(title="Measured", xlabel="Time", ylabel="Value")
        source.artist("signal").set(color="C2", lw=2)
        code = source.to_code()
        assert ".tick_params(" not in code
        assert ".grid(" not in code
        assert ".configure(" not in code
        exec(code, {"fig": target})
        assert target.get_settings()["config"] == source.get_settings()["config"]
        assert target.get_settings()["series"] == source.get_settings()["series"]
        if backend == "native":
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_export_replays_added_markers_on_the_original_resident_line(backend):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].plot([0, 1, 2], [1, 3, 2], id="signal")
        source.artist("signal").set(marker="s", ms=6, color="C2", lw=2)
        uploads = target.info.get("column_uploads")
        exec(source.to_code(), {"fig": target})
        assert target.get_settings()["config"] == source.get_settings()["config"]
        assert target.get_settings()["series"] == source.get_settings()["series"]
        assert target.artist("signal") is target.axes[0].lines[0]
        assert target.info.get("column_uploads") == uploads
        if backend == "native":
            np.testing.assert_array_equal(target.render_rgba(), source.render_rgba())
