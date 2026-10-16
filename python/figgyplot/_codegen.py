"""Readable Python export, shared by native and notebook editors (no GPU access)."""
from __future__ import annotations

import copy
import json
import keyword
import pprint


def settings_to_code(settings, defaults, dpi=120, variable="fig"):
    from .figure import _code_tree, _diff, _segments, _text
    from ._native import fitted_chart_title_margin, font_family_available

    if not isinstance(variable, str) or not variable.isidentifier() or keyword.iskeyword(variable):
        raise ValueError("variable must be a Python identifier")
    if isinstance(settings, str):
        settings = json.loads(settings)
    if isinstance(defaults, str):
        defaults = json.loads(defaults)
    for kind in ('categorical', 'boxplot'):
        if settings.get(kind) is not None:
            chart = copy.deepcopy(settings[kind])
            chart['hovered'] = chart['selected'] = None
            chart['decorations']['selected'] = None
            chart['expected_categories'] = [c['id'] for c in chart['categories']]
            chart['expected_series'] = [s['id'] for s in chart['series']]
            chart['series'] = {s['id']: {k: v for k, v in s.items() if k not in ('id', 'values')} for s in chart['series']}
            args = pprint.pformat(chart, width=96, sort_dicts=False)
            canvas = pprint.pformat({'chart_area': settings['config']['chart_area']})
            return (f"# Apply to an existing {kind} chart with matching category/series IDs and DPI.\n"
                    f"# Existing data values are preserved.\n"
                    f"{variable}.configure(config={canvas})\n"
                    f"{variable}.configure_bounded({kind!r}, **{args})\n")
    if settings.get("radial") is not None:
        chart = copy.deepcopy(settings["radial"])
        chart["interaction"] = {"hovered": None, "selected": None, "hover_progress": 0.0}
        chart["decorations"]["selected"] = None
        slices = {i: {key: value for key, value in item.items() if key != "value"}
                  for i, item in enumerate(chart.pop("slices"))}
        chart["slices"] = slices
        args = pprint.pformat(chart, width=96, sort_dicts=False)
        canvas = pprint.pformat({"chart_area": settings["config"]["chart_area"]})
        return (f"# Apply to an existing pie/donut with the same slice count and DPI.\n"
                f"# Existing category values are preserved.\n"
                f"{variable}.configure(config={canvas})\n"
                f"{variable}.configure_radial(expected_slices={len(slices)}, **{args})\n")
    segments_function = "_text_segments" if variable == "text_segments" else "text_segments"
    cfg = settings["config"]
    modeled = copy.deepcopy(defaults)
    lines = [f"# Apply to the existing {variable} with the same plotted series.",
             f"ax = {variable}.axes[0]" if variable != "ax" else "_ax = ax.axes[0]",
             f"{variable}.configure(reset=True)"]
    axis = "_ax" if variable == "ax" else "ax"
    if "draw_style" in cfg:
        draw_style = copy.deepcopy(cfg["draw_style"])
        mode = draw_style.pop("mode")
        options = ", ".join(f"{key}={value!r}" for key, value in draw_style.items())
        lines.append(f"{variable}.set_draw_style({mode!r}" + (f", {options}" if options else "") + ")")
        modeled["draw_style"] = copy.deepcopy(cfg["draw_style"])
    if settings.get("background") is not None:
        color = tuple(settings["background"][key] for key in "rgba")
        lines.append(f"{variable}.set_facecolor({color!r})")

    for key, method in (("chart_title", "set_title"), ("bottom_x", "set_xlabel"), ("left_y", "set_ylabel")):
        node = cfg[key] if key == "chart_title" else cfg[key]["title_option"]
        baseline = modeled[key] if key == "chart_title" else modeled[key]["title_option"]
        rich = node["text"]
        value = _text(rich)
        args = [repr(value)]
        baseline["text"]["segments"] = _segments(value)
        if rich.get("align", "Left") != baseline["text"].get("align", "Left"):
            args.append(f"align={rich['align'].lower()!r}")
            baseline["text"]["align"] = rich["align"]
        # Python's font sizes are points; the renderer/editor stores pixels.
        for field, prop, val in (("font_size", "fontsize", rich["font_size"] * 72 / dpi),
                                 ("font", "font", rich["font"]),
                                 ("color", "color", tuple(rich["color"][c] for c in "rgba"))):
            # The font setter rejects families that do not resolve; such a
            # font (e.g. typed in an editor) is restored by the patch below.
            if field == "font" and not font_family_available(val):
                continue
            if field == "font_size" or rich[field] != baseline["text"][field]:
                args.append(f"{prop}={val!r}")
                baseline["text"][field] = copy.deepcopy(rich[field])
        if node["visible"] != baseline["visible"]:
            args.append(f"visible={node['visible']!r}")
            baseline["visible"] = node["visible"]
        offset = (node["offset_x"], node["offset_y"])
        if offset != (baseline["offset_x"], baseline["offset_y"]):
            args.append(f"offset={offset!r}")
            baseline["offset_x"], baseline["offset_y"] = offset
        lines.append(f"{axis}.{method}({', '.join(args)})")

    # set_title derives the title band like the renderer's title helper;
    # model that, so the patch below restores a margin that differs from it.
    modeled["chart_title"]["top_margin"] = fitted_chart_title_margin(json.dumps(modeled, allow_nan=False))

    for dimension, keys in (("x", ("bottom_x", "top_x")), ("y", ("left_y", "right_y"))):
        primary = cfg[keys[0]]
        lines.append(f"{axis}.set_{dimension}lim({primary['min']!r}, {primary['max']!r})")
        for key in keys:
            modeled[key]["min"], modeled[key]["max"] = primary["min"], primary["max"]
        if primary["scale"] in ("Linear", "Logarithmic") and all(cfg[k]["scale"] == primary["scale"] for k in keys):
            scale = "log" if primary["scale"] == "Logarithmic" else "linear"
            lines.append(f"{axis}.set_{dimension}scale({scale!r})")
            for key in keys:
                modeled[key]["scale"] = primary["scale"]
                modeled[key]["major_spacing"] = 1.0 if scale == "log" else (primary["max"] - primary["min"]) / 5
    if cfg["grid"]["show_major_x"] == cfg["grid"]["show_major_y"]:
        visible = cfg["grid"]["show_major_x"]
        lines.append(f"{axis}.grid({visible!r})")
        modeled["grid"]["show_major_x"] = modeled["grid"]["show_major_y"] = visible

    series = {}
    for spec in settings["series"]:
        sid = spec["series_id"]
        patch = {k: copy.deepcopy(v) for k, v in spec.items()
                 if k not in ("series_id", "x_column", "y_column")}
        style = next(iter(patch["render_type"].values()))
        properties = {}
        colors = [(style[k], field) for k, field in
                  (("line", "line_color"), ("scatter", "point_color"), ("bar", "fill_color")) if k in style]
        if colors and all(node[field] == colors[0][0][colors[0][1]] for node, field in colors):
            color = colors[0][0][colors[0][1]]
            properties["color"] = tuple(color[c] for c in "rgba")
            for node, field in colors:
                del node[field]
        if "line" in style:
            line = style["line"]
            properties["linewidth"] = line.pop("line_width") * 72 / dpi
            properties["linestyle"] = {"Solid": "-", "Dash": "--", "Dot": ":", "DashDot": "-."}.get(line["line_style"], line["line_style"])
            del line["line_style"]
        if "scatter" in style:
            properties["markersize"] = style["scatter"].pop("point_size") * 144 / dpi
        if patch.get("label") is not None:
            label = patch["label"]
            value = _text(label)
            properties["label"] = value
            if label["segments"] == _segments(value):
                del label["segments"]
        if properties:
            args = ", ".join(f"{key}={value!r}" for key, value in properties.items())
            lines.append(f"{variable}.update({sid!r}, {args})")

        def compact(value):
            if not isinstance(value, dict):
                return value
            return {key: item for key, raw in value.items() if (item := compact(raw)) != {}}

        patch = compact(patch)
        if patch:
            series[sid] = patch

    def configure(options):
        lines.append(f"{variable}.configure(")
        for key, value in options.items():
            formatted = pprint.pformat(_code_tree(value, segments_function), width=96, sort_dicts=False)
            lines.append(f"    {key}=" + formatted.replace("\n", "\n    ") + ",")
        lines.append(")")

    # Restore advanced series styling before rebuilding the legend so ordinary
    # labels and renderer-generated symbols need no serialized segment list.
    if series:
        lines += ["", "# Preserve advanced series styling."]
        configure({"series": series})
    lines.append(f"{axis}.legend(visible={cfg['legend']['visible']!r})")
    from ._native import rebuild_legend_json
    modeled["legend"]["content"] = json.loads(rebuild_legend_json(
        json.dumps(settings["series"]), json.dumps(modeled["legend"]["content"])))
    modeled["legend"]["visible"] = cfg["legend"]["visible"]

    # Advanced geometry and rich text remain ordinary Python values.
    # No escaped JSON, data uploads or private renderer IDs are emitted.
    residual = _diff(modeled, cfg)
    residual["chart_area"] = copy.deepcopy(cfg["chart_area"])
    lines += ["", "# Preserve advanced layout."]
    configure({"config": residual})
    code = "\n".join(lines) + "\n"
    if f"{segments_function}(" in code:
        alias = "" if segments_function == "text_segments" else f" as {segments_function}"
        code = f"from figgyplot import text_segments{alias}\n\n" + code
    return code
