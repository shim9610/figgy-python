"""Upstream draw modes must render, replay and enforce data-kind restrictions."""
import copy
import numpy as np
import pytest
import figgyplot as figgy


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_milkyway_rejects_scatter_in_all_mutation_routes(backend):
    with figgy.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.scatter([0, 1, 2], [1, 0, 1], id="points")
        old, revision = fig.get_settings(), fig.revision
        for apply in [lambda: fig.set_draw_style("milkyway"),
                      lambda: fig.configure(config={"draw_style": {"mode": "milkyway"}})]:
            with pytest.raises(ValueError, match="Milkyway.*line-only"):
                apply()
            assert fig.get_settings() == old and fig.revision == revision
        raw = copy.deepcopy(old)
        raw["config"]["draw_style"] = {"mode": "milkyway"}
        with pytest.raises(ValueError, match="Milkyway.*line-only"):
            fig.apply_settings(raw)
        assert fig.get_settings() == old
        raw["config"]["draw_style"] = {"mode": "sketch", "not_a_parameter": 1}
        with pytest.raises(ValueError, match="unknown draw-style"):
            fig.apply_settings(raw)
    with figgy.Figure(backend=backend) as fig:
        fig.set_draw_style("milkyway", seed=9610)
        before, revision, columns = fig.get_settings(), fig.revision, fig.info["columns"]
        for add in [lambda: fig.axes[0].scatter([0, 1], [0, 1]),
                    lambda: fig.axes[0].plot([0, 1], [0, 1], marker="o")]:
            with pytest.raises(ValueError, match="Milkyway.*line-only"):
                add()
            assert fig.get_settings() == before and fig.revision == revision
            assert fig.info["columns"] == columns
        fig.axes[0].plot([0, 1], [0, 1])


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_constellation_requires_marker_lines_and_bad_options_are_atomic(backend):
    with figgy.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([0, 1, 2], [1, 0, 1], marker="o")
        fig.set_draw_style("constellation", star_opacity=0.8)
        before, revision = fig.get_settings(), fig.revision
        for mode, options in [("constellation", {"line_opacity": -1}),
                              ("sketch", {"amplitude_px": float("inf")}),
                              ("sketch", {"not_a_parameter": 1}),
                              ("milkyway", {})]:
            with pytest.raises(ValueError):
                fig.set_draw_style(mode, **options)
            assert fig.get_settings() == before and fig.revision == revision
        fig.set_draw_style("sketch", seed=99)
        assert fig.get_settings()["config"]["draw_style"]["mode"] == "sketch"
        fig.set_draw_style("precise")
        assert "draw_style" not in fig.get_settings()["config"]


@pytest.mark.parametrize("mode", ["sketch", "milkyway", "constellation"])
def test_native_draw_modes_change_pixels_and_replay_exactly(mode):
    t = np.linspace(0, 10, 80 if mode == "constellation" else 1500)
    with figgy.Figure(backend="native") as source, figgy.Figure(backend="native") as replay:
        for f in (source, replay):
            f.axes[0].plot(t, np.sin(t), marker="o" if mode == "constellation" else None,
                           color="#7ec8f5", id="signal")
            f.axes[0].set_title("Stylized signal", fontsize=18)
        precise = source.render_rgba()
        uploads = source.info["column_uploads"]
        source.set_draw_style(mode)
        if mode == "constellation":
            source.set_facecolor("#0b0f17")
        styled = source.render_rgba()
        assert np.count_nonzero(styled != precise) > 1000
        code = source.to_code()
        assert f"set_draw_style('{mode}'" in code
        exec(code, {"fig": replay})
        assert source.get_settings() == replay.get_settings()
        np.testing.assert_array_equal(styled, replay.render_rgba())
        assert source.info["column_uploads"] == uploads
        np.testing.assert_array_equal(source.render_rgba(scale=2), replay.render_rgba(scale=2))


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_background_is_validated_replayed_and_reset(backend):
    with figgy.Figure(backend=backend) as source, figgy.Figure(backend=backend) as replay:
        source.axes[0].plot([0, 1], [0, 1])
        replay.axes[0].plot([0, 1], [0, 1])
        source.set_facecolor("#0b0f17")
        exec(source.to_code(), {"fig": replay})
        assert source.get_settings() == replay.get_settings()
        if backend == "native":
            np.testing.assert_array_equal(source.render_rgba(), replay.render_rgba())
            np.testing.assert_array_equal(source.render_rgba()[0, 0, :3], [11, 15, 23])
        before = source.get_settings()
        with pytest.raises(ValueError): source.set_facecolor((2, 0, 0))
        assert source.get_settings() == before
        source.configure(reset=True)
        assert "background" not in source.get_settings()
