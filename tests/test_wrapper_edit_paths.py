"""Shared edit contracts and bounded work, independent of wall-clock CI speed."""

import copy

import pytest

import figgyplot as fg
from figgyplot import _document, _matplotlib, _native


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("side", ["left", "right", "top", "bottom"])
def test_colorbar_ticks_edit_only_the_scale_without_a_temporary_figure(
    monkeypatch, backend, side
):
    with fg.Figure(backend=backend) as fig:
        points = fig.axes[0].scatter([0, 1], [2, 3], c=[10, 20])
        bar = fig.colorbar(points)
        bar.set_layout(side=side)
        before = fig.get_settings()

        def forbidden(*args, **kwargs):
            pytest.fail(
                "a normal axis edit must not instantiate a code-generation Figure"
            )

        monkeypatch.setattr(_matplotlib, "_StateFigure", forbidden)
        bar.ax.tick_params(
            which="both", direction="inout", length=6, labelsize=14, labelcolor="red"
        )
        after = fig.get_settings()
        axis = after["config"]["colorbar"]["axis"]
        assert axis["tick"] == "Both"
        assert axis["major_tick_length"] == pytest.approx(6 * fig.dpi / 72)
        assert axis["minor_tick_length"] == pytest.approx(6 * fig.dpi / 72)
        assert axis["label_style"]["font_size"] == pytest.approx(14 * fig.dpi / 72)
        assert axis["label_style"]["color"] == dict(r=1, g=0, b=0, a=1)
        after["config"]["colorbar"] = before["config"]["colorbar"]
        assert after == before
        bar.ax.tick_params(reset=True)
        reset = fig.get_settings()["config"]["colorbar"]["axis"]
        default = fig._default_config[
            "right_y" if side in ("left", "right") else "bottom_x"
        ]
        for key in ("tick", "major_tick_length", "minor_tick_length", "label_style"):
            assert reset[key] == default[key]


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize(
    "options",
    [
        dict(grid_color="red"),
        dict(grid_alpha=0.5),
        dict(grid_linewidth=2),
        dict(grid_linestyle="--"),
    ],
)
def test_colorbar_rejects_grid_edits_instead_of_silently_discarding_them(
    backend, options
):
    with fg.Figure(backend=backend) as fig:
        bar = fig.axes[0].add_colorbar()
        before, revision = fig.get_settings(), fig.revision
        with pytest.raises(NotImplementedError, match="no grid"):
            bar.ax.tick_params(labelsize=22, **options)
        assert fig.get_settings() == before
        assert fig.revision == revision


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_scale_edits_fit_once_for_the_complete_domain_and_skip_palette_only(
    monkeypatch, backend
):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        points = ax.scatter([0, 1], [2, 3], c=[0, 1])
        bar = fig.colorbar(points, label="Concentration")
        measure = _native.fitted_colorbar_title_margin
        calls = []

        def recorded(config):
            import json

            scale = json.loads(config)["colorbar"]
            calls.append(
                (scale["axis"]["min"], scale["axis"]["max"], scale["colormap"])
            )
            return measure(config)

        monkeypatch.setattr(_native, "fitted_colorbar_title_margin", recorded)
        fig.update(points.id, cmap="gray", vmin=10, vmax=20)
        assert len(calls) == 1
        assert calls[0][:2] == (10, 20)
        assert points.get_clim() == (10, 20)
        calls.clear()
        points.set_cmap("viridis")
        bar.set_cmap("gray")
        assert calls == []
        before, revision = fig.get_settings(), fig.revision
        with pytest.raises(ValueError, match="increasing"):
            fig.update(points.id, cmap="viridis", vmin=30, vmax=20)
        assert fig.get_settings() == before and fig.revision == revision
        assert calls == []
        # Initialization of an existing scale must also use its accepted label.
        ax.add_colorbar(cmap="gray", vmin=100, vmax=200)
        assert len(calls) == 1 and calls[0][:2] == (100, 200)
        assert bar.ax.yaxis.label.get_text() == "Concentration"


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("overlay", [False, True])
def test_mappable_paths_resolve_the_same_panel_and_preserve_other_panels(
    backend, overlay
):
    with fg.Figure(backend=backend, grid=[["first", "second"]]) as fig:
        first = fig.subplots["first"].axes
        owner = fig.subplots["second"].axes
        ax = owner.twinx(id="extra") if overlay else owner
        first.scatter([1, 2], [3, 4], c=[50, 100], id="other")
        points = ax.scatter([1, 2], [3, 4], c=[1, 2], id="target")
        original = first._config(fig.get_settings())["colorbar"]
        bar = fig.colorbar(points, ax=owner, label="Target")
        points.set_clim(5, 9)
        bar.set_cmap("gray")
        assert points.get_clim() == (5, 9)
        assert (
            points.get_cmap()
            == owner._config(fig.get_settings())["colorbar"]["colormap"]
        )
        points.markers.map_color(points.data.x, clim=(0, 10), cmap="viridis")
        assert points.get_clim() == (0, 10)
        assert first._config(fig.get_settings())["colorbar"] == original
        before = fig.get_settings()
        with pytest.raises(ValueError, match="mappable panel"):
            fig.colorbar(points, ax=first)
        assert fig.get_settings() == before


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_reduced_copies_preserve_snapshot_isolation_and_nested_rollback(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([1, 2], [3, 4], id="data")
        original = fig.get_settings()
        candidate = copy.deepcopy(original)
        with fig.batch_update():
            candidate["config"]["chart_title"]["visible"] = False
            fig.apply_settings(candidate)
            candidate["config"]["chart_title"]["visible"] = True
            assert not fig.get_settings()["config"]["chart_title"]["visible"]
            accepted = fig.get_settings()
            with pytest.raises(ValueError):
                with fig.batch_update():
                    fig.axes[0].set_title("Rolled back")
                    broken = fig.get_settings()
                    broken["identity"]["panels"].append(dict(id="invalid", overlays=[]))
                    fig.apply_settings(broken)
            assert fig.get_settings() == accepted
            detached = fig.get_settings()
            detached["series"].clear()
            assert fig.get_settings()["series"] == original["series"]
        assert fig.get_settings() == accepted
        revision = fig.revision
        with pytest.raises(RuntimeError):
            with fig.batch_update():
                fig.axes[0].set_title("Also rolled back")
                raise RuntimeError("cancel outer transaction")
        assert fig.get_settings() == accepted and fig.revision == revision
        fig.apply_settings(original, reset=True)
        original["series"].clear()
        assert len(fig.get_settings()["series"]) == 1


@pytest.mark.parametrize("panels", [1, 16])
def test_colorbar_edit_snapshot_work_does_not_grow_with_panel_count(
    monkeypatch, panels
):
    with fg.Figure(
        backend="webgpu",
        figsize=(panels * 3, 4),
        grid=[[str(i) for i in range(panels)]],
    ) as fig:
        ax = fig.subplots[str(panels - 1)].axes
        points = ax.scatter([1, 2], [3, 4], c=[1, 2])
        bar = fig.colorbar(points)
        get = fig.get_settings
        calls = []

        def snapshot():
            calls.append(None)
            return get()

        monkeypatch.setattr(fig, "get_settings", snapshot)
        bar.set_label("Value", fontsize=18)
        assert len(calls) <= 2
        calls.clear()
        fig.colorbar(points)
        assert len(calls) <= 4
        calls.clear()
        fig.update(points.id, cmap="gray", vmin=10, vmax=20)
        assert len(calls) <= 2


class CountedList(list):
    def __init__(self, values, counter):
        super().__init__(values)
        self.counter = counter

    def __iter__(self):
        for value in super().__iter__():
            self.counter[0] += 1
            yield value


def test_linked_groups_visit_members_linearly_and_keep_dimensions_separate():
    n, work = 500, [0]
    groups = {
        str(i): dict(axis="x", members=CountedList([str(i), str(i + 1)], work))
        for i in reversed(range(n))
    }
    groups["cycle"] = dict(axis="x", members=["20", "21", "22"])
    groups["y"] = dict(axis="y", members=["0", "y-only"])
    meta = dict(groups=groups)
    assert _document.tick_owners(meta, "0", "bottom_x") == {
        str(i) for i in range(n + 1)
    }
    assert work[0] <= 4 * n
    assert _document.tick_owners(meta, "0", "left_y") == {"0", "y-only"}
    assert _document.tick_owners(meta, "0", "top_x") == {"0"}
    assert _document.tick_owners(meta, "isolated", "bottom_x") == {"isolated"}


def test_grid_placement_sums_weights_once_and_resolves_panels_once():
    n, weights_work, panels_work = 300, [0], [0]
    state = dict(
        config=dict(subplots=[dict(config={}) for _ in range(n - 1)]),
        identity=dict(
            panels=CountedList([dict(id=str(i)) for i in range(n)], panels_work),
            layout=dict(
                grid=[[str(i) for i in range(n)]],
                placement={str(i): str(i) for i in range(n)},
                row_weights=[1],
                column_weights=CountedList([1] * n, weights_work),
                gap=0,
                size=[100 * n, 200],
            ),
        ),
    )
    _document.place_grid(state)
    assert weights_work[0] <= 2 * n
    assert panels_work[0] <= n
    assert state["config"]["chart_area"] == dict(x=0, y=0, width=100, height=200)
    for index, panel in enumerate(state["config"]["subplots"], start=1):
        assert panel["config"]["chart_area"] == dict(
            x=100 * index, y=0, width=100, height=200
        )


def test_tick_options_convert_once_and_do_not_alias_per_axis_colors(monkeypatch):
    import importlib

    module = importlib.import_module("figgyplot.figure")
    with fg.Figure(backend="webgpu") as fig:
        conversions = []
        color = module._color

        def counted(value):
            conversions.append(value)
            return color(value)

        monkeypatch.setattr(module, "_color", counted)
        fig.axes[0].tick_params(
            axis="both", which="both", labelcolor="red", grid_color="blue"
        )
        assert conversions == ["red", "blue"]
        state = fig.get_settings()
        state["config"]["bottom_x"]["label_style"]["color"]["a"] = 0.2
        state["config"]["grid"]["major_x_color"]["a"] = 0.3
        assert state["config"]["top_x"]["label_style"]["color"]["a"] == 1
        assert state["config"]["grid"]["minor_x_color"]["a"] == 1
