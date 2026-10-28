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


def _formatter_expression(label, names):
    native = label["format"]
    precision = label["significant_digits"]
    if isinstance(native, str):
        notation = {
            "Decimal": "plain",
            "Scientific": "scientific",
            "Power": "power",
            "Degrees": "degrees",
            "Radians": "radians",
        }[native]
        return f"{names['SignificantFormatter']}({precision!r}, style={notation!r})"
    spec = native["Timestamp"]
    unit = {
        "Seconds": "s",
        "Milliseconds": "ms",
        "Microseconds": "us",
        "Nanoseconds": "ns",
    }[spec.get("unit", "Seconds")]
    zone = spec.get("timezone", "Utc")
    offset = 0 if zone == "Utc" else zone["FixedOffsetMinutes"]
    pattern = spec.get("label", "Auto")
    pattern = None if pattern == "Auto" else pattern["Pattern"]
    fractional = spec.get("fractional", "Auto")
    fractional = None if fractional == "Auto" else fractional["Fixed"]
    calendar = spec.get("tick_policy", "AutoCalendar") == "AutoCalendar"
    return f"{names['TimestampFormatter']}({pattern!r}, unit={unit!r}, timezone={offset!r}, fractional_digits={fractional!r}, calendar={calendar!r}, precision={precision!r})"


