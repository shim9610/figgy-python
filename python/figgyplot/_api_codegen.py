"""Export public plotting calls; keep exact, renderer-only recovery explicit.

The CPU state view executes the actual setters while compiling. Residual fields
are computed against their real effects rather than a second guessed model.
"""

import copy
import json
import keyword
import pprint
import numpy as np


def _points(pixels, dpi):
    """Shortest point constant that reproduces the exact renderer f32 length."""
    value = pixels * 72 / dpi
    for digits in range(10):
        candidate = round(value, digits)
        if np.float32(candidate * dpi / 72) == np.float32(pixels):
            return candidate
    return value


def _prune_empty(value):
    if not isinstance(value, dict):
        return value
    return {
        key: part for key, item in value.items() if (part := _prune_empty(item)) != {}
    }


def _color_literal(value):
    channels = tuple(value[k] for k in "rgba")
    encoded = tuple(round(c * 255) for c in channels)
    if all(np.float32(c) == np.float32(v / 255) for c, v in zip(channels, encoded)):
        return "#" + "".join(
            f"{c:02x}" for c in (encoded[:3] if encoded[3] == 255 else encoded)
        )
    return channels


def settings_to_api_code(settings, defaults, dpi=120, variable="fig"):
    from .figure import _diff, _text, _code_tree
    from ._matplotlib import _StateFigure
    from .ticker import (
        MultipleLocator,
        LogLocator,
        AutoMinorLocator,
        SignificantFormatter,
    )
    from ._charts import family
    from ._native import font_family_available, canonical_style_state_json

    if (
        not isinstance(variable, str)
        or not variable.isidentifier()
        or keyword.iskeyword(variable)
    ):
        raise ValueError("variable must be a Python identifier")
    settings = (
        json.loads(settings) if isinstance(settings, str) else copy.deepcopy(settings)
    )
    defaults = json.loads(defaults) if isinstance(defaults, str) else defaults
    if family(settings):
        return _bounded_api_code(settings, defaults, dpi, variable)
    model = _StateFigure(settings, defaults, dpi)
    ticker_classes = {
        "MultipleLocator": MultipleLocator,
        "LogLocator": LogLocator,
        "AutoMinorLocator": AutoMinorLocator,
        "SignificantFormatter": SignificantFormatter,
    }
    ticker_names = {
        name: ("_fg_" + name if variable == name else name) for name in ticker_classes
    }
    namespace = {
        variable: model,
        **{ticker_names[name]: cls for name, cls in ticker_classes.items()},
    }
    from .figure import text_segments

    segments_name = (
        "_fg_text_segments" if variable != "_fg_text_segments" else "_fg_text_runs"
    )
    namespace[segments_name] = text_segments
    lines = []

    def emit(statement, force=False):
        before = model._state
        exec(statement, namespace)
        after = model._state
        keys = ("config", "series", "background")
        changed = any(before.get(k) != after.get(k) for k in keys)
        if changed and not force and " = " not in statement:
            # Point conversions can differ in Python's final binary digit while
            # producing identical typed renderer state. Omit only proven native
            # no-ops, without rounding scientific data or weakening replay.
            original = json.loads(canonical_style_state_json(json.dumps(before)))
            updated = json.loads(canonical_style_state_json(json.dumps(after)))
            changed = any(original.get(k) != updated.get(k) for k in keys)
            if not changed:
                model._state = before
        if force or changed or " = " in statement:
            lines.append(statement)

    def color(value):
        return _color_literal(value)

    unit = 72 / dpi

    def fmt(value):
        return pprint.pformat(
            _code_tree(value, segments_name), width=96, sort_dicts=False
        )

    def rich_arg(rich):
        from .figure import _segments

        text = _text(rich)
        if rich["segments"] == _segments(text):
            return repr(text)
        return repr(
            _code_tree({"segments": rich["segments"]}, segments_name)["segments"]
        )

    def text(target, method, node):
        from .figure import _segments

        rich = node["text"]
        plain = _text(rich)
        rebuilt = _segments(plain)
        style = []
        for flag, prop, value in [
            ("bold", "fontweight", "bold"),
            ("italic", "fontstyle", "italic"),
        ]:
            if rich["segments"] and all(s.get(flag) is True for s in rich["segments"]):
                for segment in rebuilt:
                    segment[flag] = True
                style.append(f"{prop}={value!r}")
        args = [repr(plain) if rebuilt == rich["segments"] else rich_arg(rich)]
        if rebuilt == rich["segments"]:
            args += style
        handle = {
            "set_title": "title",
            "set_xlabel": "xaxis.label",
            "set_ylabel": "yaxis.label",
        }[method]
        baseline = eval(target + "." + handle, namespace)._node(model.get_settings())
        for field, prop, value in [
            ("font_size", "fontsize", _points(rich["font_size"], dpi)),
            ("color", "color", color(rich["color"])),
            ("font", "fontfamily", rich["font"]),
        ]:
            if field == "font" and not font_family_available(value):
                continue
            if rich[field] != baseline["text"][field]:
                args.append(f"{prop}={value!r}")
        if node["visible"] != baseline["visible"]:
            args.append(f"visible={node['visible']!r}")
        if rich.get("align") != baseline["text"].get("align") and "align" in rich:
            args.append(f"multialignment={rich['align'].lower()!r}")
        emit(f"{target}.{method}({', '.join(args)})")

    emit(f"{variable}.reset_style()", force=True)
    layout = settings["identity"].get("layout")
    if layout:
        args = ", ".join(
            f"{key}={layout[key]!r}"
            for key in ("placement", "row_weights", "column_weights", "gap")
        )
        emit(f"{variable}.set_layout({layout['grid']!r}, {args})", force=True)
    from ._matplotlib import canvas_size

    width, height = canvas_size(settings)
    emit(f"{variable}.set_size_inches({width / dpi!r}, {height / dpi!r})", force=True)
    if "background" in settings:
        emit(f"{variable}.set_facecolor({color(settings['background'])!r})")
    panels = [settings["config"]] + [
        p["config"] for p in settings["config"].get("subplots", [])
    ]
    for index, cfg in enumerate(panels):
        ax = "_ax" if variable != "_ax" else "_axes"
        if index:
            emit(
                f"{ax} = {variable}.subplots[{settings['identity']['panels'][index]['id']!r}].axes"
            )
        else:
            emit(f"{ax} = {variable}.axes[0]")
        area = cfg["chart_area"]
        if len(panels) > 1:
            bounds = (
                area["x"] / width,
                1 - (area["y"] + area["height"]) / height,
                area["width"] / width,
                area["height"] / height,
            )
            emit(f"{ax}.set_panel_position({bounds!r})", force=True)
        if cfg.get("draw_style"):
            options = dict(cfg["draw_style"])
            mode = options.pop("mode")
            args = ", ".join(f"{key}={value!r}" for key, value in options.items())
            emit(f"{ax}.set_draw_style({mode!r}" + (", " + args if args else "") + ")")
        # Express paired ranges/scales first, then preserve independent boundaries.
        for dim, key in [("x", "bottom_x"), ("y", "left_y")]:
            node = cfg[key]
            low, high = node["min"], node["max"]
            if node["inverted"]:
                low, high = high, low
            emit(f"{ax}.set_{dim}lim({low!r}, {high!r})", force=True)
            emit(
                f"{ax}.set_{dim}scale({'log' if node['scale'] == 'Logarithmic' else 'linear'!r})",
                force=True,
            )
        for dim, key in [("x", "bottom_x"), ("y", "left_y")]:
            node = cfg[key]
            if node["scale"] == "Linear":
                emit(
                    f"{ax}.{dim}axis.set_major_locator({ticker_names['MultipleLocator']}({node['major_spacing']!r}))"
                )
            elif node["scale"] == "Logarithmic":
                emit(
                    f"{ax}.{dim}axis.set_major_locator({ticker_names['LogLocator']}(base={10 ** node['major_spacing']!r}))"
                )
        text(ax, "set_title", cfg["chart_title"])
        text(ax, "set_xlabel", cfg["bottom_x"]["title_option"])
        text(ax, "set_ylabel", cfg["left_y"]["title_option"])
        emit(
            f"{ax}.title.set_layout_height({_points(cfg['chart_title']['top_margin'], dpi)!r})"
        )
        if cfg["chart_title"]["offset_x"] or cfg["chart_title"]["offset_y"]:
            emit(
                f"{ax}.title.set_offset({(_points(cfg['chart_title']['offset_x'], dpi), _points(cfg['chart_title']['offset_y'], dpi))!r})"
            )
        for side, key, dim in [
            ("bottom", "bottom_x", "x"),
            ("top", "top_x", "x"),
            ("left", "left_y", "y"),
            ("right", "right_y", "y"),
        ]:
            node = cfg[key]
            spine = f"{ax}.spines[{side!r}]"
            emit(
                f"{spine}.set(visible={node['line_visible']!r}, color={color(node['line_color'])!r}, linewidth={_points(node['line_width'], dpi)!r}, linestyle={dict(Solid='-', Dash='--', Dot=':', DashDot='-.').get(node['line_style'], node['line_style'])!r})"
            )
            if node["line_offset"]:
                emit(
                    f"{spine}.set_position(('outward', {_points(node['line_offset'], dpi)!r}))"
                )
            boundary = f"{ax}.secondary_{dim}axis({side!r})"
            axis = boundary + "." + dim + "axis"
            low, high = node["min"], node["max"]
            if node["inverted"]:
                low, high = high, low
            emit(f"{axis}.set_view_interval({low!r}, {high!r})")
            # Independent opposite-axis scales have no public setter yet.
            # Leave their scale and spacing together in the advanced residual.
            modeled_scale = eval(axis, namespace)._nodes(model.get_settings())[0][
                "scale"
            ]
            if node["scale"] == modeled_scale:
                if node["scale"] == "Linear":
                    emit(
                        f"{axis}.set_major_locator({ticker_names['MultipleLocator']}({node['major_spacing']!r}))"
                    )
                elif node["scale"] == "Logarithmic":
                    emit(
                        f"{axis}.set_major_locator({ticker_names['LogLocator']}(base={10 ** node['major_spacing']!r}))"
                    )
            emit(
                f"{axis}.set_minor_locator({ticker_names['AutoMinorLocator']}({node['minor_count'] + 1}))"
            )
            label = node["label_style"]
            notation = (
                {"Decimal": "plain", "Scientific": "scientific", "Power": "power"}.get(
                    label["format"]
                )
                if isinstance(label["format"], str)
                else None
            )
            if notation is not None:
                emit(
                    f"{axis}.set_major_formatter({ticker_names['SignificantFormatter']}({label['significant_digits']}, style={notation!r}))"
                )
            args = [
                f"labelsize={_points(label['font_size'], dpi)!r}",
                f"labelcolor={color(label['color'])!r}",
                f"labelfontfamily={label['label_font']!r}",
                f"label{side}={bool(label['label_visible'] and label['visible'])!r}",
            ]
            if node["tick"] != "None":
                args.append(
                    f"direction={dict(Inside='in', Outside='out', Both='inout')[node['tick']]!r}"
                )
            args.append(f"{side}={node['tick'] != 'None'!r}")
            emit(
                f"{boundary}.tick_params(which='major', length={_points(node['major_tick_length'], dpi)!r}, {', '.join(args)})"
            )
            emit(
                f"{boundary}.tick_params(which='minor', length={_points(node['minor_tick_length'], dpi)!r})"
            )
            emit(f"{axis}.set_layout_margin({_points(node['out_margin'], dpi)!r})")
            emit(
                f"{axis}.set_ticklabel_offset({(_points(label['label_offset_x'], dpi), _points(label['label_offset_y'], dpi))!r})"
            )
            if side in ("top", "right"):
                text(
                    boundary,
                    "set_xlabel" if dim == "x" else "set_ylabel",
                    node["title_option"],
                )
            title = axis + ".label"
            emit(
                f"{title}.set_offset({(_points(node['title_option']['offset_x'], dpi), _points(node['title_option']['offset_y'], dpi))!r})"
            )
        for dim in ("x", "y"):
            for which in ("major", "minor"):
                grid = cfg["grid"]
                prefix = which + "_" + dim
                emit(
                    f"{ax}.grid({grid['show_' + prefix]!r}, which={which!r}, axis={dim!r}, color={color(grid[prefix + '_color'])!r}, linewidth={_points(grid[prefix + '_width'], dpi)!r}, linestyle={dict(Solid='-', Dash='--', Dot=':', DashDot='-.').get(grid[prefix + '_style'], grid[prefix + '_style'])!r})"
                )
    # Stable lookup avoids the label-filtering/index association bug in legends.
    for spec in settings["series"]:
        artist = f"{variable}.artist({spec['series_id']!r})"
        body = next(iter(spec["render_type"].values()))
        if "line" in body:
            line = body["line"]
            emit(
                f"{artist}.set(color={color(line['line_color'])!r}, linewidth={_points(line['line_width'], dpi)!r}, linestyle={dict(Solid='-', Dash='--', Dot=':', DashDot='-.').get(line['line_style'], line['line_style'])!r})",
                force=True,
            )
            if line.get("interpolation", "Linear") != "Linear":
                draw = {
                    "StepPre": "steps-pre",
                    "StepPost": "steps-post",
                    "StepMid": "steps-mid",
                }[line["interpolation"]]
                emit(f"{artist}.set_drawstyle({draw!r})")
        if "scatter" in body:
            scatter = body["scatter"]
            from .figure import _MARKERS

            marker = {v: k for k, v in _MARKERS.items()}.get(
                scatter["point_shape"], scatter["point_shape"]
            )
            # Adding markers is a supported resident-Line transition. Emit it
            # before size, even when the source model already has that marker.
            emit(f"{artist}.set_marker({marker!r})", force=True)
            emit(
                f"{artist}.set_markersize({_points(scatter['point_size'] * 2, dpi)!r})",
                force=True,
            )
            emit(
                f"{artist}.set_facecolor({color(scatter['point_color'])!r})", force=True
            )
        if "bar" in body:
            bar = body["bar"]
            emit(f"{artist}.set_facecolor({color(bar['fill_color'])!r})", force=True)
            emit(f"{artist}.set_edgecolor({color(bar['border_color'])!r})", force=True)
            emit(
                f"{artist}.set_linewidth({_points(bar['border_width'], dpi)!r})",
                force=True,
            )
            emit(f"{artist}.set_baseline({bar['baseline']!r})", force=True)
            emit(
                f"{artist}.set_bar_width({bar['width_ratio']!r}, gap={_points(bar['gap_px'], dpi)!r})",
                force=True,
            )
            emit(
                f"{artist}.set_orientation({bar['orientation'].lower()!r})", force=True
            )
        if "err_style" in body:
            error = body["err_style"]
            emit(
                f"{artist}.set_errorbar_style(color={color(error['error_bar_color'])!r}, width={_points(error['error_bar_width'], dpi)!r}, capsize={_points(error['error_bar_cap_size'], dpi)!r}, capthick={_points(error['cap_width'], dpi)!r})",
                force=True,
            )
        if (
            "matrix" in body
            or body.get("scatter", {}).get("point_color_map")
            or body.get("style", {}).get("color_map")
        ):
            owner = next(
                a
                for a in model.axes
                if any(
                    s["series_id"] == spec["series_id"]
                    for s in a._owned_series(model.get_settings())
                )
            )
            bar = owner._config(settings)["colorbar"]
            if isinstance(bar["colormap"], str):
                name = {"GrayScale": "gray", "RdBu": "RdBu"}.get(
                    bar["colormap"], bar["colormap"].lower()
                )
                emit(f"{artist}.set_cmap({name!r})", force=True)
            emit(
                f"{artist}.set_clim({bar['axis']['min']!r}, {bar['axis']['max']!r})",
                force=True,
            )
        emit(
            f"{artist}.set_label({rich_arg(spec['label']) if spec.get('label') is not None else 'None'})",
            force=True,
        )
    for index, cfg in enumerate(panels):
        ax = "_ax" if variable != "_ax" else "_axes"
        if index:
            emit(
                f"{ax} = {variable}.subplots[{settings['identity']['panels'][index]['id']!r}].axes"
            )
        elif len(panels) > 1:
            emit(f"{ax} = {variable}.axes[0]")
        legend = cfg["legend"]
        rich = legend["content"]
        loc = {
            "TopLeft": "upper left",
            "TopRight": "upper right",
            "BottomLeft": "lower left",
            "BottomRight": "lower right",
        }[legend["corner"]]
        if legend["visible"] or rich["segments"]:
            baseline = eval(ax, namespace)._config(model.get_settings())["legend"]
            args = [] if legend["visible"] else ["False"]
            if legend["corner"] != baseline["corner"]:
                args.append(f"loc={loc!r}")
            if rich["font_size"] != baseline["content"]["font_size"]:
                args.append(f"fontsize={_points(rich['font_size'], dpi)!r}")
            if rich["font"] != baseline["content"]["font"] and font_family_available(
                rich["font"]
            ):
                args.append(f"prop={{'family': {rich['font']!r}}}")
            if rich["color"] != baseline["content"]["color"]:
                args.append(f"labelcolor={color(rich['color'])!r}")
            if legend["padding"] != baseline["padding"]:
                args.append(f"borderpad={legend['padding'] / rich['font_size']!r}")
            if legend["bg_color"] != baseline["bg_color"]:
                args.append(f"facecolor={color(legend['bg_color'])!r}")
            if legend["border_color"] != baseline["border_color"]:
                args.append(f"edgecolor={color(legend['border_color'])!r}")
            emit(f"{ax}.legend({', '.join(args)})")
        if legend["offset_x"] or legend["offset_y"]:
            emit(
                f"{ax}.get_legend().set_offset({(_points(legend['offset_x'], dpi), _points(legend['offset_y'], dpi))!r})"
            )
    # Guard fidelity: advanced fields must remain present, never disappear because
    # they lack a Matplotlib counterpart. Exact mode is the standalone full dump.
    from ._native import canonical_style_state_json

    restored = json.loads(
        canonical_style_state_json(json.dumps(model.get_settings(), allow_nan=False))
    )
    config_patch = _prune_empty(_diff(restored["config"], settings["config"]))
    series_patch = _prune_empty(
        {
            s["series_id"]: _diff(a, s)
            for a, s in zip(restored["series"], settings["series"])
            if a != s
        }
    )
    # Fields not represented by the public artist setters must be exported even
    # when the compiler's source-based view already contains them. Otherwise a
    # destination's edited mapping/override would silently leak into the replay.
    for spec in settings["series"]:
        kind, body = next(iter(spec["render_type"].items()))
        advanced = copy.deepcopy(body)
        for part, keys in [
            ("line", ("line_color", "line_width", "line_style", "interpolation")),
            ("scatter", ("point_color", "point_size", "point_shape")),
            (
                "bar",
                (
                    "fill_color",
                    "border_color",
                    "border_width",
                    "baseline",
                    "width_ratio",
                    "gap_px",
                    "orientation",
                ),
            ),
            (
                "err_style",
                (
                    "error_bar_color",
                    "error_bar_width",
                    "error_bar_cap_size",
                    "cap_width",
                ),
            ),
        ]:
            if part in advanced:
                for key in keys:
                    advanced[part].pop(key, None)
                if not advanced[part]:
                    advanced.pop(part)
        for binding in ("matrix", "components", "err_x", "err_y"):
            advanced.pop(binding, None)
        if advanced:
            patch = (
                series_patch.setdefault(spec["series_id"], {})
                .setdefault("render_type", {})
                .setdefault(kind, {})
            )
            from .figure import _merge

            _merge(patch, advanced)
    # Colorbar axis scale/spacing are independent of the plotted X/Y axes.
    # Keep their current exact API until a full public colorbar-axis adapter is
    # available, including logarithmic policy and independently moved bars.
    config_patch.pop("subplots", None)
    panel_patches = []
    restored_panels = [restored["config"]] + [
        p["config"] for p in restored["config"].get("subplots", [])
    ]
    for index, (baseline, cfg) in enumerate(zip(restored_panels, panels)):
        patch = config_patch if index == 0 else _prune_empty(_diff(baseline, cfg))
        if cfg.get("colorbar"):
            patch["colorbar"] = copy.deepcopy(cfg["colorbar"])
        if index and patch:
            panel_patches.append((index, patch))
    if config_patch or series_patch:
        parts = []
        if config_patch:
            parts.append("config=" + fmt(config_patch))
        if series_patch:
            parts.append("series=" + fmt(series_patch))
        lines.append("# Figgy-specific state without a public Matplotlib counterpart.")
        lines.append(f"{variable}.configure({', '.join(parts)})")
    for index, patch in panel_patches:
        panel_id = settings["identity"]["panels"][index]["id"]
        lines.append(
            f"{variable}.subplots[{panel_id!r}].axes.configure(**{fmt(patch)})"
        )
    used = [
        name + (" as " + ticker_names[name] if ticker_names[name] != name else "")
        for name in ticker_classes
        if any(ticker_names[name] + "(" in line for line in lines)
    ]
    imports = ("from figgyplot.ticker import " + ", ".join(used) + "\n") if used else ""
    if any(segments_name + "(" in line for line in lines):
        imports += f"from figgyplot import text_segments as {segments_name}\n"
    return (
        imports
        + "\n# Apply to existing matching panels and stable artist IDs; source arrays stay resident.\n"
        + f"with {variable}.batch_update():\n"
        + "\n".join("    " + line.replace("\n", "\n    ") for line in lines)
        + "\n"
    )


