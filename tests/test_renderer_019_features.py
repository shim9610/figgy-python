"""Exercise real 0.19 public chart sources, exports and shared host settings."""

import hashlib
import json
import numpy as np
import pytest
import figgyplot as fg


def populate(ax, kind):
    f32 = lambda v: np.asarray(v, dtype=np.float32)
    if kind == "stem":
        return ax.stem(f32([1, 3, 2]))
    if kind == "bar":
        return ax.bar(["A", "B"], f32([2, 4]))
    if kind == "radar":
        return ax.radar(["A", "B", "C"], f32([2, 4, 3]))
    if kind == "box":
        return ax.boxplot([[1, 2, 3], [2, 4, 5]])
    if kind == "violin":
        return ax.violinplot([[1, 2, 3], [2, 3, 5]])
    if kind == "raincloud":
        return ax.raincloud([[1, 2, 3], [2, 3, 5]])
    if kind == "range":
        return ax.range_bars([0, 1], [1, 2], [3, 4])
    if kind == "candle":
        return ax.candlestick([0, 1], [1, 2], [4, 5], [0, 1], [3, 4])
    if kind == "stream":
        return ax.streamlines([0, 1, 2], [0, 1, 0])
    if kind == "ternary":
        return ax.ternary([0.2, 0.6], [0.3, 0.2], [0.5, 0.2])
    if kind == "parallel":
        return ax.parallel_coordinates([[1, 2, 3], [2, 1, 4]])
    if kind == "rgb":
        return ax.imshow(
            np.array(
                [[[255, 0, 0], [0, 255, 0]], [[0, 0, 255], [255, 255, 0]]],
                dtype=np.uint8,
            )
        )
    if kind == "hexbin":
        return ax.hexbin([0, 1, 2, 1], [0, 1, 0, 2], gridsize=5)
    if kind == "mesh":
        return ax.tripcolor([0, 1, 0], [0, 0, 1], [1, 2, 3], triangles=[[0, 1, 2]])
    if kind == "tricontour":
        return ax.tricontour([0, 1, 0], [0, 0, 1], [1, 2, 3], triangles=[[0, 1, 2]])
    if kind == "surface":
        return ax.plot_surface([0, 1], [0, 1], [[1, 2], [2, 1]])
    if kind == "trisurf":
        return ax.plot_trisurf([0, 1, 0], [0, 0, 1], [1, 2, 3], triangles=[[0, 1, 2]])
    if kind == "line3d":
        return ax.plot3D([0, 1, 2], [0, 1, 0], [1, 2, 3])
    if kind == "scatter3d":
        return ax.scatter3D([0, 1, 2], [0, 1, 0], [1, 2, 3])
    if kind == "quiver3d":
        return ax.quiver3D([0, 1], [0, 1], [0, 1], [1, 0], [0, 1], [1, 1])
    if kind == "sunburst":
        return ax.sunburst(
            [
                dict(
                    label="A",
                    children=[dict(label="B", value=2), dict(label="C", value=1)],
                )
            ]
        )
    if kind == "feynman":
        return ax.feynman(
            [dict(id="a", role="Incoming"), dict(id="b", role="Outgoing")],
            [dict(id="p", **{"from": "a", "to": "b", "particle": "Fermion"})],
        )
    if kind == "energy":
        return ax.energy_levels(
            [dict(id="a", column="A", energy=1), dict(id="b", column="A", energy=3)]
        )
    raise AssertionError(kind)


KINDS = [
    "stem",
    "bar",
    "radar",
    "box",
    "violin",
    "raincloud",
    "range",
    "candle",
    "stream",
    "ternary",
    "parallel",
    "rgb",
    "hexbin",
    "mesh",
    "tricontour",
    "surface",
    "trisurf",
    "line3d",
    "scatter3d",
    "quiver3d",
    "sunburst",
    "energy",
    "feynman",
]


