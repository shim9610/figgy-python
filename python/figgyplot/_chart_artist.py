"""Named controls for bounded charts whose materials have no Matplotlib peer."""

import copy
import json

from ._matplotlib import _number


class ChartAppearance:
    """Figgy extension for shared labels, categorical series and pie slices.

    Data values are never accepted by these appearance setters. Lengths use
    points; IDs refer to the existing chart rather than renderer list offsets.
    """

    def __init__(self, axes):
        from ._charts import family

        self.axes = axes
        self.figure = axes.figure
        self.kind = family(self.figure.get_settings())
        if self.kind is None:
            raise AttributeError("chart appearance requires a bounded chart")

    def _edit(self, operation):
        state = self.figure.get_settings()
        operation(state[self.kind])
        self.figure.apply_settings(state)
        return self

    def reset_style(self):
        from ._native import default_bounded_json, default_radial_json

        state = self.figure.get_settings()
        old = state[self.kind]
        baseline = json.loads(
            default_radial_json()
            if self.kind == "radial"
            else default_bounded_json(self.kind)
        )
        if self.kind == "radial":
            baseline["slices"] = copy.deepcopy(old["slices"])
            for item in baseline["slices"]:
                for key in ("style", "labels", "label_format", "label_color"):
                    item[key] = None
        else:
            baseline.update(
                categories=copy.deepcopy(old["categories"]),
                series=copy.deepcopy(old["series"]),
            )
            for item in baseline["series"]:
                item["style"] = None
        state[self.kind] = baseline
        self.figure.apply_settings(state)

    def set_label_style(self, *, fontsize=None, fontfamily=None, color=None):
        from .figure import _color

        def edit(chart):
            if fontsize is not None:
                pixels = (
                    _number(fontsize, "fontsize", positive=True) * self.figure.dpi / 72
                )
                maximum = 64 if self.kind == "radial" else 32
                if not 8 <= pixels <= maximum:
                    raise ValueError(
                        f"renderer shared label size must be 8..{maximum} logical pixels "
                        f"({8 * 72 / self.figure.dpi:g}..{maximum * 72 / self.figure.dpi:g} points at this DPI)"
                    )
                chart["font_size"] = pixels
            if fontfamily is not None:
                chart["font_family"] = self.figure._check_font(fontfamily)
            if color is not None:
                chart["label_color" if self.kind == "radial" else "text_color"] = (
                    _color(color)
                )

        return self._edit(edit)

    def set_material(self, name):
        from .figure import _material

        if self.kind == "radar":
            raise NotImplementedError("radar charts have no material")
        return self._edit(lambda chart: chart["style"].update(material=_material(name)))

    def set_series(self, id, *, label=None, color=None):
        from .figure import _color

        if self.kind == "radial":
            raise AttributeError("pies use set_slice instead of series")

        def edit(chart):
            item = next((s for s in chart["series"] if s["id"] == id), None)
            if item is None:
                raise ValueError("unknown chart series ID")
            if label is not None:
                item["label"] = str(label)
            if color is not None:
                item["color"] = _color(color)

        return self._edit(edit)

    def set_category_label(self, id, label):
        from ._chart_text import category_label

        def edit(chart):
            item = next((c for c in chart["categories"] if c["id"] == id), None)
            if item is None:
                raise ValueError("unknown category ID")
            item["label"] = category_label(label)

        return self._edit(edit)

    def set_slice(self, index, *, label, color, explode=0):
        from .figure import _color

        if self.kind != "radial":
            raise AttributeError("set_slice requires a pie/donut")
        if not isinstance(index, int) or index < 0:
            raise ValueError("slice index must be a nonnegative integer")

        def edit(chart):
            if index >= len(chart["slices"]):
                raise ValueError("slice index is out of range")
            chart["slices"][index].update(
                label=str(label),
                color=_color(color),
                explode=_number(explode, "explode"),
            )

        return self._edit(edit)

    def set_startangle(self, angle):
        if self.kind != "radial":
            raise AttributeError("start angle requires a pie/donut")
        return self._edit(
            lambda chart: chart.update(start_angle_degrees=-_number(angle, "angle"))
        )

    def set_inner_radius(self, fraction=None):
        if self.kind != "radial":
            raise AttributeError("inner radius requires a pie/donut")
        if fraction is not None:
            fraction = _number(fraction, "inner radius")
            if not 0 < fraction < 1:
                raise ValueError("inner radius must be in (0,1)")
        return self._edit(
            lambda chart: chart.update(
                kind="Pie"
                if fraction is None
                else {"Donut": {"inner_radius": fraction}}
            )
        )

    def set_mode(self, mode):
        modes = {
            "grouped": "Grouped",
            "stacked": "Stacked",
            "percent_stacked": "PercentStacked",
        }
        if self.kind != "categorical" or mode not in modes:
            raise ValueError(
                "mode requires categorical bars: grouped, stacked, percent_stacked"
            )
        return self._edit(lambda chart: chart.update(mode=modes[mode]))

    def set_orientation(self, orientation):
        if self.kind not in ("categorical", "boxplot") or orientation not in (
            "horizontal",
            "vertical",
        ):
            raise ValueError(
                "orientation requires categorical bars/boxes: horizontal or vertical"
            )
        return self._edit(lambda chart: chart.update(direction=orientation.title()))

    def set_group_width(self, fraction):
        value = _number(fraction, "group width")
        if self.kind not in ("categorical", "boxplot") or not 0 < value <= 1:
            raise ValueError("group width requires bars/boxes and a fraction in (0,1]")
        return self._edit(lambda chart: chart.update(group_width=value))

    def set_gap(self, points):
        value = _number(points, "gap")
        if self.kind not in ("categorical", "boxplot") or value < 0:
            raise ValueError("gap requires bars/boxes and a nonnegative length")
        return self._edit(
            lambda chart: chart.update(
                **{
                    "bar_gap" if self.kind == "categorical" else "box_gap": value
                    * self.figure.dpi
                    / 72
                }
            )
        )
