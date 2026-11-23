#!/usr/bin/env python3
"""Generate a field-level inventory from typed, accepted editor documents.

This is an exposure inventory, not a claim that every field has a pixel test.
Run with the built wheel installed. --check fails on undocumented catalog changes.
"""
import argparse
import csv
import io
from pathlib import Path

import figgyplot as fg


def build(fig, case):
    ax = fig.axes[0]
    if case == "line":
        ax.plot([0, 1, 2], [1, 3, 2], marker="o", id="signal")
    elif case == "mapped_points":
        ax.scatter([0, 1, 2], [1, 3, 2], c=[2, 4, 3], s=[4, 8, 6], id="signal")
    elif case == "histogram":
        ax.hist([0, 1, 1, 2], id="signal")
    elif case == "errors":
        ax.errorbar([0, 1, 2], [1, 3, 2], yerr=[.1, .2, .3], id="signal")
    elif case == "contour":
        ax.contour([[0, 1], [2, 3]], levels=[.5, 1.5, 2.5], id="signal")
    elif case == "field":
        ax.imshow([[0, 1], [2, 3]], id="signal")
    elif case == "vector_points":
        ax.quiver([0, 1], [1, 2], [2, 1], [1, 3], id="signal")
    elif case == "vector_grid":
        ax.quiver([0, 1], [1, 2], [[1, 2], [3, 4]], [[2, 1], [4, 3]], values=[[1, 3], [2, 4]], id="signal")
    elif case == "polar":
        ax.plot([0, 90, 180], [1, 2, 1], id="signal"); ax.set_polar()
    elif case == "panels":
        for name in ("left", "right"):
            fig.subplots[name].axes.plot([0, 1], [1, 2], id=name+"/signal")
        fig.subplots["right"].axes.twinx(id="secondary").plot([0, 1], [3, 4], id="secondary/data")
        fig.subplots["right"].axes.inset_axes([.25, .15, .7, .7], id="zoom").subplot.set_inset_marker()
    elif case in ("radial", "radial_split"):
        ax.pie([3, 2, 1])
        if case=="radial_split":
            import copy
            child=copy.deepcopy(fig.get_settings()['radial']['slices'][0]);child.update(value=1,label='Detail A')
            other=copy.deepcopy(child);other.update(value=2,label='Detail B')
            fig.configure_radial(split={'slice_index':0,'children':[child,other],'kind':'Pie'})
    elif case == "categorical":
        ax.bar(["A", "B"], [3, 5])
    elif case == "boxplot":
        ax.boxplot([[1, 2, 3], [2, 4, 6]])
    elif case == "energy":
        diagram = ax.energy_levels(
            [{"id": "g", "column": "S", "energy": 0}, {"id": "e", "column": "P", "energy": 3}],
            transitions=[{"id": "t", "lower": "g", "upper": "e", "wavelength": 530}],
            id="spectrum",
        )
        diagram.set_wavelength_colors()
        diagram.set_wavelength_labels(unit="nm", decimals=1)
        diagram.transition("t").set_color("red")
    elif case == "range_links":
        bars = ax.range_bars([0, 1], [0, 2], [1, 3], labels=["A", "B"], timeline=True,
                             progress=[.2, .75], id="tasks")
        bars.set_connector()
        ax.yaxis.set_category_window(-.5, 1.5)
        ax.range_links(bars, [(0, 1)], id="dependencies")
    else:
        ax.radar(["A", "B", "C"], [[2, 3, 4]])
    if case != "panels":
        ax.text(.3, .4, "Text", coords="ratio", id="text")
        ax.arrow(.2, .2, .2, .2, coords="ratio", id="arrow")
        if case not in ("polar", "radial", "radial_split", "radar"):
            ax.axhline(1, id="reference"); ax.axvspan(0, .5, id="band")