def test_pyplot_imshow_rgb_adds_an_image_to_the_current_axes(monkeypatch):
    from figgyplot import pyplot as plt

    with fg.Figure(backend="webgpu") as fig:
        monkeypatch.setattr(plt, "_current", fig)
        image = np.array([[[255, 0, 0], [0, 255, 0]]], dtype=np.uint8)
        artist = plt.imshow_rgb(image, id="rgb")
        assert artist.id == "rgb"
        assert "RgbImage" in fig.get_settings()["series"][0]["render_type"]


@pytest.mark.parametrize("kind", KINDS)
def test_chart_themes_layout_and_renderer_exports(kind, tmp_path):
    with fg.Figure(figsize=(4, 3), dpi=72, backend="native") as fig:
        populate(fig.axes[0], kind)
        images = set()
        for theme in fig.theme_names():
            fig.set_theme(theme).tight_layout()
            rgba = fig.render_rgba()
            assert rgba.shape == (216, 288, 4)
            assert (
                np.count_nonzero(np.any(rgba[:, :, :3] != rgba[0, 0, :3], axis=2)) > 30
            )
            images.add(hashlib.sha256(rgba.tobytes()).hexdigest())
        assert len(images) == len(fig.theme_names())
        fig.savefig(tmp_path / "chart.svg", scale=2)
        fig.savefig(tmp_path / "chart.pdf", scale=2)
        assert "<svg" in (tmp_path / "chart.svg").read_text()
        assert (tmp_path / "chart.pdf").read_bytes().startswith(b"%PDF-")
        state = fig.get_settings()
        fig.apply_settings(state)
        assert fig.get_settings() == state


@pytest.mark.parametrize("kind", KINDS)
def test_notebook_source_manifest_and_edit_replay(kind):
    with fg.Figure(
        figsize=(4, 3), dpi=72, backend="webgpu", retain_notebook_data=True
    ) as fig:
        populate(fig.axes[0], kind)
        fig.set_theme("midnight").tight_layout()
        state = fig.get_settings()
        exec(fig.to_code(), {"fig": fig})
        assert fig.get_settings() == state
        manifest, buffers = fig._native.payload()
        assert len(manifest) == len(buffers)
        assert all(item["bytes"] == len(data) for item, data in zip(manifest, buffers))
        assert all(
            item["dtype"] in ("float32", "float64", "uint32") for item in manifest
        )


def test_float32_input_is_preserved_without_changing_original():
    from figgyplot.figure import _array

    for dtype, expected in [
        ("float16", "float32"),
        ("float32", "float32"),
        ("float64", "float64"),
        ("int16", "float32"),
        ("int32", "float64"),
        ("uint8", "float32"),
    ]:
        original = np.arange(8, dtype=dtype)
        array = _array(original)
        assert str(array.dtype) == expected
        if dtype in ("float32", "float64"):
            assert array is original
    with fg.Figure(backend="webgpu", retain_notebook_data=True) as fig:
        fig.axes[0].plot(np.arange(8, dtype=np.float32))
        manifest, buffers = fig._native.payload()
        assert [m["dtype"] for m in manifest] == ["float32", "float32"]
        assert sum(map(len, buffers)) == 8 * 4 * 2


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_sunburst_child_inspection_and_style_replay_keep_destination_values(backend):
    def nodes(n):
        return [
            dict(
                label="Root",
                children=[
                    dict(label="First", value=2 * n),
                    dict(label="Second", value=n),
                ],
            )
        ]

    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        source.axes[0].sunburst(nodes(1))
        target.axes[0].sunburst(nodes(10))
        owner = source.editor_properties("bounded/series/slice_1_1")
        assert owner["target"] == "slice_1_1"
        source.edit_property(
            owner["id"],
            "Slice/label",
            "Edited child",
            expected_revision=source.revision,
        )
        assert (
            source.get_settings()["radial"]["slices"][0]["children"][1]["label"]
            == "Edited child"
        )
        exec(source.to_code(), {"fig": target})
        children = target.get_settings()["radial"]["slices"][0]["children"]
        assert [v["value"] for v in children] == [20, 10]
        assert children[1]["label"] == "Edited child"
        assert "33" in children[1]["text"]
        if backend == "native":
            assert target.to_png().startswith(b"\x89PNG")


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_energy_axes_and_secondary_x_ownership(backend):
    with fg.Figure(backend=backend) as fig:
        populate(fig.axes[0], "energy")
        axis = fig.get_settings()["config"]["left_y"]
        assert axis["min"] < 1 and axis["max"] > 3
    with fg.Figure(backend=backend) as fig:
        a = fig.axes[0]
        a.plot([0, 1], [1, 2])
        before = fig.get_settings()["config"]["bottom_x"].copy()
        twin = a.twiny()
        twin.plot([100, 200], [1, 2])
        twin.set_xlim(50, 250)
        twin.set_xlabel("Secondary X")
        state = fig.get_settings()
        o = state["config"]["overlays"][0]
        assert [o["x_axis"][key] for key in ("min", "max")] == [50, 250]
        assert (
            "".join(v["text"] for v in o["x_axis"]["title_option"]["text"]["segments"])
            == "Secondary X"
        )
        assert state["config"]["bottom_x"] == before


