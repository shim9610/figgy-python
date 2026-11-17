"""Stable diagram handles, inspector defaults and scientific-data ownership."""

import copy
import pytest
import figgyplot as fg


def make(ax, kind):
    if kind == "energy":
        return ax.energy_levels(
            [
                dict(id="g", column="S", energy=0, label="ground"),
                dict(id="e", column="P", energy=3, label="excited"),
            ],
            transitions=[dict(id="t", lower="g", upper="e", label="line")],
            id="diagram",
        )
    return ax.feynman(
        [
            dict(id="a", role="incoming", label="electron"),
            dict(id="b", role="outgoing"),
        ],
        [dict(id="p", source="a", target="b", particle="fermion")],
        id="diagram",
    )


def body(fig):
    return next(iter(fig.get_settings()["series"][0]["render_type"].values()))


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("kind", ["energy", "feynman"])
def test_default_diagram_inspector_can_edit_style_and_label_without_changing_data(
    backend, kind
):
    with fg.Figure(backend=backend) as f:
        d = make(f.axes[0], kind)
        before = f.get_settings()
        uploads = f.info.get("column_uploads")
        owner = next(o for o in f.editor_properties() if o["target"] == d.id)
        field = (
            "Appearance/style/level/width"
            if kind == "energy"
            else "Appearance/style/width"
        )
        assert any(v["id"] == field for v in owner["fields"])
        f.edit_property(owner["id"], field, 4)
        assert d.get_linewidth() == pytest.approx(4 * 72 / f.dpi)
        after = f.get_settings()
        assert f.info.get("column_uploads") == uploads
        key = "levels" if kind == "energy" else "vertices"
        assert (
            body(f)[key] == next(iter(before["series"][0]["render_type"].values()))[key]
        )
        f.undo()
        assert f.get_settings() == before
        f.redo()
        assert f.get_settings() == after
        label = f"Appearance/{key}/0/label/plain_text"
        owner = next(o for o in f.editor_properties() if o["target"] == d.id)
        assert any(v["id"] == label for v in owner["fields"])
        f.edit_property(owner["id"], label, "Edited")
        assert (
            "".join(s["text"] for s in body(f)[key][0]["label"]["segments"]) == "Edited"
        )
        if backend == "native":
            assert f.export("svg").startswith("<?xml") or "<svg" in f.export("svg")


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_energy_handles_keep_ids_and_nist_records_and_replay(backend):
    with fg.Figure(backend=backend) as f:
        d = make(f.axes[0], "energy")
        assert f.artist("diagram") is d
        before = copy.deepcopy(body(f))
        d.set_color("red").set_linewidth(2)
        level = d.level("g")
        assert level.set_label(fg.TextRun("Ground", bold=True), fontsize=12) is level
        level.set_label_offset((2, 3))
        assert level.get_label_offset() == pytest.approx((2, 3))
        d.transition("t").set_label("Photon").set_endpoints("g", "e")
        assert [x["energy"] for x in body(f)["levels"]] == [
            x["energy"] for x in before["levels"]
        ]
        state = f.get_settings()
        state["series"][0]["render_type"]["EnergyLevels"]["levels"].reverse()
        f.apply_settings(state)
        level.set_energy(0.25)
        assert next(r for r in body(f)["levels"] if r["id"] == "g")["energy"] == 0.25
        level.select(label=True)
        assert (
            f.get_settings()["config"]["picked_data"]["refs"][0]["category_index"] == 1
        )
        checkpoint = f.get_settings()
        with pytest.raises(ValueError):
            d.transition("t").set_endpoints("missing", "e")
        with pytest.raises(ValueError):
            d.level("missing")
        with pytest.raises(AttributeError):
            level.set_style(color="blue")
        assert f.get_settings() == checkpoint
        exec(f.to_code(mode="exact"), {"fig": f})
        assert f.get_settings() == checkpoint


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_feynman_handles_support_geometry_inheritance_and_atomic_undo(backend):
    with fg.Figure(backend=backend, dpi=144) as f:
        d = make(f.axes[0], "feynman")
        d.set_layout(direction="bottom-to-top")
        v = d.vertex("a")
        v.set_position((0, 0)).set_label("Incoming").set_label_offset((2, 3))
        assert v.get_position() == [0, 0]
        p = d.propagator("p")
        assert (
            p.set_bend(20).set_particle("photon").set_color("red").set_linewidth(2) is p
        )
        assert p.get()["particle"] == "Photon" and p.get()["width_px"] == 4
        p.reset_style()
        assert p.get().get("color") is None and p.get().get("width_px") is None
        old = f.get_settings()
        v.set_position((0.1, 0.2))
        f.undo()
        assert f.get_settings() == old
        v.set_position(None)
        assert v.get_position() is None
        before = f.get_settings()
        with pytest.raises(ValueError):
            p.set_endpoints("a", "missing")
        with pytest.raises(ValueError):
            p.set_particle("typo")
        with pytest.raises(ValueError):
            v.set_position((float("nan"), 0))
        assert f.get_settings() == before
        p.select()
        assert (
            f.get_settings()["config"]["picked_data"]["refs"][0]["kind"]
            == "feynman_propagator"
        )
        if backend == "native":
            assert f.export("pdf").startswith(b"%PDF")


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_artist_setters_return_the_selected_handle(backend):
    with fg.Figure(backend=backend) as f:
        (line,) = f.axes[0].plot([0, 1], [1, 2])
        assert (
            line.set_color("red").set_linewidth(2).set_label("Signal").set(alpha=0.5)
            is line
        )


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_diagram_input_aliases_and_styled_labels_are_not_mutated(backend):
    vertices = [
        dict(
            id="a", role="incoming", label=fg.TextRun("e", fontsize=9, script="super")
        ),
        dict(id="b", role="outgoing"),
    ]
    edges = [
        dict(
            id="p",
            from_="a",
            target="b",
            particle="anti_fermion",
            momentum=dict(label=fg.TextRun("q", fontsize=8), side="right"),
        )
    ]
    before = copy.deepcopy((vertices, edges))
    with fg.Figure(backend=backend, dpi=144) as f:
        d = f.axes[0].feynman(vertices, edges)
        assert body(f)["vertices"][0]["label"]["segments"][0]["font_size"] == 18
        assert body(f)["propagators"][0]["particle"] == "AntiFermion"
        assert (
            body(f)["propagators"][0]["momentum"]["label"]["segments"][0]["font_size"]
            == 16
        )
        assert (vertices, edges) == before


