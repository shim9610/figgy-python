"""Scientific record input, ownership and actual diagram export contracts."""

import copy
from io import StringIO

import numpy as np
import pytest

import figgyplot as fg

LEVELS = '''Configuration,Term,J,g,Prefix,Level (eV),Suffix,Uncertainty (eV),Reference
"=""1s2""","=""1S""","=""0""",1,"=""[""","=""0.00000000""","=""]""","=""0.00000015""","=""L22715"""
"=""1s.2p""","=""1P*""","=""1""",3,"=""[""","=""21.2180227112""","=""]""","=""0.0000000016""","=""L22715"""
He II,Limit,,, ,24.587389,,0.000001,L22715
'''
LINES = """conf_i,term_i,J_i,conf_k,term_k,J_k,obs_wl_vac(nm),ritz_wl_vac(nm),unc_obs_wl,unc_ritz_wl,intens,Aki(s^-1),Acc,Type,tp_ref,line_ref
1s2,1S,0,1s.2p,1P*,1,,58.43339,,0.00001,100*,1.8e9,AAA,,T1,L1
"""


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_nist_csv_preserves_units_flags_and_transition_identity(backend, tmp_path):
    data = fg.read_nist(StringIO(LEVELS), StringIO(LINES))
    assert data.energy_unit == "eV"
    assert (data.wavelength_unit, data.wavelength_medium) == ("nm", "vac")
    assert data.levels[1]["energy"] == 21.2180227112
    assert data.levels[1]["prefix"] == "[" and data.levels[1]["suffix"] == "]"
    assert data.levels[1]["uncertainty"] == 1.6e-9
    assert data.transitions[0]["lower"] == data.levels[0]["id"]
    assert data.transitions[0]["upper"] == data.levels[1]["id"]
    assert data.transitions[0]["wavelength"] == 58.43339
    assert data.transitions[0]["intensity"] == "100*"
    before = copy.deepcopy(data)
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].energy_levels(data)
        state = fig.get_settings()
        body = state["series"][0]["render_type"]["EnergyLevels"]
        assert body["limits"][0]["energy"] == 24.587389
        assert (
            "".join(
                s["text"]
                for s in state["config"]["left_y"]["title_option"]["text"]["segments"]
            )
            == "Energy (eV)"
        )
        fig.set_theme("warm-paper").tight_layout()
        exec(fig.to_code(), {"fig": fig})
        if backend == "native":
            fig.savefig(tmp_path / "nist.svg")
            fig.savefig(tmp_path / "nist.pdf")
            assert "<svg" in (tmp_path / "nist.svg").read_text()
            assert (tmp_path / "nist.pdf").read_bytes().startswith(b"%PDF-")
    assert data == before


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_numpy_records_and_plain_labels_are_accepted_without_mutating_inputs(backend):
    vertices = [
        dict(
            id="a",
            role="Incoming",
            at=np.array([0, 0], dtype=np.float32),
            label="electron",
        ),
        dict(id="b", role="Outgoing", at=[1, 1]),
    ]
    edges = [dict(id="p", **{"from": "a", "to": "b"}, particle="Fermion", label="p")]
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].feynman(vertices, edges, direction="bottom-to-top")
        body = fig.get_settings()["series"][0]["render_type"]["Feynman"]
        assert body["vertices"][0]["at"] == [0, 0]
        assert body["layout"]["direction"] == "BottomToTop"
        assert (
            "".join(s["text"] for s in body["propagators"][0]["label"]["segments"])
            == "p"
        )
        assert isinstance(vertices[0]["at"], np.ndarray)
        assert edges[0]["label"] == "p"
        if backend == "native":
            assert fig.export("pdf").startswith(b"%PDF-")
    levels = np.array(
        [("a", "S", 0), ("b", "P", 3)],
        dtype=[("id", "U1"), ("column", "U1"), ("energy", "f4")],
    )
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].energy_levels(levels)
        assert (
            fig.get_settings()["series"][0]["render_type"]["EnergyLevels"]["levels"][1][
                "energy"
            ]
            == 3
        )


def test_record_validation_rolls_back_and_names_the_bad_reference():
    with fg.Figure(backend="webgpu") as fig:
        before = fig.get_settings()
        with pytest.raises(ValueError, match="endpoints"):
            fig.axes[0].feynman(
                [dict(id="a")],
                [dict(id="p", **{"from": "a", "to": "missing"}, particle="Photon")],
            )
        assert fig.get_settings() == before
        with pytest.raises(ValueError, match="missing.*column"):
            fig.axes[0].energy_levels([dict(id="a", energy=1)])
        assert fig.get_settings() == before


def test_nist_does_not_silently_drop_unmatched_lines_or_evaluate_formulas():
    bad = LINES.replace("1s.2p", "absent")
    with pytest.raises(ValueError, match="absent"):
        fg.read_nist(LEVELS, bad)
    data = fg.read_nist(LEVELS, bad, unmatched="skip")
    assert data.transitions == [] and data.unmatched_transitions == 1
    with pytest.raises(ValueError, match="numeric"):
        fg.read_nist(LEVELS.replace("24.587389", "=2+2"))