def rows():
    inventory = set()
    for case in ("line", "mapped_points", "histogram", "errors", "contour", "field", "vector_points", "vector_grid", "polar", "panels", "radial", "radial_split", "categorical", "boxplot", "radar", "range_links", "energy"):
        with fg.Figure(backend="webgpu", id="inventory", **({"grid": [["left", "right"]]} if case == "panels" else {})) as fig:
            build(fig, case)

            def collect():
                for owner in fig.editor_properties():
                    for field in owner["fields"]:
                        inventory.add((case, owner["id"], field["id"], field["path"], field["kind"],
                                       'Editor::catalog_properties / specialized form', 'webgpu.js::catalogProperties / properties',
                                       "Figure.edit_property", "group behavior + code replay"))

            def command(owner, field, value):
                fig.edit_property(owner, field, value, expected_revision=fig.revision)

            collect()
            # Materialise omitted optional structures using the public command
            # layer, so their nested fields are part of the inventory too.
            enable = {"Area fill/enabled", "Contours/show_labels", "Contours/level_colors",
                      "Contour labels/background", "Series style/custom", "Slice labels/custom_labels",
                      "Slice labels/custom_label_format", "Slice labels/custom_label_color", "Polar coordinates/limit_sector"}
            for _ in range(3):
                for owner in fig.editor_properties():
                    for field in owner["fields"]:
                        if (field["id"] in enable or "/override/" in field["id"]) and field["value"] is False:
                            command(owner["id"], field["id"], True)
                        elif field["id"] in {"Marker palette/add", "Marker point overrides/add", "Error-bar palette/add", "Error-bar point overrides/add", "Label positions/add"}:
                            # One representative row suffices: row indices are
                            # data, not an unlimited number of distinct controls.
                            if not any(v["id"].startswith(field["group"]+"/remove/") for v in owner["fields"]):
                                command(owner["id"], field["id"], True)
                collect()
            for owner in fig.editor_properties():
                for field in owner["fields"]:
                    changes={"Vectors/scale_mode":"Data", "Polar coordinates/interpolation_mode":"Arc", "Pie / donut/mode":"Donut", "Detail shape/mode":"Donut"}
                    if case == "radar" and field["id"] == "Polar coordinates/interpolation_mode":
                        continue  # Radar requires straight edges.
                    if field["id"] in changes:
                        command(owner["id"],field["id"],changes[field["id"]])
            if case in ("categorical", "boxplot"):
                chart = fig.axes[0].chart
                series_id = next(iter(chart.get_series()))
                category_id = next(iter(chart.get_categories()))
                chart.cell(category_id, series_id).set_color("red").set_style(outline=True)
            collect()
            if case=="line":
                owner=next(v for v in fig.editor_properties() if v['target']=='tick_labels_bottom')
                field=next(v for v in owner['fields'] if v['path'].endswith('/format'))
                command(owner['id'],field['id'],'Timestamp')
                for prop,value in [('timezone/mode','FixedOffsetMinutes'),('label/mode','Pattern'),('fractional/mode','Fixed')]:
                    command(owner['id'],field['id']+'/Timestamp/'+prop,value)
                collect()
                for prop, value in [('step/mode', 'Week'), ('label/mode', 'Relative'), ('label/mode', 'Custom')]:
                    command(owner['id'], field['id']+'/Timestamp/'+prop, value)
                    collect()
    grouped = {}
    for row in inventory:
        grouped.setdefault(row[1:], set()).add(row[0])
    return [(";".join(sorted(cases)), *route) for route, cases in sorted(grouped.items())]


def render():
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("fixture", "object_id", "property_id", "ssot_pointer", "input_kind", "native_adapter", "browser_adapter", "python_command", "regression_scope"))
    writer.writerows(rows())
    return stream.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/EDITOR_CONTROLS.csv"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = render()
    if args.check:
        if args.output.read_text() != result:
            raise SystemExit("Editor control inventory changed; regenerate and review the field-level diff.")
    else:
        args.output.write_text(result)