@pytest.mark.parametrize("horizontal", [False, True])
@pytest.mark.parametrize("mode", ["grouped", "stacked", "percent_stacked"])
def test_category_fit_matches_native_after_mode_and_orientation_changes(
    horizontal, mode
):
    states = []
    for backend in ("native", "webgpu"):
        with fg.Figure(backend=backend) as f:
            ax = f.axes[0]
            ax.bar(["A", "B"], [[1, 9], [9, 1]])
            if backend == "webgpu":
                f._native.acknowledged()
            if horizontal:
                ax.chart.set_orientation("horizontal")
            ax.chart.set_mode(mode)
            (ax.set_xlim if horizontal else ax.set_ylim)(-100, 200)
            ax.fit()
            states.append((ax.get_xlim if horizontal else ax.get_ylim)())
    assert states[1] == pytest.approx(states[0])


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_box_fit_follows_current_orientation_after_transfer_release(backend):
    with fg.Figure(backend=backend) as f:
        ax = f.axes[0]
        ax.boxplot([[1, 2, 4], [2, 5, 9]])
        if backend == "webgpu":
            f._native.acknowledged()
        ax.chart.set_orientation("horizontal")
        ax.set_xlim(-10, 10)
        ax.fit()
        assert ax.get_xlim() == pytest.approx((0.6, 9.4))
        ax.chart.set_orientation("vertical")
        ax.set_ylim(-10, 10)
        ax.fit()
        assert ax.get_ylim() == pytest.approx((0.6, 9.4))


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_marker_and_label_style_chains_preserve_row_identity(backend):
    with fg.Figure(backend=backend) as f:
        d = make(f.axes[0], "feynman")
        v = d.vertex("a")
        assert (
            v.set_role("internal")
            .set_marker("blob", radius=5, facecolor="red")
            .set_label("q")
            .set_label_style(fontsize=12)
            is v
        )
        assert v.get()["id"] == "a" and v.get_label() == "q"
        checkpoint = f.get_settings()
        with pytest.raises(ValueError):
            v.set_marker("blob")
        with pytest.raises(ValueError):
            v.set_marker("dot", radius=5)
        assert f.get_settings() == checkpoint


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_diagram_opacity_and_momentum_are_editable_without_raw_settings(backend):
    with fg.Figure(backend=backend, dpi=144) as f:
        d = make(f.axes[0], "feynman")
        assert d.set(alpha=0.4).set_linewidth(2) is d
        assert body(f)["style"]["color"]["a"] == pytest.approx(0.4)
        p = d.propagator("p")
        assert (
            p.set_momentum(
                fg.TextRun("q", fontsize=9),
                side="right",
                reversed=True,
                label_offset=(3, -2),
            )
            is p
        )
        momentum = p.get()["momentum"]
        assert momentum["side"] == "Right" and momentum["reversed"]
        assert momentum["label_offset"] == [6, -4]
        assert momentum["label"]["segments"][0]["font_size"] == 18
        assert p.set_momentum().get().get("momentum") is None
        checkpoint = f.get_settings()
        with pytest.raises(TypeError):
            p.set_momentum("q", reversed="yes")
        assert f.get_settings() == checkpoint


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("kind", ["categorical", "boxplot", "radar"])
def test_series_name_editor_materializes_optional_rich_label_atomically(backend, kind):
    with fg.Figure(backend=backend) as f:
        ax = f.axes[0]
        if kind == "categorical":
            ax.bar(["A", "B"], [2, 4])
        elif kind == "boxplot":
            ax.boxplot([[1, 2, 3], [2, 4, 6]])
        else:
            ax.radar(["A", "B", "C"], [2, 4, 3])
        initial = f.get_settings()
        initial["series"][0]["label"] = None
        f.apply_settings(initial)
        before = f.get_settings()
        id = before["series"][0]["series_id"]
        owner = next(o for o in f.editor_properties() if o["id"] == "series/" + id)
        field = "Series/label/plain_text"
        assert next(v for v in owner["fields"] if v["id"] == field)["value"] == ""
        f.edit_property(owner["id"], field, "Measurements")
        assert f.artist(id).get_label() == "Measurements"
        assert (
            f.get_settings()["series"][0]["render_type"]
            == before["series"][0]["render_type"]
        )
        f.undo()
        assert f.get_settings() == before


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_feynman_editor_optional_overrides_and_momentum_use_valid_model_choices(
    backend,
):
    with fg.Figure(backend=backend) as f:
        d = f.axes[0].feynman(
            [dict(id="a"), dict(id="b")],
            [dict(id="p", source="a", target="b", particle="fermion")],
            id="diagram",
        )
        before = f.get_settings()
        owner = "series/diagram"

        def field(name):
            return next(
                v
                for o in f.editor_properties()
                if o["id"] == owner
                for v in o["fields"]
                if v["id"] == name
            )

        def edit(name, value):
            f.edit_property(owner, name, value)

        marker = "Appearance/vertices/0/marker"
        assert field(marker)["value"] == "Inherit"
        assert field(marker)["choices"] == [
            "Inherit",
            "Hidden",
            "Dot",
            "Cross",
            "CircledCross",
            "Blob",
        ]
        assert field("Appearance/vertices/0/role")["value"] == "Internal"
        with pytest.raises(ValueError):
            edit(marker, "Circle")
        assert f.get_settings() == before
        edit(marker, "Blob")
        edit(marker + "/Blob/radius_px", 6)
        edit(marker + "/Blob/fill/enabled", True)
        assert d.vertex("a").get()["marker"]["Blob"]["radius_px"] == 6
        edit(marker, "Inherit")
        assert d.vertex("a").get().get("marker") is None
        base = "Appearance/propagators/0/"
        edit(base + "momentum/enabled", True)
        assert field(base + "momentum/side")["choices"] == ["Left", "Right"]
        assert field(base + "momentum/side")["value"] == "Left"
        edit(base + "momentum/side", "Right")
        edit(base + "momentum/reversed", True)
        edit(base + "momentum/label/plain_text", "q")
        assert d.propagator("p").get()["momentum"]["reversed"]
        edit(base + "width_px/enabled", True)
        edit(base + "width_px/value", 4)
        edit(base + "color/enabled", True)
        edit(base + "color/value", dict(r=0.2, g=0.4, b=0.8, a=1))
        assert d.propagator("p").get()["width_px"] == 4
        edit(base + "width_px/enabled", False)
        edit(base + "color/enabled", False)
        assert d.propagator("p").get().get("width_px") is None
        edit(base + "bend/enabled", True)
        edit(base + "bend/value", 20)
        assert d.propagator("p").get()["bend"] == 20
        edit(base + "bend/enabled", False)
        edit(base + "momentum/enabled", False)
        assert d.propagator("p").get().get("momentum") is None
        while f.edit_history["can_undo"]:
            f.undo()
        assert f.get_settings() == before


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_new_diagram_labels_inherit_their_own_panel_typography(backend):
    with fg.Figure(backend=backend, grid=[["main", "right"]]) as f:
        state = f.get_settings()
        state["config"]["subplots"][0]["config"]["legend"]["content"]["font_size"] = 31
        f.apply_settings(state)
        d = f.subplots["right"].axes.feynman([dict(id="a")], [], id="diagram")
        owner = next(o for o in f.editor_properties() if o["id"] == "series/diagram")
        assert (
            next(
                v["value"]
                for v in owner["fields"]
                if v["id"] == "Appearance/vertices/0/label/font_size"
            )
            == 31
        )
        f.edit_property(owner["id"], "Appearance/vertices/0/label/plain_text", "E")
        assert d.vertex("a").get()["label"]["font_size"] == 31
        assert f.get_settings()["config"]["legend"]["content"]["font_size"] != 31