@pytest.mark.parametrize("kind", ["bar", "box", "radar"])
@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_coordinate_chart_named_styles_keep_sources_and_change_real_appearance(
    kind, backend
):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        if kind == "bar":
            ax.bar(["A", "B"], np.array([1, 2], dtype=np.float32))
        elif kind == "box":
            ax.boxplot([[1, 2, 3], [2, 4, 6]])
        else:
            ax.radar(["A", "B", "C"], [1, 2, 3])
        before = fig.get_settings()
        uploads = (
            fig.info["column_uploads"]
            if backend == "native"
            else dict(fig._native.columns)
        )
        pixels = fig.render_rgba() if backend == "native" else None
        artist = fig.artist(before["series"][0]["series_id"])
        assert len(artist.get_color()) == 4
        artist.set_linewidth(2)
        assert artist.get_linewidth() == pytest.approx(2)
        style = ax.chart.get_style()
        ax.chart.set_style(**style)
        ax.chart.set_style(linewidth=3)
        ax.chart.set_label_style(fontsize=10, color="red")
        after = fig.get_settings()
        assert [s["x_column"] for s in after["series"]] == [
            s["x_column"] for s in before["series"]
        ]
        assert [s["y_column"] for s in after["series"]] == [
            s["y_column"] for s in before["series"]
        ]
        assert (
            fig.info["column_uploads"] if backend == "native" else fig._native.columns
        ) == uploads
        expected_categories = (
            {"category_0": "Box 1", "category_1": "Box 2"}
            if kind == "box"
            else {"category_0": "A", "category_1": "B"}
        )
        if kind == "radar":
            expected_categories["category_2"] = "C"
        assert ax.chart.get_categories() == expected_categories
        if pixels is not None:
            assert not np.array_equal(pixels, fig.render_rgba())


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_energy_appearance_replay_preserves_destination_energies_and_line_metadata(
    backend,
):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig, offset in [(source, 1), (target, 100)]:
            fig.axes[0].energy_levels(
                [
                    dict(id="a", column="S", energy=offset),
                    dict(id="b", column="P", energy=offset + 3),
                ],
                transitions=[
                    dict(
                        id="t",
                        lower="a",
                        upper="b",
                        wavelength=offset + 500,
                        aki=offset * 1000,
                    )
                ],
            )
        source.set_theme("midnight")
        before = target.get_settings()
        identity = target.id
        exec(source.to_code(), {"fig": target})
        body = target.get_settings()["series"][0]["render_type"]["EnergyLevels"]
        assert [v["energy"] for v in body["levels"]] == [100, 103]
        assert body["transitions"][0]["wavelength"] == 600
        assert body["transitions"][0]["aki"] == 100000
        assert target.id == identity
        changed = source.get_settings()
        changed["series"][0]["render_type"]["EnergyLevels"]["levels"][0]["id"] = "other"
        checkpoint = target.get_settings()
        with pytest.raises(ValueError, match="record IDs"):
            target.apply_settings(changed, preserve_data=True)
        assert target.get_settings() == checkpoint


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_appearance_replay_rejects_category_shape_and_graph_topology_changes(backend):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        source.axes[0].bar(["A", "B"], [1, 2])
        target.axes[0].bar(["A", "B", "C"], [10, 20, 30])
        before = target.get_settings()
        with pytest.raises(ValueError, match="category IDs"):
            exec(source.to_code(), {"fig": target})
        assert target.get_settings() == before
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig, particle in [(source, "Photon"), (target, "Gluon")]:
            fig.axes[0].feynman(
                [dict(id="a"), dict(id="b")],
                [dict(id="p", **{"from": "a", "to": "b"}, particle=particle)],
            )
        before = target.get_settings()
        with pytest.raises(ValueError, match="topology"):
            exec(source.to_code(), {"fig": target})
        assert target.get_settings() == before


@pytest.mark.parametrize(
    "spectrum,count,lines", [("he_i", 59, 111), ("cu_i", 35, 69), ("ar_i", 43, 51)]
)
@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_actual_nist_exports_link_every_line_without_dropping_rows(
    spectrum, count, lines, backend
):
    from pathlib import Path

    folder = Path(__file__).parent / "data" / "nist"
    data = fg.read_nist(
        folder / (spectrum + "_levels.csv"), folder / (spectrum + "_lines.csv")
    )
    assert (
        len(data.levels) == count
        and len(data.transitions) == lines
        and len(data.limits) == 1
    )
    assert data.unmatched_transitions == 0
    assert all(
        t["lower"] in {l["id"] for l in data.levels}
        and t["upper"] in {l["id"] for l in data.levels}
        for t in data.transitions
    )
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].energy_levels(data)
        body = fig.get_settings()["series"][0]["render_type"]["EnergyLevels"]
        assert [v["energy"] for v in body["levels"]] == [
            v["energy"] for v in data.levels
        ]
        if backend == "native":
            assert "<svg" in fig.export("svg")
        else:
            widget = fig.widget()
            assert (
                widget.state["settings"]["series"][0]["render_type"]["EnergyLevels"][
                    "levels"
                ][0]["energy"]
                == data.levels[0]["energy"]
            )
