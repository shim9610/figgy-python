"""Readable Python export, shared by native and notebook editors (no GPU access)."""
from __future__ import annotations

import copy
import ast
from collections import Counter
import json
import keyword
import pprint


def _share_colors(code):
    """Name repeated literal colors without changing values or hiding settings."""
    tree = ast.parse(code)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        try:
            value = ast.literal_eval(node)
        except (ValueError, TypeError):
            continue
        if set(value) not in ({'r', 'g', 'b'}, {'r', 'g', 'b', 'a'}):
            continue
        if not all(type(v) in (int, float) for v in value.values()):
            continue
        key = tuple(sorted(value.items()))
        matches.append((node, key, value))
    counts = Counter(key for _, key, _ in matches)
    shared = {}; definitions = []
    for _, key, value in matches:
        if counts[key] < 2 or key in shared:
            continue
        index = len(shared) + 1
        name = f'_color{index}'
        while name in names:
            index += 1; name = f'_color{index}'
        names.add(name); shared[key] = name
        definitions.append(f'{name} = {value!r}')
    if not shared:
        return code
    # AST columns count UTF-8 bytes. Byte offsets preserve Korean/Greek text on
    # a line containing a styled run and its color keyword.
    data = code.encode('utf-8'); offsets = [0]
    for line in data.splitlines(keepends=True): offsets.append(offsets[-1] + len(line))
    edits = [(offsets[n.lineno-1]+n.col_offset,
              offsets[n.end_lineno-1]+n.end_col_offset, shared[key].encode())
             for n,key,_ in matches if key in shared]
    for start,end,value in sorted(edits,reverse=True): data = data[:start] + value + data[end:]
    return '\n'.join(definitions) + '\n\n' + data.decode('utf-8')


def compact_config(config, defaults):
    """Drop only known default leaves; keep topology and every panel rectangle."""
    from .figure import _diff
    from ._native import default_colorbar_json
    patch = _diff(defaults, config)
    patch['chart_area'] = copy.deepcopy(config['chart_area'])
    if config.get('colorbar') is not None:
        patch['colorbar'] = _diff(json.loads(default_colorbar_json()), config['colorbar'])
    if config.get('subplots'):
        patch['subplots'] = copy.deepcopy(config['subplots'])
        for panel in patch['subplots']:
            panel['config'] = compact_config(panel['config'], defaults)
    if config.get('overlays'):
        patch['overlays'] = copy.deepcopy(config['overlays'])
        for overlay in patch['overlays']:
            overlay['y_axis'] = _diff(defaults['left_y'], overlay['y_axis'])
            if overlay.get('legend') is not None:
                overlay['legend'] = _diff(defaults['legend'], overlay['legend'])
    return patch


def expand_config(patch, defaults):
    """Resolve compact settings against defaults, never the target's edited state."""
    from .figure import _merge
    from ._native import default_colorbar_json
    config = _merge(copy.deepcopy(defaults), patch)
    if patch.get('colorbar') is not None:
        config['colorbar'] = _merge(json.loads(default_colorbar_json()), patch['colorbar'])
    for panel in config.get('subplots', []):
        panel['config'] = expand_config(panel['config'], defaults)
    for overlay in config.get('overlays', []):
        overlay['y_axis'] = _merge(copy.deepcopy(defaults['left_y']), overlay['y_axis'])
        if overlay.get('legend') is not None:
            overlay['legend'] = _merge(copy.deepcopy(defaults['legend']), overlay['legend'])
    return config