@pytest.mark.parametrize("backend", ["native", "webgpu"])
@pytest.mark.parametrize("kind", ["categorical", "boxplot"])
def test_cell_label_handles_edit_one_category_and_preserve_other_values(backend, kind):
    with fg.Figure(backend=backend) as f:
        ax = f.axes[0]
        if kind == "categorical":
            ax.bar(["A", "B"], [2, 4])
        else:
            ax.boxplot([[1, 2, 3], [2, 4, 6]])
        state = f.get_settings()
        sid = state["series"][0]["series_id"]
        before = next(iter(state["series"][0]["render_type"].values()))["labels"].get(
            "text", []
        )
        handle = ax.chart.cell("category_0", sid)
        assert handle.set_label("Measured").set_color("red") is handle
        assert handle.get_label() == "Measured"
        after = next(iter(f.get_settings()["series"][0]["render_type"].values()))[
            "labels"
        ]["text"]
        assert after[1:] == before[1:]
        assert handle.set_label(None).get_label() == ""
        assert ax.chart.series(sid).get_label() == f.artist(sid).get_label()


@pytest.mark.parametrize(
    "reference, record_id",
    [
        ({"kind": "histogram_bin", "bin_index": 0}, "g"),
        ({"kind": "point", "point_index": 0}, "t"),
        ({"kind": "value_label", "category_index": 0, "part": "level"}, "g"),
    ],
)
def test_native_energy_selection_resolves_public_source_records(reference, record_id):
    with fg.Figure(backend="native") as f:
        make(f.axes[0], "energy")
        source = body(f)
        f.axes[0].energy_levels(
            source["levels"], transitions=source["transitions"], id="alias"
        )
        state = f.get_settings()
        alias = state["series"][1]["render_type"]["EnergyLevels"]
        alias.update(source="diagram", levels=[], transitions=[], limits=[], bands=[])
        state["config"]["picked_data"] = {"refs": [dict(reference, series_id="alias")]}
        f.apply_settings(state)
        import json

        details = json.loads(f._native.selection_details_json())
        assert details["record"]["id"] == record_id
        assert details["series_id"] == "alias"
        assert f.info["column_uploads"] == 0