def _bounded_api_code(settings, defaults, dpi, variable):
    """Keep ordinary bounded appearance editable without exposing chart structs."""
    from ._charts import family
    from ._matplotlib import _StateFigure, canvas_size
    from .figure import _diff, _code_tree, _text, _segments, text_segments
    from ._native import canonical_style_state_json, font_family_available

    kind = family(settings)
    chart = copy.deepcopy(settings[kind])
    if kind == "radial":
        chart["interaction"] = dict(hovered=None, selected=None, hover_progress=0.0)
    else:
        chart["hovered"] = chart["selected"] = None
    chart["decorations"]["selected"] = None
    model = _StateFigure(settings, defaults, dpi)
    axname = "_ax" if variable != "_ax" else "_axes"
    runs = "_fg_text_segments" if variable != "_fg_text_segments" else "_fg_text_runs"
    namespace = {variable: model, runs: text_segments}
    lines = []
    unit = 72 / dpi

    def fmt(value):
        return pprint.pformat(_code_tree(value, runs), width=96, sort_dicts=False)

    def color(value):
        return _color_literal(value)

    def emit(code, force=False):
        before = model._state
        exec(code, namespace)
        if force or before != model._state or " = " in code:
            lines.append(code)

    emit(f"{axname} = {variable}.axes[0]")
    appearance = axname + ".chart"
    emit(f"{appearance}.reset_style()", force=True)
    width, height = canvas_size(settings)
    emit(f"{variable}.set_size_inches({width / dpi!r}, {height / dpi!r})", force=True)
    baseline = model.get_settings()[kind]
    shared = []
    if chart["font_size"] != baseline["font_size"]:
        shared.append(f"fontsize={_points(chart['font_size'], dpi)!r}")
    if chart["font_family"] != baseline["font_family"] and font_family_available(
        chart["font_family"]
    ):
        shared.append(f"fontfamily={chart['font_family']!r}")
    text_color = "label_color" if kind == "radial" else "text_color"
    if chart[text_color] != baseline[text_color]:
        shared.append(f"color={color(chart[text_color])!r}")
    if shared:
        emit(f"{appearance}.set_label_style({', '.join(shared)})")
    if chart["background"] != baseline["background"]:
        emit(f"{variable}.set_facecolor({color(chart['background'])!r})")
    if kind != "radar":
        material = {"BrushedMetal": "brushed_metal", "SatinMetal": "satin_metal"}.get(
            chart["style"]["material"], chart["style"]["material"].lower()
        )
        emit(f"{appearance}.set_material({material!r})")
    if kind == "radial":
        emit(f"{appearance}.set_startangle({-chart['start_angle_degrees']!r})")
        inner = (
            None if chart["kind"] == "Pie" else chart["kind"]["Donut"]["inner_radius"]
        )
        emit(f"{appearance}.set_inner_radius({inner!r})")
        for index, item in enumerate(chart["slices"]):
            emit(
                f"{appearance}.set_slice({index}, label={item['label']!r}, color={color(item['color'])!r}, explode={item['explode']!r})",
                force=True,
            )
    else:
        if kind in ("categorical", "boxplot"):
            emit(f"{appearance}.set_orientation({chart['direction'].lower()!r})")
            emit(f"{appearance}.set_group_width({chart['group_width']!r})")
            gap = chart["bar_gap" if kind == "categorical" else "box_gap"]
            emit(f"{appearance}.set_gap({_points(gap, dpi)!r})")
            if kind == "categorical":
                mode = {
                    "Grouped": "grouped",
                    "Stacked": "stacked",
                    "PercentStacked": "percent_stacked",
                }[chart["mode"]]
                emit(f"{appearance}.set_mode({mode!r})")
            xname, yname = (
                (chart["value_title"], chart["category_title"])
                if chart["direction"] == "Horizontal"
                else (chart["category_title"], chart["value_title"])
            )
            emit(f"{axname}.set_xlabel({xname!r})")
            emit(f"{axname}.set_ylabel({yname!r})")
        if chart.get("value_range") is not None:
            dimension = "x" if chart.get("direction") == "Horizontal" else "y"
            emit(f"{axname}.set_{dimension}lim({tuple(chart['value_range'])!r})")
        emit(f"{axname}.grid({chart['grid']!r})")
        emit(f"{axname}.legend({chart['legend']!r})")
        for item in chart["series"]:
            emit(
                f"{appearance}.set_series({item['id']!r}, label={item['label']!r}, color={color(item['color'])!r})",
                force=True,
            )
        for item in chart["categories"]:
            emit(
                f"{appearance}.set_category_label({item['id']!r}, {item['label']!r})",
                force=True,
            )
    title = chart.get("chart_title")
    if title is not None:
        rich = title["text"]
        plain = _text(rich)
        rebuilt = _segments(plain)
        styles = []
        for flag, prop, value in [
            ("bold", "fontweight", "bold"),
            ("italic", "fontstyle", "italic"),
        ]:
            if rich["segments"] and all(s.get(flag) is True for s in rich["segments"]):
                for segment in rebuilt:
                    segment[flag] = True
                styles.append(f"{prop}={value!r}")
        value = (
            repr(plain)
            if rebuilt == rich["segments"]
            else repr(_code_tree({"segments": rich["segments"]}, runs)["segments"])
        )
        args = [
            value,
            f"fontsize={_points(rich['font_size'], dpi)!r}",
            f"color={color(rich['color'])!r}",
            f"visible={title['visible']!r}",
        ]
        if rebuilt == rich["segments"]:
            args += styles
        if font_family_available(rich["font"]):
            args.append(f"fontfamily={rich['font']!r}")
        if "align" in rich:
            args.append(f"multialignment={rich['align'].lower()!r}")
        emit(f"{axname}.set_title({', '.join(args)})")
    restored = json.loads(
        canonical_style_state_json(json.dumps(model.get_settings(), allow_nan=False))
    )[kind]

    # Strip resident values before computing any residual. No data values may
    # appear in an appearance recipe, even when the destination data differ.
    def appearance_only(value):
        value = copy.deepcopy(value)
        if kind == "radial":
            value["slices"] = {
                i: {k: v for k, v in item.items() if k != "value"}
                for i, item in enumerate(value["slices"])
            }
        else:
            value["series"] = {
                item["id"]: {k: v for k, v in item.items() if k not in ("id", "values")}
                for item in value["series"]
            }
        return value

    residual = _prune_empty(_diff(appearance_only(restored), appearance_only(chart)))
    if residual:
        lines.append(
            "# Renderer-specific materials/decorations without Matplotlib equivalents."
        )
        if kind == "radial":
            lines.append(f"{variable}.configure_radial(**{fmt(residual)})")
        else:
            lines.append(f"{variable}.configure_bounded({kind!r}, **{fmt(residual)})")
    imports = (
        f"from figgyplot import text_segments as {runs}\n"
        if any(runs + "(" in line for line in lines)
        else ""
    )
    return (
        imports
        + "# Apply appearance to an existing chart with matching category/series IDs.\n"
        + f"with {variable}.batch_update():\n"
        + "\n".join("    " + line.replace("\n", "\n    ") for line in lines)
        + "\n"
    )