@pytest.mark.parametrize("kind", KINDS)
def test_native_and_notebook_initial_domains_match(kind):
    with fg.Figure(backend="native", id="parity") as native, fg.Figure(
        backend="webgpu", id="parity"
    ) as browser:
        for fig in (native, browser):
            populate(fig.axes[0], kind)

        def same(a, b):
            if isinstance(a, dict):
                assert a.keys() == b.keys()
                for key in a:
                    same(a[key], b[key])
            elif isinstance(a, list):
                assert len(a) == len(b)
                for x, y in zip(a, b):
                    same(x, y)
            elif isinstance(a, float):
                assert a == pytest.approx(b, rel=1e-6, abs=1e-6)
            else:
                assert a == b

        same(native.get_settings(), browser.get_settings())


@pytest.mark.parametrize(
    "kind,reference,expected",
    [
        (
            "bar",
            dict(kind="histogram_bin", bin_index=1),
            dict(value=4, category_label="B"),
        ),
        ("box", dict(kind="histogram_bin", bin_index=1), dict(median=4, q1=3, q3=4.5)),
        (
            "range",
            dict(kind="histogram_bin", bin_index=1),
            dict(start=2, end=4, position=1),
        ),
        (
            "mesh",
            dict(kind="mesh_triangle", triangle_index=0),
            dict(vertices=[0, 1, 2], values=[1, 2, 3]),
        ),
        (
            "rgb",
            dict(kind="matrix_cell", x_index=0, y_index=0),
            dict(red=255, green=0, blue=0),
        ),
        ("line3d", dict(kind="point", point_index=1), dict(x=1, y=1, z=2)),
        (
            "quiver3d",
            dict(kind="point", point_index=1),
            dict(x=1, y=1, z=1, u=0, v=1, w=1),
        ),
        ("ternary", dict(kind="point", point_index=0), dict(x=0.2, y=0.3, c=0.5)),
        ("parallel", dict(kind="point", point_index=0), dict(values=[1, 2, 3])),
        (
            "feynman",
            dict(kind="feynman_vertex", vertex_index=1),
            dict(id="b", role="Outgoing"),
        ),
    ],
)
def test_selected_new_chart_values_come_from_resident_sources(
    kind, reference, expected
):
    with fg.Figure(backend="native") as fig:
        populate(fig.axes[0], kind)
        state = fig.get_settings()
        reference = dict(reference, series_id=state["series"][0]["series_id"])
        state["config"]["picked_data"] = dict(refs=[reference])
        fig.apply_settings(state)
        details = json.loads(fig._native.selection_details_json())
        for key, value in expected.items():
            if isinstance(value, str):
                assert details[key] == value
            else:
                assert details[key] == pytest.approx(value)
        assert fig.info["rgba_readbacks"] == 0


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_three_dimensional_scatter_maps_and_z_axis_are_independent(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.scatter(
            [0, 1], [1, 2], [10, 20], c=[3, 8], s=[2, 4], label="Mapped", id="mapped"
        )
        ax.set_zlabel("Height")
        ax.set_ylabel("Y")
        ax.set_zlim(5, 25)
        ax.set_ylim_without_tick_auto(0, 3)
        cfg = fig.get_settings()["config"]
        assert [cfg["right_y"][key] for key in ("min", "max")] == [5, 25]
        assert cfg["right_y"]["title_option"]["visible"]
        assert (
            "".join(
                v["text"] for v in cfg["right_y"]["title_option"]["text"]["segments"]
            )
            == "Height"
        )
        if backend == "native":
            state = fig.get_settings()
            state["config"]["picked_data"] = {
                "refs": [{"kind": "point", "series_id": "mapped", "point_index": 1}]
            }
            fig.apply_settings(state)
            detail = json.loads(fig._native.selection_details_json())
            assert [detail[key] for key in ("z", "color_value", "size_value")] == [
                20,
                8,
                4,
            ]
        ax.set_zlabel("Height", visible=False)
        assert not fig.get_settings()["config"]["right_y"]["title_option"]["visible"]


@pytest.mark.parametrize("kind", ["box", "raincloud", "mesh"])
def test_composite_sources_are_isolated_and_released_on_close(kind):
    with fg.Figure(backend="native") as probe:
        baseline = probe.info["pool_used_bytes"]
        first = fg.Figure(backend="native")
        second = fg.Figure(backend="native")
        try:
            for fig in (first, second):
                populate(fig.axes[0], kind)
            before = second.to_png()
            used = probe.info["pool_used_bytes"]
            assert used > baseline
            first.close()
            assert second.to_png() == before
            assert baseline < probe.info["pool_used_bytes"] < used
            second.close()
            assert probe.info["pool_used_bytes"] == baseline
        finally:
            first.close()
            second.close()


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_inline_legacy_import_validates_before_publishing_columns(backend):
    import copy
    from figgyplot._native import default_bounded_json

    with fg.Figure(backend=backend) as fig:
        legacy = json.loads(default_bounded_json("categorical"))
        legacy.update(
            categories=[dict(id="a", label="A"), dict(id="b", label="B")],
            series=[
                dict(
                    id="old",
                    label="Legacy",
                    color=dict(r=0, g=0, b=1, a=1),
                    style=None,
                    values=[1, 3],
                )
            ],
            group_width=0.6,
        )
        saved = dict(fig.get_settings(), renderer_version="0.18.1", categorical=legacy)
        before = fig.get_settings()
        bad = copy.deepcopy(saved)
        bad["categorical"]["series"][0]["values"] = []
        with pytest.raises(ValueError):
            fig.apply_settings(bad)
        assert fig.get_settings() == before and fig.info["columns"] == 0
        fig.apply_settings(saved)
        state = fig.get_settings()
        assert "CategoryBars" in state["series"][0]["render_type"]
        assert [c["label"] for c in state["config"]["bottom_x"]["categories"]] == [
            "A",
            "B",
        ]
        assert state["config"]["bar_groups"]["group_width"] == pytest.approx(0.6)
        assert (
            state["config"]["left_y"]["min"] < 1
            and state["config"]["left_y"]["max"] > 3
        )
        if backend == "native":
            assert fig.to_png().startswith(b"\x89PNG")


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("kind", [kind for kind in KINDS if kind != "sunburst"])
def test_common_chart_family_keeps_the_cartesian_root_when_used_in_a_subplot(
    backend, kind
):
    # Sunburst uses a separate radial Figure; these are coordinate-series charts.
    with fg.Figure(backend=backend, grid=[["main", "right"]]) as fig:
        fig.axes[0].plot(
            np.array([0, 1], dtype=np.float32),
            np.array([0, 1], dtype=np.float32),
            id="base",
        )
        base = fig.get_settings()["series"][0]
        populate(fig.subplots["right"].axes, kind)
        if backend == "native":
            assert fig.render_rgba().shape == (600, 960, 4)
        state = fig.get_settings()
        assert state["series"][0] == base
        assert state["config"]["bottom_x"].get("categories") is None
        assert state["config"]["subplots"][0]["series"]
