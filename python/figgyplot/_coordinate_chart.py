"""Named appearance controls for bar/box/radar series in coordinate panels."""

import copy
import json

from ._appearance import edit_style, style_values
from ._validation import number


class CoordinateChartAppearance:
    _families = {"CategoryBars": "categorical", "BoxPlot": "boxplot", "Radar": "radar"}

    def __init__(self, axes):
        self.axes, self.figure = axes, axes.figure
        kinds = {
            next(iter(s["render_type"]))
            for s in axes._owned_series(self.figure.get_settings())
        }
        kinds &= self._families.keys()
        if len(kinds) != 1:
            raise AttributeError(
                "chart appearance requires one bar, box or radar family; use artist handles for mixed families"
            )
        self.tag = kinds.pop()
        self.kind = self._families[self.tag]

    def _members(self, state):
        return [
            s for s in self.axes._owned_series(state) if self.tag in s["render_type"]
        ]

    def _body(self, spec):
        return spec["render_type"][self.tag]

    def _edit(self, operation):
        with self.figure._lock:
            state = self.figure.get_settings()
            members = self._members(state)
            if not members:
                raise ValueError("chart series no longer exist")
            operation(self.axes._config(state), members)
            self.figure.apply_settings(state)
        return self

    def _axis(self, cfg):
        return (
            "left_y"
            if self.kind != "radar"
            and (cfg.get("bar_groups") or {}).get("direction") == "Horizontal"
            else "bottom_x"
        )

    def _style(self, cfg, spec):
        body = self._body(spec)
        if self.kind != "radar":
            return copy.deepcopy(body["style"])
        from ._native import default_bounded_json

        style = json.loads(default_bounded_json("radar"))["style"]
        style.update(
            {k: v for k, v in body["style"].items() if v is not None and k in style}
        )
        polar = cfg["polar"]
        style.update(
            start_angle_degrees=-polar["zero_angle_degrees"],
            clockwise=polar["clockwise"],
            grid_shape=polar["grid_shape"],
            spoke_color=cfg["grid"]["major_x_color"],
            ring_color=cfg["grid"]["major_y_color"],
        )
        return style

    def get_style(self):
        state = self.figure.get_settings()
        members = self._members(state)
        if not members:
            raise ValueError("chart series no longer exist")
        result = style_values(
            self.kind,
            self._style(self.axes._config(state), members[0]),
            self.figure.dpi,
        )
        if self.kind == "radar":
            result.pop("emphasis_brightness", None)
        return result

    def set_style(self, **properties):
        if self.kind == "radar" and "emphasis_brightness" in properties:
            raise ValueError(
                "common radar uses selection rings; emphasis_brightness is unavailable"
            )

        def edit(cfg, members):
            for spec in members:
                style = self._style(cfg, spec)
                edit_style(self.kind, style, self.figure.dpi, properties)
                if self.kind == "radar":
                    body = self._body(spec)
                    for key in (
                        "line_width_px",
                        "marker",
                        "marker_size_px",
                        "fill_opacity",
                    ):
                        body["style"][key] = style[key]
                    cfg["polar"].update(
                        zero_angle_degrees=-style["start_angle_degrees"],
                        clockwise=style["clockwise"],
                        grid_shape=style["grid_shape"],
                    )
                    cfg["grid"].update(
                        major_x_color=style["spoke_color"],
                        major_y_color=style["ring_color"],
                    )
                else:
                    self._body(spec)["style"] = style

        return self._edit(edit)

    def reset_style(self):
        from ._native import default_bounded_json

        defaults = json.loads(default_bounded_json(self.kind))["style"]
        properties = style_values(self.kind, defaults, self.figure.dpi)
        if self.kind == "radar":
            properties.pop("emphasis_brightness", None)
        return self.set_style(**properties)

    def set_material(self, name):
        if self.kind == "radar":
            raise NotImplementedError("radar charts have no material")
        return self.set_style(material=name)

    def set_label_style(self, *, fontsize=None, fontfamily=None, color=None):
        from .figure import _color

        def edit(cfg, members):
            patch = {}
            if fontsize is not None:
                patch["font_size"] = (
                    number(fontsize, "fontsize", positive=True) * self.figure.dpi / 72
                )
            if fontfamily is not None:
                patch["label_font"] = self.figure._check_font(fontfamily)
            if color is not None:
                patch["color"] = _color(color)
            for side in ("bottom_x", "top_x", "left_y", "right_y"):
                cfg[side]["label_style"].update(copy.deepcopy(patch))

        return self._edit(edit)

    def get_categories(self):
        cfg = self.axes._config(self.figure.get_settings())
        return {c["id"]: c["label"] for c in cfg[self._axis(cfg)].get("categories", [])}

    def get_series(self):
        from .figure import _text

        return {
            s["series_id"]: _text(s["label"]) if s.get("label") else ""
            for s in self._members(self.figure.get_settings())
        }

    def set_category_label(self, id, label):
        from ._chart_text import category_label

        def edit(cfg, members):
            item = next(
                (
                    c
                    for c in cfg[self._axis(cfg)].get("categories", [])
                    if c["id"] == id
                ),
                None,
            )
            if item is None:
                raise ValueError("unknown category ID")
            item["label"] = category_label(label)
            item.pop("rich_label", None)

        return self._edit(edit)

    def set_series(self, id, *, label=None, color=None):
        from .figure import _color, _segments

        def edit(cfg, members):
            item = next((s for s in members if s["series_id"] == id), None)
            if item is None:
                raise ValueError("unknown chart series ID")
            if label is not None:
                item["label"] = copy.deepcopy(
                    item.get("label") or cfg["legend"]["content"]
                )
                item["label"]["segments"] = _segments(label, dpi=self.figure.dpi)
            if color is not None:
                self._body(item)["color"] = _color(color)

        return self._edit(edit)

    def _groups(self, **patch):
        if self.kind == "radar":
            raise AttributeError("group controls require bars or boxes")
        return self._edit(
            lambda cfg, members: cfg.setdefault("bar_groups", {}).update(patch)
        )

    def set_group_width(self, fraction):
        value = number(fraction, "group width")
        if not 0.1 <= value <= 0.95:
            raise ValueError("group width must be in [0.1, 0.95]")
        return self._groups(group_width=value)

    def set_gap(self, points):
        value = number(points, "gap") * self.figure.dpi / 72
        if not 0 <= value <= 24:
            raise ValueError("gap must be in [0, 24] logical pixels")
        return self._groups(bar_gap=value)

    def set_mode(self, mode):
        modes = dict(
            grouped="Grouped", stacked="Stacked", percent_stacked="PercentStacked"
        )
        if self.kind != "categorical" or mode not in modes:
            raise ValueError(
                "mode requires categorical bars: grouped/stacked/percent_stacked"
            )
        return self._groups(mode=modes[mode])

    def set_ring_spacing(self, spacing=None):
        if self.kind != "radar":
            raise AttributeError("ring spacing requires radar")
        if spacing is None:
            self.axes.fit()
            return self
        value = number(spacing, "ring spacing", positive=True)
        return self._edit(
            lambda cfg, members: cfg["left_y"].update(major_spacing=value)
        )

    def set_value_labels(
        self, *, position=None, format=None, decimals=None, suffix=None
    ):
        from ._chart_artist import _FORMATS, _placement

        def edit(cfg, members):
            for spec in members:
                body = self._body(spec)
                if position is not None:
                    body["labels"]["placement"] = _placement(self.kind, position)
                if format is not None:
                    if self.kind != "categorical":
                        raise NotImplementedError(
                            "this chart has no value-label format selector"
                        )
                    if format not in _FORMATS:
                        raise ValueError("unknown value label format")
                    body["label_format"] = _FORMATS[format]
                if decimals is not None:
                    if type(decimals) is not int or not 0 <= decimals <= 6:
                        raise ValueError("decimals must be an integer from 0 to 6")
                    body["labels"]["decimals"] = decimals
                if suffix is not None:
                    body["labels"]["value_suffix"] = str(suffix)

        return self._edit(edit)

    def series(self, id):
        return CoordinateElement(self, "series", id)

    def cell(self, category, series):
        if self.kind == "radar":
            raise AttributeError("cell overrides require categorical bars or boxes")
        return CoordinateElement(self, "cell", (category, series))

    def clear_overrides(self):
        if self.kind == "radar":
            raise AttributeError("radar has no cell overrides")
        return self._edit(
            lambda cfg, members: [self._body(s).pop("overrides", None) for s in members]
        )

    def set_plot_bounds(self, bounds=None):
        """Set a fixed plot rectangle in points, or return to fitted layout."""
        if bounds is None:
            from ._native import transform_settings_json

            def edit(cfg, members):
                state = self.figure.get_settings()
                fitted = json.loads(
                    transform_settings_json(json.dumps(state), "layout", "")
                )
                result = self.axes._config(fitted)
                cfg["layout_state"] = "fitted"
                for side in ("bottom_x", "top_x", "left_y", "right_y"):
                    cfg[side]["out_margin"] = result[side]["out_margin"]
                for old, new in zip(
                    cfg.get("overlays", []), result.get("overlays", [])
                ):
                    old["y_axis"]["out_margin"] = new["y_axis"]["out_margin"]

            return self._edit(edit)
        values = [number(v, "plot bounds") * self.figure.dpi / 72 for v in bounds]
        if len(values) != 4 or min(values[2:]) <= 0:
            raise ValueError("bounds require left, top and positive width/height")
        self.figure.edit_property(
            "panel/" + self.axes.subplot_id, "Plot area/bounds", values
        )
        return self

    def set_orientation(self, orientation):
        if self.kind == "radar" or orientation not in ("horizontal", "vertical"):
            raise ValueError(
                "orientation requires categorical bars/boxes: horizontal or vertical"
            )

        def edit(cfg, members):
            groups = cfg["bar_groups"]
            direction = orientation.title()
            if groups["direction"] == direction:
                return
            cfg["bottom_x"], cfg["left_y"] = cfg["left_y"], cfg["bottom_x"]
            if self.kind == "categorical":
                for spec in members:
                    spec["x_column"], spec["y_column"] = (
                        spec["y_column"],
                        spec["x_column"],
                    )
            groups["direction"] = direction

        return self._edit(edit)

    def decoration(
        self, name, *, side=None, category=None, series=None, index=None, detail=False
    ):
        if detail:
            raise AttributeError("detail decorations require a pie")
        return CoordinateDecoration(self, name, side, category, series, index)