def settings_to_api_code(settings, defaults, dpi=120, variable="fig"):
    from .figure import _diff, _text, _code_tree
    from ._matplotlib import _StateFigure
    from .ticker import (
        MultipleLocator,
        LogLocator,
        AutoMinorLocator,
        SignificantFormatter,
        TimestampFormatter,
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
        "TimestampFormatter": TimestampFormatter,
    }
    ticker_names = {
        name: ("_fg_" + name if variable == name else name) for name in ticker_classes
    }
    namespace = {
        variable: model,
        **{ticker_names[name]: cls for name, cls in ticker_classes.items()},
    }
    from ._artist_appearance import MarkerStyle, ErrorBarStyle, BinStyle, _PARTS

    from ._field_api import ContourLabel

    style_classes = {
        "ContourLabel": ContourLabel,
        "MarkerStyle": MarkerStyle,
        "ErrorBarStyle": ErrorBarStyle,
        "BinStyle": BinStyle,
    }
    style_names = {
        name: ("_fg_" + name if variable == name else name) for name in style_classes
    }
    namespace.update({style_names[name]: cls for name, cls in style_classes.items()})
    from .figure import text_segments
    from ._richtext import TextRun, run_expression

    run_name = "TextRun" if variable != "TextRun" else "_fg_TextRun"
    namespace[run_name] = TextRun

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
        return run_expression(rich["segments"], dpi, run_name)

    def style_expression(entry, part):
        from dataclasses import fields
        from ._artist_appearance import _style

        _, cls, _, _ = _PARTS[part]
        value = _style(entry, part, dpi, decode=True)
        args = []
        for field in fields(value):
            item = getattr(value, field.name)
            if item is None:
                continue
            if field.name in ("color", "facecolor", "edgecolor"):
                item = _color_literal(dict(zip("rgba", item)))
            if field.name in ("markersize", "linewidth", "capsize", "capthick", "gap"):
                pixels = item * dpi / 72
                item = _points(pixels, dpi)
            args.append(f"{field.name}={item!r}")
        return style_names[cls.__name__] + "(" + ", ".join(args) + ")"

    def column_expression(name):
        return f"{variable}.data.column({name!r})"

    def grid_expression(grid):
        axis = "y" if grid["orientation"] == "ColumnsAreY" else "x"
        return f"{variable}.data.grid({grid['columns']!r}, axis={axis!r}, coordinates={grid['grid_layout'].lower()!r})"

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
            emit(
                f"{axis}.set_scale({'log' if node['scale'] == 'Logarithmic' else 'linear'!r})"
            )
            if node["scale"] == "Linear":
                emit(
                    f"{axis}.set_major_locator({ticker_names['MultipleLocator']}({node['major_spacing']!r}))"
                )
            else:
                emit(
                    f"{axis}.set_major_locator({ticker_names['LogLocator']}(base={10 ** node['major_spacing']!r}))"
                )
            emit(
                f"{axis}.set_minor_locator({ticker_names['AutoMinorLocator']}({node['minor_count'] + 1}))"
            )
            label = node["label_style"]
            emit(
                f"{axis}.set_major_formatter({_formatter_expression(label, ticker_names)})"
            )
            args = [
                f"labelsize={_points(label['font_size'], dpi)!r}",
                f"labelcolor={color(label['color'])!r}",
                f"labelfontfamily={label['label_font']!r}",
                f"label{side}={bool(label['label_visible'])!r}",
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
            emit(f"{axis}.set_ticklabels_enabled({label['visible']!r})")
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
            if line.get("fill_color") is not None and line.get("fill") is None:
                emit(
                    f"{artist}.set_fill(None, color={color(line['fill_color'])!r})",
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

            from ._markers import decode_marker

            marker, fillstyle = decode_marker(scatter["point_shape"])
            # Adding markers is a supported resident-Line transition. Emit it
            # before size, even when the source model already has that marker.
            emit(f"{artist}.set_marker({marker!r})", force=True)
            if fillstyle is not None:
                emit(f"{artist}.set_fillstyle({fillstyle!r})", force=True)
            emit(
                f"{artist}.set_markersize({_points(scatter['point_size'] * 2, dpi)!r})",
                force=True,
            )
            emit(
                f"{artist}.markers.set(color={color(scatter['point_color'])!r})",
                force=True,
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
        for part, (key, _, _, prefix) in _PARTS.items():
            if key not in body:
                continue
            node = body[key]
            base = artist + "." + part
            if part != "bins":
                table = node.get(prefix + "_style_table")
                index = node.get(prefix + "_style_index_column")
                entries = (
                    "None"
                    if table is None
                    else "[" + ", ".join(style_expression(v, part) for v in table) + "]"
                )
                source = "None" if index is None else column_expression(index)
                emit(f"{base}.set_palette({entries}, source={source})", force=True)
            overrides = node.get(prefix + "_style_overrides")
            entries = (
                "None"
                if overrides is None
                else "["
                + ", ".join(
                    f"({v['index']!r}, {style_expression(v, part)})" for v in overrides
                )
                + "]"
            )
            emit(f"{base}.set_overrides({entries})", force=True)
        if "scatter" in body:
            node = body["scatter"]
            mapping = node.get("point_color_map")
            if mapping:
                owner = next(
                    a
                    for a in model.axes
                    if any(
                        s["series_id"] == spec["series_id"]
                        for s in a._owned_series(model.get_settings())
                    )
                )
                bar = owner._config(settings)["colorbar"]
                clim = (bar["axis"]["min"], bar["axis"]["max"])
                emit(
                    f"{artist}.markers.map_color({column_expression(mapping['column'])}, clim={clim!r})",
                    force=True,
                )
            else:
                emit(f"{artist}.markers.map_color(None)", force=True)
            mapping = node.get("point_size_map")
            if mapping:
                domain = (mapping["domain_min"], mapping["domain_max"])
                sizes = (
                    _points(mapping["min_px"] * 2, dpi),
                    _points(mapping["max_px"] * 2, dpi),
                )
                emit(
                    f"{artist}.markers.map_size({column_expression(mapping['column'])}, domain={domain!r}, markersizes={sizes!r}, scale={mapping['scale'].lower()!r})",
                    force=True,
                )
            else:
                emit(f"{artist}.markers.map_size(None)", force=True)
        if "matrix" in body:
            emit(f"{artist}.set_grid({grid_expression(body['matrix'])})", force=True)
        if "contour" in body:
            contour = body["contour"]
            line = contour["line"]
            emit(f"{artist}.contours.set_levels({contour['levels']!r})", force=True)
            colors = contour.get("per_level_color")
            colors = None if colors is None else [color(v) for v in colors]
            emit(
                f"{artist}.contours.set_style(color={color(line['line_color'])!r}, linewidth={_points(line['line_width'], dpi)!r}, linestyle={dict(Solid='-', Dash='--', Dot=':', DashDot='-.')[line['line_style']]!r}, colors={colors!r})",
                force=True,
            )
            label = contour.get("labels")
            if label:
                positions = (
                    "["
                    + ", ".join(
                        f"{style_names['ContourLabel']}({v['level_index']!r}, {v['x']!r}, {v['y']!r}, tangent={(v['tx'], v['ty'])!r})"
                        for v in label["anchors"]
                    )
                    + "]"
                )
                emit(
                    f"{artist}.contours.set_labels({label['visible']!r}, fontsize={_points(label['font_size'], dpi)!r}, color={color(label['color'])!r}, formatter={_formatter_expression(label, ticker_names)}, spacing={_points(label['spacing_px'], dpi)!r}, positions={positions}, background={color(label['bg_color']) if label.get('bg_color') else None!r}, padding={_points(label['bg_padding_px'], dpi)!r})",
                    force=True,
                )
            else:
                emit(f"{artist}.contours.set_labels(None)", force=True)
        if "components" in body:
            style = body["style"]
            units, scale = next(iter(style["scale"].items()))
            scale = next(iter(scale.values()))
            emit(
                f"{artist}.vectors.set(color={color(style['color'])!r}, linewidth={_points(style['width_px'], dpi)!r}, head_length={_points(style['head_length_px'], dpi)!r}, head_width={_points(style['head_width_px'], dpi)!r}, min_length={_points(style.get('min_length_px', 0), dpi)!r}, pivot={style['pivot'].lower()!r}, units={'data' if units == 'Data' else 'pixels'!r}, scale={scale!r})",
                force=True,
            )
            mapping = style.get("color_map")
            if mapping:
                kind, value = next(iter(mapping.items()))
                source = (
                    grid_expression(value)
                    if kind == "Grid"
                    else column_expression(value)
                )
                owner = next(
                    a
                    for a in model.axes
                    if any(
                        s["series_id"] == spec["series_id"]
                        for s in a._owned_series(model.get_settings())
                    )
                )
                bar = owner._config(settings)["colorbar"]
                clim = (bar["axis"]["min"], bar["axis"]["max"])
                emit(f"{artist}.vectors.map_color({source}, clim={clim!r})", force=True)
            else:
                emit(f"{artist}.vectors.map_color(None)", force=True)
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
        if spec.get("label") is not None:
            rich = spec["label"]
            emit(
                f"{artist}.legend_label.set(fontsize={_points(rich['font_size'], dpi)!r}, color={color(rich['color'])!r}, fontfamily={rich['font']!r})",
                force=True,
            )
        if body.get("line", {}).get("fill") is not None:
            fill = body["line"]["fill"]
            target = next(iter(fill.values()))
            opts = (
                ", color=" + repr(color(body["line"]["fill_color"]))
                if body["line"].get("fill_color") is not None
                else ""
            )
            emit(f"{artist}.set_fill({target!r}{opts})", force=True)
        if "fill" in body and "matrix" in body:
            fill = body["fill"]
            emit(
                f"{artist}.set_field_fill(mode={fill['mode'].lower()!r}, shading={fill['shading'].lower()!r}, alpha={fill['opacity']!r})",
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
        emit(
            f"{ax}.legend_handle.content.set(text={rich_arg(rich)}, multialignment={rich.get('align', 'Left').lower()!r})"
        )
        if legend["offset_x"] or legend["offset_y"]:
            emit(
                f"{ax}.legend_handle.set_offset({(_points(legend['offset_x'], dpi), _points(legend['offset_y'], dpi))!r})"
            )
    for index, cfg in enumerate(panels):
        parent = (
            f"{variable}.subplots[{settings['identity']['panels'][index]['id']!r}].axes"
        )
        for oid, layer in zip(
            settings["identity"]["panels"][index]["overlays"], cfg.get("overlays", [])
        ):
            target = f"{parent}.get_overlay({oid!r})"
            node = layer["y_axis"]
            axis = target + ".yaxis"
            low, high = node["min"], node["max"]
            emit(f"{axis}.set_view_interval({low!r}, {high!r})", force=True)
            emit(
                f"{axis}.set_scale({'log' if node['scale'] == 'Logarithmic' else 'linear'!r})",
                force=True,
            )
            emit(f"{axis}.set_inverted({node['inverted']!r})", force=True)
            locator = (
                f"{ticker_names['MultipleLocator']}({node['major_spacing']!r})"
                if node["scale"] == "Linear"
                else f"{ticker_names['LogLocator']}(base={10 ** node['major_spacing']!r})"
            )
            emit(f"{axis}.set_major_locator({locator})", force=True)
            emit(
                f"{axis}.set_minor_locator({ticker_names['AutoMinorLocator']}({node['minor_count'] + 1}))",
                force=True,
            )
            label = node["label_style"]
            emit(
                f"{axis}.set_major_formatter({_formatter_expression(label, ticker_names)})",
                force=True,
            )
            direction = dict(Inside="in", Outside="out", Both="inout", None_="in").get(
                node["tick"], "in"
            )
            emit(
                f"{axis}.set_tick_params(which='major', direction={direction!r}, length={_points(node['major_tick_length'], dpi)!r}, labelsize={_points(label['font_size'], dpi)!r}, labelcolor={color(label['color'])!r}, labelfontfamily={label['label_font']!r}, right={node['tick'] != 'None'!r}, labelright={label['label_visible']!r})",
                force=True,
            )
            emit(
                f"{axis}.set_tick_params(which='minor', length={_points(node['minor_tick_length'], dpi)!r})",
                force=True,
            )
            emit(f"{axis}.set_ticklabels_enabled({label['visible']!r})", force=True)
            emit(
                f"{axis}.set_layout_margin({_points(node['out_margin'], dpi)!r})",
                force=True,
            )
            emit(
                f"{axis}.set_ticklabel_offset({(_points(label['label_offset_x'], dpi), _points(label['label_offset_y'], dpi))!r})",
                force=True,
            )
            emit(
                f"{axis}.line.set(visible={node['line_visible']!r}, color={color(node['line_color'])!r}, linewidth={_points(node['line_width'], dpi)!r}, linestyle={dict(Solid='-', Dash='--', Dot=':', DashDot='-.')[node['line_style']]!r})",
                force=True,
            )
            emit(
                f"{axis}.line.set_position(('outward', {_points(node['line_offset'], dpi)!r}))",
                force=True,
            )
            title = node["title_option"]
            rich = title["text"]
            emit(
                f"{target}.set_ylabel({rich_arg(rich)}, fontsize={_points(rich['font_size'], dpi)!r}, color={color(rich['color'])!r}, fontfamily={rich['font']!r}, visible={title['visible']!r}, multialignment={rich.get('align', 'Left').lower()!r})",
                force=True,
            )
            emit(
                f"{axis}.label.set_offset({(_points(title['offset_x'], dpi), _points(title['offset_y'], dpi))!r})",
                force=True,
            )
            legend = layer.get("legend")
            if legend is None:
                emit(f"{target}.clear_legend()", force=True)
            else:
                rich = legend["content"]
                loc = dict(
                    TopLeft="upper left",
                    TopRight="upper right",
                    BottomLeft="lower left",
                    BottomRight="lower right",
                )[legend["corner"]]
                emit(
                    f"{target}.legend({legend['visible']!r}, loc={loc!r}, fontsize={_points(rich['font_size'], dpi)!r}, labelcolor={color(rich['color'])!r}, prop={{'family': {rich['font']!r}}}, borderpad={legend['padding'] / rich['font_size']!r}, facecolor={color(legend['bg_color'])!r}, edgecolor={color(legend['border_color'])!r})",
                    force=True,
                )
                emit(
                    f"{target}.legend_handle.content.set(text={rich_arg(rich)}, multialignment={rich.get('align', 'Left').lower()!r})",
                    force=True,
                )
                emit(
                    f"{target}.legend_handle.set_offset({(_points(legend['offset_x'], dpi), _points(legend['offset_y'], dpi))!r})",
                    force=True,
                )
    from ._annotation_codegen import annotation_calls

    annotations = settings["config"].get("annotations")
    if annotations:
        for call in annotation_calls(
            annotations, f"{variable}.axes[0]", variable, dpi, rich_arg
        ):
            emit(call, force=True)
    # Color scales use the same public shared object whether mapped or standalone.
    for index, cfg in enumerate(panels):
        ax = (
            f"{variable}.axes[0]"
            if index == 0
            else f"{variable}.subplots[{settings['identity']['panels'][index]['id']!r}].axes"
        )
        polar = cfg.get("polar")
        if polar:
            interpolation = polar["interpolation"]
            emit(
                f"{ax}.set_polar_options(unit={polar['angle_unit'].lower()!r}, zero={polar['zero_angle_degrees']!r}, clockwise={polar['clockwise']!r}, sector={polar['sector']!r}, inner_radius={polar['inner_radius_fraction']!r}, interpolation={'chord' if interpolation == 'Chord' else 'arc'!r}, pieces={1 if interpolation == 'Chord' else interpolation['Arc']['pieces']!r}, label_angle={polar['radial_label_angle_degrees']!r})",
                force=True,
            )
        else:
            emit(f"{ax}.clear_polar()", force=True)
        bar = cfg.get("colorbar")
        if not bar:
            emit(f"{ax}.clear_colorbar()", force=True)
            continue
        cmap = {"GrayScale": "gray", "RdBu": "RdBu"}.get(
            bar["colormap"], bar["colormap"].lower()
        )
        emit(
            f"{ax}.add_colorbar(cmap={cmap!r}, vmin={bar['axis']['min']!r}, vmax={bar['axis']['max']!r})",
            force=True,
        )
        scale = f"{ax}.get_colorbar()"
        axis = scale + ".ax.yaxis"
        node = bar["axis"]
        label = node["label_style"]
        title = node["title_option"]
        emit(
            f"{scale}.set_layout(side={bar['side'].lower()!r}, align={bar['align'].lower()!r}, fraction={bar['length_frac']!r}, thickness={_points(bar['thickness_px'], dpi)!r}, gap={_points(bar['gap_px'], dpi)!r}, offset={(_points(bar['offset_x'], dpi), _points(bar['offset_y'], dpi))!r})"
        )
        emit(f"{scale}.set_nan_color({color(bar['nan_color'])!r})")
        emit(
            f"{scale}.set_outline(color={color(bar['border_color'])!r}, linewidth={_points(bar['border_width'], dpi)!r})"
        )
        emit(f"{scale}.set_visible({bar['visible']!r})")
        emit(
            f"{axis}.set_scale({'log' if node['scale'] == 'Logarithmic' else 'linear'!r})"
        )
        emit(f"{axis}.set_inverted({node['inverted']!r})")
        locator = (
            f"{ticker_names['MultipleLocator']}({node['major_spacing']!r})"
            if node["scale"] == "Linear"
            else f"{ticker_names['LogLocator']}(base={10 ** node['major_spacing']!r})"
        )
        emit(f"{axis}.set_major_locator({locator})")
        emit(
            f"{axis}.set_minor_locator({ticker_names['AutoMinorLocator']}({node['minor_count'] + 1}))"
        )
        emit(
            f"{axis}.set_major_formatter({_formatter_expression(label, ticker_names)})"
        )
        side = "right" if bar["side"] in ("Left", "Right") else "bottom"
        direction = {"Inside": "in", "Outside": "out", "Both": "inout", "None": "in"}[
            node["tick"]
        ]
        emit(
            f"{axis}.set_tick_params(which='major', direction={direction!r}, length={_points(node['major_tick_length'], dpi)!r}, labelsize={_points(label['font_size'], dpi)!r}, labelcolor={color(label['color'])!r}, labelfontfamily={label['label_font']!r}, {side}={node['tick'] != 'None'!r}, label{side}={label['label_visible']!r})"
        )
        emit(
            f"{axis}.set_tick_params(which='minor', length={_points(node['minor_tick_length'], dpi)!r})"
        )
        emit(f"{axis}.set_ticklabels_enabled({label['visible']!r})")
        emit(
            f"{axis}.set_ticklabel_offset({(_points(label['label_offset_x'], dpi), _points(label['label_offset_y'], dpi))!r})"
        )
        emit(f"{axis}.set_layout_margin({_points(node['out_margin'], dpi)!r})")
        emit(
            f"{axis}.line.set(visible={node['line_visible']!r}, color={color(node['line_color'])!r}, linewidth={_points(node['line_width'], dpi)!r}, linestyle={dict(Solid='-', Dash='--', Dot=':', DashDot='-.')[node['line_style']]!r})"
        )
        emit(
            f"{axis}.line.set_position(('outward', {_points(node['line_offset'], dpi)!r}))"
        )
        rich = title["text"]
        emit(
            f"{scale}.set_label({rich_arg(rich)}, fontsize={_points(rich['font_size'], dpi)!r}, color={color(rich['color'])!r}, fontfamily={rich['font']!r}, visible={title['visible']!r})"
        )
        emit(
            f"{axis}.label.set_offset({(_points(title['offset_x'], dpi), _points(title['offset_y'], dpi))!r})"
        )
    active = settings["config"].get("active_layer", "Base")
    if active == "Annotations":
        emit(f"{variable}.axes[0].activate_annotations()")
    else:
        panel_index, overlay_index = 0, None
        if isinstance(active, dict):
            name, value = next(iter(active.items()))
            if name == "Subplot":
                panel_index = value + 1
            elif name == "Overlay":
                overlay_index = value
            elif name == "SubplotOverlay":
                panel_index, overlay_index = value[0] + 1, value[1]
        panel = settings["identity"]["panels"][panel_index]
        target = f"{variable}.subplots[{panel['id']!r}].axes"
        if overlay_index is not None:
            target += f".get_overlay({panel['overlays'][overlay_index]!r})"
        emit(target + ".activate()")
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
            (
                "line",
                (
                    "line_color",
                    "line_width",
                    "line_style",
                    "interpolation",
                    "fill",
                    "fill_color",
                ),
            ),
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
        if "matrix" in body:
            advanced.pop("fill", None)
        for part, (key, _, _, prefix) in _PARTS.items():
            if key not in advanced:
                continue
            for name in (
                prefix + "_style_table",
                prefix + "_style_index_column",
                prefix + "_style_overrides",
            ):
                advanced[key].pop(name, None)
            if key == "scatter":
                advanced[key].pop("point_color_map", None)
                advanced[key].pop("point_size_map", None)
            if not advanced[key]:
                advanced.pop(key)
        if "components" in body:
            advanced.pop("style", None)
        for binding in ("matrix", "components", "err_x", "err_y"):
            advanced.pop(binding, None)
        if "contour" in advanced:
            extra = {
                key: value
                for key, value in advanced["contour"].get("line", {}).items()
                if key not in ("line_color", "line_width", "line_style")
            }
            if extra:
                advanced["contour"] = {"line": extra}
            else:
                advanced.pop("contour")
        if advanced:
            patch = (
                series_patch.setdefault(spec["series_id"], {})
                .setdefault("render_type", {})
                .setdefault(kind, {})
            )
            from .figure import _merge

            _merge(patch, advanced)
    # Editor/identity records and unhandled native extension fields remain
    # lossless. All supported visual controls above use public object calls.
    config_patch.pop("subplots", None)
    panel_patches = []
    restored_panels = [restored["config"]] + [
        p["config"] for p in restored["config"].get("subplots", [])
    ]
    for index, (baseline, cfg) in enumerate(zip(restored_panels, panels)):
        patch = config_patch if index == 0 else _prune_empty(_diff(baseline, cfg))
        if index and patch:
            panel_patches.append((index, patch))
    if config_patch or series_patch:
        parts = []
        if config_patch:
            parts.append("config=" + fmt(config_patch))
        if series_patch:
            parts.append("series=" + fmt(series_patch))
        lines.append("# Exact internal state outside public appearance controls.")
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
    used_styles = [
        name + (" as " + style_names[name] if style_names[name] != name else "")
        for name in style_classes
        if any(style_names[name] + "(" in line for line in lines)
    ]
    if any(run_name + "(" in line for line in lines):
        imports += f"from figgyplot import TextRun as {run_name}\n"
    if used_styles:
        imports += "from figgyplot import " + ", ".join(used_styles) + "\n"
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
    from ._richtext import TextRun, run_expression

    run_name = "TextRun" if variable != "TextRun" else "_fg_TextRun"
    namespace[run_name] = TextRun

    def rich_arg(rich):
        plain = _text(rich)
        return (
            repr(plain)
            if rich["segments"] == _segments(plain)
            else run_expression(rich["segments"], dpi, run_name)
        )

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
    from ._appearance import style_values
    from ._chart_artist import _LABELS

    options = style_values(kind, chart["style"], dpi)
    current = eval(appearance, namespace).get_style()
    options = {key: value for key, value in options.items() if value != current[key]}
    if options:
        emit(
            f"{appearance}.set_style("
            + ", ".join(f"{key}={value!r}" for key, value in options.items())
            + ")"
        )
    label_options = {}
    if "label_format" in chart:
        from ._chart_artist import _FORMATS

        formats = {v: k for k, v in _FORMATS.items()}
        label_options["format"] = formats[chart["label_format"]]
    for public, key in [
        ("position", "labels"),
        ("decimals", "label_decimals"),
        ("suffix", "value_suffix"),
    ]:
        if key in chart:
            label_options[public] = (
                {v: k for k, v in _LABELS[kind].items()}[chart[key]]
                if public == "position"
                else chart[key]
            )
    emit(
        f"{appearance}.set_value_labels("
        + ", ".join(f"{key}={value!r}" for key, value in label_options.items())
        + ")"
    )
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
        value = repr(plain) if rebuilt == rich["segments"] else rich_arg(rich)
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

    # Every item is addressed by stable identity; resident values are never exported.
    def element_appearance(target, item):
        if item.get("style") is not None:
            if kind == "radar":
                from ._appearance import convert

                fields = dict(
                    linewidth=("line_width_px", "length"),
                    facecolor=("fill", "color"),
                    marker=("marker", "shape"),
                    markersize=("marker_size_px", "length"),
                )
                options = {
                    name: None
                    if item["style"].get(key) is None
                    else convert(item["style"][key], conversion, dpi, decode=True)
                    for name, (key, conversion) in fields.items()
                }
            else:
                options = style_values(kind, item["style"], dpi)
                shared = style_values(kind, chart["style"], dpi)
                options = {
                    key: value for key, value in options.items() if value != shared[key]
                }
            if kind == "radar":
                options = {
                    key: value for key, value in options.items() if value is not None
                }
            options = {
                key: _color_literal(dict(zip("rgba", value)))
                if isinstance(value, tuple) and len(value) == 4
                else value
                for key, value in options.items()
            }
            emit(
                f"{target}.set_style("
                + ", ".join(f"{key}={value!r}" for key, value in options.items())
                + ")",
                force=True,
            )
        if "labels" in item:
            options = dict(
                position=None
                if item["labels"] is None
                else {v: k for k, v in _LABELS[kind].items()}[item["labels"]]
            )
            if "label_format" in item:
                from ._chart_artist import _FORMATS

                options["format"] = (
                    None
                    if item["label_format"] is None
                    else {v: k for k, v in _FORMATS.items()}[item["label_format"]]
                )
            if "label_color" in item:
                options["color"] = (
                    None if item["label_color"] is None else color(item["label_color"])
                )
            emit(
                f"{target}.set_value_labels("
                + ", ".join(f"{key}={value!r}" for key, value in options.items())
                + ")",
                force=True,
            )

    if kind == "radial":
        for index, item in enumerate(chart["slices"]):
            element_appearance(f"{appearance}.slice({index})", item)
        if chart.get("split"):
            split = chart["split"]
            inner = (
                None
                if split["kind"] == "Pie"
                else split["kind"]["Donut"]["inner_radius"]
            )
            emit(f"{appearance}.set_split_inner_radius({inner!r})", force=True)
            for index, item in enumerate(split["children"]):
                target = f"{appearance}.slice({index}, detail=True)"
                emit(f"{target}.set_label({item['label']!r})", force=True)
                emit(f"{target}.set_color({color(item['color'])!r})", force=True)
                emit(f"{target}.set_explode({item['explode']!r})", force=True)
                element_appearance(target, item)
    else:
        for item in chart["series"]:
            element_appearance(f"{appearance}.series({item['id']!r})", item)
        for item in chart.get("overrides", []):
            target = item["target"]
            handle = (
                f"{appearance}.cell({target['category_id']!r}, {target['series_id']!r})"
            )
            emit(
                f"{handle}.set_color({None if item['color'] is None else color(item['color'])!r})",
                force=True,
            )
            element_appearance(handle, item)
        if kind == "radar":
            emit(f"{appearance}.set_ring_spacing({chart['ring_spacing']!r})")
    bounds = chart["decorations"]["data_area"]
    if bounds:
        emit(
            f"{appearance}.set_plot_bounds({tuple(_points(bounds[k], dpi) for k in ('x', 'y', 'width', 'height'))!r})"
        )
    for offset in chart["decorations"]["offsets"]:
        element = offset["element"]
        names = dict(DataArea="data", ChartTitle="title", Legend="legend")
        if isinstance(element, str):
            args = repr(names[element])
        else:
            name, value = next(iter(element.items()))
            if name in ("Axis", "AxisLabel", "AxisTitle"):
                args = f"{dict(Axis='axis', AxisLabel='ticklabels', AxisTitle='axis_title')[name]!r}, side={value.lower()!r}"
            elif name == "DataLabel":
                args = f"'value_label', category={value['category_id']!r}, series={value['series_id']!r}"
            elif name == "SpokeLabel":
                args = f"'spoke_label', category={value['category_id']!r}"
            elif name == "RadialLabel":
                args = f"'slice_label', index={value['index']!r}, detail={bool(value['group'])!r}"
            elif name == "Annotation":
                args = f"'annotation', index={value!r}"
            else:
                raise ValueError("unsupported bounded decoration; use exact recovery")
        emit(
            f"{appearance}.decoration({args}).set_offset({tuple(_points(v, dpi) for v in offset['offset'])!r})",
            force=True,
        )
    if chart.get("annotations"):
        from ._annotation_codegen import annotation_calls

        for call in annotation_calls(
            chart["annotations"], axname, variable, dpi, rich_arg
        ):
            emit(call, force=True)
    if chart.get("active_layer", "Base") == "Annotations":
        emit(f"{axname}.activate_annotations()")
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
            if value.get("split"):
                value["split"]["children"] = {
                    i: {k: v for k, v in item.items() if k != "value"}
                    for i, item in enumerate(value["split"]["children"])
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
    if any(run_name + "(" in line for line in lines):
        imports += f"from figgyplot import TextRun as {run_name}\n"
    return (
        imports
        + "# Apply appearance to an existing chart with matching category/series IDs.\n"
        + f"with {variable}.batch_update():\n"
        + "\n".join("    " + line.replace("\n", "\n    ") for line in lines)
        + "\n"
    )
