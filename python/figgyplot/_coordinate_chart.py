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
            if (cfg.get("bar_groups") or {}).get("direction") == "Horizontal"
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
        return style_values(
            self.kind,
            self._style(self.axes._config(state), members[0]),
            self.figure.dpi,
        )

    def set_style(self, **properties):
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
        return self.set_style(**style_values(self.kind, defaults, self.figure.dpi))

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
        return self._groups(group_width=number(fraction, "group width"))

    def set_gap(self, points):
        return self._groups(bar_gap=number(points, "gap") * self.figure.dpi / 72)

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