class CoordinateElement:
    """A stable series or cell handle into the common-series model."""

    def __init__(self, chart, kind, key):
        self.chart, self.kind, self.key = chart, kind, key
        state = chart.figure.get_settings()
        self._node(chart.axes._config(state), chart._members(state), False)

    def _node(self, cfg, members, create=True):
        sid = self.key if self.kind == "series" else self.key[1]
        spec = next((s for s in members if s["series_id"] == sid), None)
        if spec is None:
            raise ValueError("unknown series ID")
        body = self.chart._body(spec)
        if self.kind == "series":
            return spec, body
        category = self.key[0]
        categories = cfg[self.chart._axis(cfg)].get("categories", [])
        if category not in [c["id"] for c in categories]:
            raise ValueError("unknown category ID")
        target = dict(category_id=category, series_id=sid)
        item = next(
            (o for o in body.get("overrides", []) if o["target"] == target), None
        )
        if item is None:
            item = dict(target=target, color=None, style=None, labels=None)
            if self.chart.kind == "categorical":
                item["label_format"] = None
            if create:
                body.setdefault("overrides", []).append(item)
        return spec, item

    def _edit(self, operation):
        def edit(cfg, members):
            spec, item = self._node(cfg, members)
            operation(cfg, spec, item)

        self.chart._edit(edit)
        return self

    def get_style(self):
        state = self.chart.figure.get_settings()
        cfg = self.chart.axes._config(state)
        spec, item = self._node(cfg, self.chart._members(state), False)
        style = item.get("style")
        if style is None or not any(v is not None for v in style.values()):
            return None
        if self.chart.kind == "radar":
            from ._appearance import convert

            return {
                name: (
                    None
                    if style.get(key) is None
                    else convert(style[key], kind, self.chart.figure.dpi, decode=True)
                )
                for name, (key, kind) in self._radar_fields.items()
            }
        return style_values(self.chart.kind, style, self.chart.figure.dpi)

    _radar_fields = dict(
        linewidth=("line_width_px", "length"),
        facecolor=("fill", "color"),
        marker=("marker", "shape"),
        markersize=("marker_size_px", "length"),
    )

    def set_style(self, **properties):
        def edit(cfg, spec, item):
            if self.chart.kind == "radar":
                from ._appearance import convert

                if properties.keys() - self._radar_fields.keys():
                    raise ValueError(
                        "radar series style supports linewidth, facecolor, marker, markersize"
                    )
                for name, value in properties.items():
                    key, kind = self._radar_fields[name]
                    item["style"][key] = (
                        None
                        if value is None
                        else convert(value, kind, self.chart.figure.dpi)
                    )
            else:
                style = copy.deepcopy(
                    item.get("style") or self.chart._body(spec)["style"]
                )
                edit_style(self.chart.kind, style, self.chart.figure.dpi, properties)
                item["style"] = style

        return self._edit(edit)

    def reset_style(self):
        def edit(cfg, spec, item):
            if self.kind == "cell":
                item["style"] = None
            elif self.chart.kind == "radar":
                item["style"] = dict.fromkeys(
                    self._radar_fields[name][0] for name in self._radar_fields
                )
            else:
                from ._native import series_template_json

                tag = (
                    "category_bars" if self.chart.kind == "categorical" else "box_plot"
                )
                template = json.loads(series_template_json(tag))
                item["style"] = next(iter(template["render_type"].values()))["style"]

        return self._edit(edit)

    def set_color(self, color):
        from .figure import _color

        if color is None and self.kind != "cell":
            raise ValueError("only cell colors may inherit")
        return self._edit(
            lambda cfg, spec, item: item.update(
                color=None if color is None else _color(color)
            )
        )

    def set_label(self, text):
        if self.kind == "cell":
            # Text is already a public renderer appearance field. Address it
            # through the category ID rather than creating a style override.
            def edit(cfg, members):
                spec, _ = self._node(cfg, members, False)
                categories = cfg[self.chart._axis(cfg)]["categories"]
                index = next(
                    i for i, c in enumerate(categories) if c["id"] == self.key[0]
                )
                labels = self.chart._body(spec)["labels"]
                values = list(labels.get("text", []))
                values.extend([""] * max(0, len(categories) - len(values)))
                values[index] = "" if text is None else str(text)
                labels["text"] = values

            self.chart._edit(edit)
            return self
        self.chart.set_series(self.key, label=text)
        return self

    def get_label(self):
        state = self.chart.figure.get_settings()
        cfg = self.chart.axes._config(state)
        spec, _ = self._node(cfg, self.chart._members(state), False)
        if self.kind == "series":
            from .figure import _text

            return "" if spec.get("label") is None else _text(spec["label"])
        categories = cfg[self.chart._axis(cfg)]["categories"]
        index = next(i for i, c in enumerate(categories) if c["id"] == self.key[0])
        values = self.chart._body(spec)["labels"].get("text", [])
        return values[index] if index < len(values) else ""

    def set_value_labels(self, *, position=..., format=..., color=...):
        from ._chart_artist import _FORMATS, _placement

        if self.kind == "series":
            raise AttributeError(
                "series label placement uses chart defaults; override a cell"
            )
        if color is not ...:
            raise AttributeError("label color overrides require a pie slice")

        def edit(cfg, spec, item):
            if position is not ...:
                item["labels"] = (
                    None if position is None else _placement(self.chart.kind, position)
                )
            if format is not ...:
                if self.chart.kind != "categorical":
                    raise AttributeError("this element has no label format override")
                if format is not None and format not in _FORMATS:
                    raise ValueError("unknown label format")
                item["label_format"] = None if format is None else _FORMATS[format]

        return self._edit(edit)


