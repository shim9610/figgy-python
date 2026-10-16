"""Real radial shader output, bounded data validation and style replay."""
import copy
import hashlib
import numpy as np
import pytest
import figgyplot as figgy


def make(values=(40, 25, 20, 15), **kwargs):
    fig = figgy.Figure(backend="native")
    try:
        fig.axes[0].pie(values, labels=["Search", "Direct", "Email", "Other"], **kwargs)
        fig.axes[0].set_title("Traffic share", fontsize=18)
        return fig
    except BaseException:
        fig.close()
        raise


def test_pie_donut_render_and_data_ownership():
    values = np.array([40., 25., 20., 15.])
    with make(values) as pie, make(inner_radius=0.5) as donut:
        values[:] = -100
        assert [s["value"] for s in pie.get_settings()["radial"]["slices"]] == [40, 25, 20, 15]
        a, b = pie.render_rgba(), donut.render_rgba()
        assert a.shape == b.shape == (600, 960, 4)
        assert np.count_nonzero(a != b) > 10_000
        assert pie.info["columns"] == donut.info["columns"] == 0
        assert pie.info["gpu_context_id"] == donut.info["gpu_context_id"]
        assert pie.render_rgba(scale=2).shape == (1200, 1920, 4)


def test_radial_invalid_edits_are_atomic_and_families_cannot_mix():
    with make(inner_radius=0.5) as fig:
        before, revision = fig.get_settings(), fig.revision
        for edit in [lambda: fig.set_radial_style(material="wood", depth=2),
                     lambda: fig.configure_radial(kind={"Donut": {"inner_radius": 0.99}}),
                     lambda: fig.configure_radial(slices={0: {"value": 100}}),
                     lambda: fig.configure_radial(slices={4: {"label": "Invalid"}}),
                     lambda: fig.axes[0].plot([0, 1], [0, 1]),
                     lambda: fig.axes[0].set_xlim(0, 2),
                     lambda: fig.axes[0].set_ylabel("Ignored"),
                     lambda: fig.axes[0].legend(),
                     lambda: fig.update("axis_left", color="red"),
                     lambda: fig.set_draw_style("sketch")]:
            with pytest.raises(ValueError): edit()
            assert fig.get_settings() == before and fig.revision == revision
        bad = copy.deepcopy(before)
        bad["radial"]["slices"][0]["value"] = -1
        with pytest.raises(ValueError): fig.apply_settings(bad)
        assert fig.get_settings() == before
    with figgy.Figure(backend="native") as fig:
        fig.axes[0].plot([0, 1], [0, 1])
        before = fig.get_settings()
        with pytest.raises(ValueError, match="separate Figure"): fig.axes[0].pie([1, 2])
        assert fig.get_settings() == before
    with figgy.Figure(backend="webgpu") as fig:
        fig.axes[0].pie([1, 2])
        fig.axes[0].set_title("Browser radial")
        assert fig.get_settings()["radial"]["title"] == "Browser radial"


@pytest.mark.parametrize("values", [[-1, 2], [0, 0], [1, float("nan")], [1]*65])
def test_invalid_radial_values(values):
    with figgy.Figure(backend="native") as fig:
        before = fig.get_settings()
        with pytest.raises(ValueError): fig.axes[0].pie(values)
        assert fig.get_settings() == before


def test_materials_are_actual_different_shader_outputs():
    with make(inner_radius=0.5, tilt=55, depth=0.16, shadow=True,
              inner_corner=0.045, outer_corner=0.045) as fig:
        hashes = set()
        for material in ["flat", "matte", "ceramic", "brushed_metal", "paper", "wood",
                         "satin_metal", "toon", "enamel", "hatch", "pearl"]:
            fig.set_radial_style(material=material, texture_strength=0.8)
            hashes.add(hashlib.sha256(fig.render_rgba().tobytes()).hexdigest())
        assert len(hashes) == 11
        assert fig.info["column_uploads"] == 0


def test_radial_code_replay_preserves_new_values_and_shared_device():
    with make(inner_radius=0.5, material="pearl", tilt=55, depth=0.16) as source, make() as replay:
        source.configure_radial(slices={0: {"explode": 0.08}})
        source.set_radial_style(texture_strength=0.8)
        code = source.to_code()
        assert "configure_radial" in code and "'value':" not in code
        exec(code, {"fig": replay})
        assert source.get_settings()["radial"] == replay.get_settings()["radial"]
        np.testing.assert_array_equal(source.render_rgba(), replay.render_rgba())
    with make(inner_radius=0.5, material="pearl") as source, make((10, 20, 30, 40)) as replay:
        exec(source.to_code(), {"fig": replay})
        assert [s["value"] for s in replay.get_settings()["radial"]["slices"]] == [10, 20, 30, 40]
        assert replay.get_settings()["radial"]["style"]["material"] == "Pearl"
    with figgy.Figure(backend="native") as source, figgy.Figure(backend="native") as replay:
        source.axes[0].pie([1, 1])
        replay.axes[0].pie([0, 2])
        assert source.select(600, 300)["index"] == 0
        exec(source.to_code(), {"fig": replay})
        assert [s["value"] for s in replay.get_settings()["radial"]["slices"]] == [0, 2]
        assert replay.get_settings()["radial"]["interaction"]["selected"] is None


def test_radial_pick_prepare_and_explicit_value_replacement():
    with figgy.Figure(backend="native") as fig:
        artist = fig.axes[0].pie([1, 1], labels=["First", "Second"])
        picked = fig.select(600, 300)
        assert picked["index"] == 0 and picked["label"] == "First" and picked["value"] == 1
        assert fig.selection_bounds() is None
        assert fig.info["rgba_readbacks"] == 0
        artist.set_slice(0, material="pearl")
        assert fig.get_settings()["radial"]["slices"][0]["style"]["material"] == "Pearl"
        artist.set_values([0, 2])
        assert fig.get_settings()["radial"]["interaction"]["selected"] is None
        assert fig.prepare()["ready"]
        assert fig.info["rgba_readbacks"] == 1
        assert fig.info["allocation_mode"] == "bounded"


def test_radial_style_replay_rejects_a_different_slice_count():
    with make() as source, figgy.Figure(backend="native") as destination:
        destination.axes[0].pie([1, 2, 3])
        before = destination.get_settings()
        with pytest.raises(ValueError, match="same slice count"):
            exec(source.to_code(), {"fig": destination})
        assert destination.get_settings() == before