def settings_to_code(settings, defaults, dpi=120, variable="fig", *, compact=True, mode='api'):
    if type(compact) is not bool:
        raise ValueError('compact must be boolean')
    if mode not in ('api','exact'):
        raise ValueError('mode must be api or exact')
    if mode=='api' and compact:
        from ._api_codegen import settings_to_api_code
        return settings_to_api_code(settings,defaults,dpi,variable)
    from .figure import _code_tree, _diff, _segments, _text
    from ._native import fitted_chart_title_margin, font_family_available

    if not isinstance(variable, str) or not variable.isidentifier() or keyword.iskeyword(variable):
        raise ValueError("variable must be a Python identifier")
    if type(compact) is not bool:
        raise ValueError('compact must be boolean')
    if isinstance(settings, str):
        settings = json.loads(settings)
    if isinstance(defaults, str):
        defaults = json.loads(defaults)
    segments_function = "_text_segments" if variable == "text_segments" else "text_segments"
    def formatted(value):
        return pprint.pformat(_code_tree(value, segments_function) if compact else value,
                              width=96, sort_dicts=False)
    def finish(code):
        if compact:
            code = _share_colors(code)
        if f'{segments_function}(' in code:
            alias = '' if segments_function == 'text_segments' else f' as {segments_function}'
            code = f'from figgyplot import text_segments{alias}\n\n' + code
        return code
    identity = settings.get('identity')
    def with_identity(code):
        if identity is not None:
            code += f"{variable}.configure(identity={formatted(identity)})\n"
        return finish(code)
    config = settings['config']
    advanced = config.get('subplots') or config.get('overlays') or config.get('polar') or config.get('annotations')
    for spec in settings['series']:
        style = next(iter(spec['render_type'].values()))
        advanced = advanced or 'Vector' in spec['render_type'] or any(
            style.get('scatter', {}).get(key) is not None for key in ('point_color_map', 'point_size_map'))
        advanced = advanced or style.get('line', {}).get('fill') is not None or style.get('line', {}).get('interpolation', 'Linear') != 'Linear'
    if advanced:
        document = copy.deepcopy(settings)
        if compact:
            document['config'] = compact_config(config, defaults)
        reset = ', reset=True' if compact else ''
        return finish(f"# Apply the complete document to an existing Figure with matching source columns.\n"
                f"# Source arrays stay resident; panels, layers and references commit together.\n"
                f"{variable}.apply_settings({formatted(document)}{reset})\n")
    for kind in ('categorical', 'boxplot', 'radar'):
        if settings.get(kind) is not None:
            chart = copy.deepcopy(settings[kind])
            chart['hovered'] = chart['selected'] = None
            chart['decorations']['selected'] = None
            chart['expected_categories'] = [c['id'] for c in chart['categories']]
            chart['expected_series'] = [s['id'] for s in chart['series']]
            chart['series'] = {s['id']: {k: v for k, v in s.items() if k not in ('id', 'values')} for s in chart['series']}
            if compact:
                from ._native import default_bounded_json
                chart = _diff(json.loads(default_bounded_json(kind)), chart)
                chart['reset'] = True
            args = formatted(chart)
            canvas = formatted({'chart_area': settings['config']['chart_area']})
            return with_identity(f"# Apply to an existing {kind} chart with matching category/series IDs and DPI.\n"
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
        if compact:
            from ._native import default_radial_json
            chart = _diff(json.loads(default_radial_json()), chart)
            chart['reset'] = True
        args = formatted(chart)
        canvas = formatted({"chart_area": settings["config"]["chart_area"]})
        return with_identity(f"# Apply to an existing pie/donut with the same slice count and DPI.\n"
                f"# Existing category values are preserved.\n"
                f"{variable}.configure(config={canvas})\n"
                f"{variable}.configure_radial(expected_slices={len(slices)}, **{args})\n")
    cfg = settings["config"]
    modeled = copy.deepcopy(defaults)
    lines = [f"# Apply to the existing {variable} with the same plotted series.",
             f"ax = {variable}.axes[0]" if variable != "ax" else "_ax = ax.axes[0]"]
    # A resident field cannot temporarily lose its required colorbar while
    # replay resets the rest of the document to defaults.
    if cfg.get("colorbar") is not None:
        modeled["colorbar"] = copy.deepcopy(cfg["colorbar"])
        reset = formatted({"colorbar": cfg["colorbar"]})
        lines.append(f"{variable}.configure(config={reset}, reset=True)")
    else:
        lines.append(f"{variable}.configure(reset=True)")
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
            literal = formatted(value)
            lines.append(f"    {key}=" + literal.replace("\n", "\n    ") + ",")
        lines.append(")")

    # Restore advanced series styling before rebuilding the legend so ordinary
    # labels and renderer-generated symbols need no serialized segment list.
    if series:
        lines += ["", "# Preserve advanced series styling."]
        configure({"series": series})
    lines.append(f"{axis}.legend(visible={cfg['legend']['visible']!r})")
    from ._native import rebuild_legend_json
    colorbar = modeled.get("colorbar")
    modeled["legend"]["content"] = json.loads(rebuild_legend_json(
        json.dumps(settings["series"]), json.dumps(modeled["legend"]["content"]),
        json.dumps(colorbar["colormap"]) if colorbar else None))
    modeled["legend"]["visible"] = cfg["legend"]["visible"]

    # Advanced geometry and rich text remain ordinary Python values.
    # No escaped JSON, data uploads or private renderer IDs are emitted.
    residual = _diff(modeled, cfg)
    residual["chart_area"] = copy.deepcopy(cfg["chart_area"])
    lines += ["", "# Preserve advanced layout."]
    configure({"config": residual})
    code = "\n".join(lines) + "\n"
    return with_identity(code)