class CoordinateDecoration:
    def __init__(self, chart, name, side, category, series, index):
        self.chart, self.name, self.side = chart, name, side
        self.category, self.series, self.index = category, series, index
        self._offset = [0.0, 0.0]
        if name not in (
            "title",
            "legend",
            "data",
            "axis",
            "ticklabels",
            "axis_title",
            "value_label",
            "spoke_label",
            "annotation",
        ):
            raise ValueError("unknown chart decoration")
        if name in ("axis", "ticklabels", "axis_title") and side not in (
            "left",
            "right",
            "top",
            "bottom",
        ):
            raise ValueError("side must be left/right/top/bottom")
        if name == "spoke_label" and chart.kind != "radar":
            raise AttributeError("spoke label requires radar")

    def set_offset(self, offset):
        values = [
            number(v, "decoration offset") * self.chart.figure.dpi / 72 for v in offset
        ]
        if len(values) != 2:
            raise ValueError("offset requires two components")

        if self.name == "data":
            with self.chart.figure._lock:
                owner = next(
                    o
                    for o in self.chart.figure.editor_properties()
                    if o["id"] == "panel/" + self.chart.axes.subplot_id
                )
                bounds = next(
                    f["value"] for f in owner["fields"] if f["id"] == "Plot area/bounds"
                )
                bounds[0] += values[0] - self._offset[0]
                bounds[1] += values[1] - self._offset[1]
                self.chart.figure.edit_property(owner["id"], "Plot area/bounds", bounds)
                self._offset = values
            return self
        if self.name == "annotation":
            from ._native import transform_settings_json
            from . import _document

            with self.chart.figure._lock:
                state = self.chart.figure.get_settings()
                cfg = self.chart.axes._config(state)
                items = cfg.get("annotations", {}).get("items", [])
                if type(self.index) is not int or not 0 <= self.index < len(items):
                    raise ValueError("annotation index out of range")
                arg = dict(
                    panel=_document.panel_index(state, self.chart.axes.subplot_id),
                    index=self.index,
                    dx=values[0] - self._offset[0],
                    dy=values[1] - self._offset[1],
                )
                if arg["dx"] or arg["dy"]:
                    updated = json.loads(
                        transform_settings_json(
                            json.dumps(state), "annotation_offset", json.dumps(arg)
                        )
                    )
                    self.chart.figure.apply_settings(updated)
                self._offset = values
            return self

        def edit(cfg, members):
            if self.name in ("title", "legend"):
                node = cfg["chart_title" if self.name == "title" else "legend"]
                node.update(offset_x=values[0], offset_y=values[1])
            elif self.name in ("axis", "ticklabels", "axis_title"):
                side = dict(
                    left="left_y", right="right_y", bottom="bottom_x", top="top_x"
                )[self.side]
                axis = cfg[side]
                if self.name == "axis":
                    axis["line_offset"] = values[
                        0 if self.side in ("left", "right") else 1
                    ]
                elif self.name == "axis_title":
                    axis["title_option"].update(offset_x=values[0], offset_y=values[1])
                else:
                    axis["label_style"].update(
                        label_offset_x=values[0], label_offset_y=values[1]
                    )
            elif self.name in ("value_label", "spoke_label"):
                categories = cfg[self.chart._axis(cfg)].get("categories", [])
                i = next(
                    (i for i, c in enumerate(categories) if c["id"] == self.category),
                    None,
                )
                if i is None:
                    raise ValueError("unknown category ID")
                if self.name == "spoke_label":
                    categories[i]["label_offset"] = values
                else:
                    spec = next(
                        (s for s in members if s["series_id"] == self.series), None
                    )
                    if spec is None:
                        raise ValueError("unknown series ID")
                    labels = self.chart._body(spec)["labels"]
                    labels.setdefault("offsets", [[0.0, 0.0] for _ in categories])[
                        i
                    ] = values
            else:
                raise AttributeError("use set_plot_bounds to position the data area")

        self.chart._edit(edit)
        return self

    def remove(self):
        return self.set_offset((0, 0))
