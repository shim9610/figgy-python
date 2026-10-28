"""Named controls for bounded charts whose materials have no Matplotlib peer."""

import copy
import json

from ._matplotlib import _number

_FORMATS = dict(
    value="Value",
    percent="Percent",
    name="Name",
    name_value="NameValue",
    name_percent="NamePercent",
    value_percent="ValuePercent",
    name_value_percent="NameValuePercent",
    category_value="CategoryValue",
)


_LABELS = dict(
    categorical={
        "none": "None",
        "inside": "Inside",
        "outside": "Outside",
        "auto": "Auto",
    },
    boxplot={"none": "None", "median": "Median", "median_and_count": "MedianAndCount"},
    radial={"none": "None", "inside": "Inside", "outside": "Outside"},
    radar={"none": "None", "values": "Values", "emphasized": "Emphasized"},
)


def _placement(kind, value):
    value = "none" if value is False else value
    if value not in _LABELS[kind]:
        raise ValueError(
            f"{kind} label position must be one of: " + ", ".join(_LABELS[kind])
        )
    return _LABELS[kind][value]


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
            baseline["split"] = copy.deepcopy(old.get("split"))
            items = baseline["slices"] + (
                [] if baseline["split"] is None else baseline["split"]["children"]
            )
            for item in items:
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

    def set_plot_bounds(self, bounds=None):
        """Manual plot rectangle (left, top, width, height) in points; None fits automatically."""
        value = None
        if bounds is not None:
            numbers = [_number(v, "plot bounds") * self.figure.dpi / 72 for v in bounds]
            if len(numbers) != 4 or numbers[2] <= 0 or numbers[3] <= 0:
                raise ValueError("bounds require left, top and positive width/height")
            value = dict(zip(("x", "y", "width", "height"), numbers))
        return self._edit(lambda chart: chart["decorations"].update(data_area=value))

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

    def get_style(self):
        """Return reusable style keywords; colors are RGBA tuples, lengths points."""
        from ._appearance import style_values

        return style_values(
            self.kind, self.figure.get_settings()[self.kind]["style"], self.figure.dpi
        )

    def set_style(self, **properties):
        """Set material, outlines, camera, box statistics or radar appearance.

        get_style() lists this chart family's supported keyword arguments.
        Values and registered data bindings are retained.
        """
        from ._appearance import edit_style

        return self._edit(
            lambda chart: edit_style(
                self.kind, chart["style"], self.figure.dpi, properties
            )
        )

    def set_value_labels(
        self, *, position=None, format=None, decimals=None, suffix=None
    ):
        """Choose label placement/content without constructing renderer variants."""

        def edit(chart):
            if position is not None:
                chart["labels"] = _placement(self.kind, position)
            if format is not None:
                names = _FORMATS
                if format not in names:
                    raise ValueError("unknown value label format")
                if "label_format" not in chart:
                    raise NotImplementedError(
                        "this chart has no value-label format selector"
                    )
                chart["label_format"] = names[format]
            if decimals is not None:
                if not isinstance(decimals, int) or not 0 <= decimals <= 15:
                    raise ValueError("decimals must be an integer from 0 to 15")
                chart["label_decimals"] = decimals
            if suffix is not None:
                chart["value_suffix"] = str(suffix)

        return self._edit(edit)

    def series(self, id):
        """Appearance of an existing stable series, independent of its values."""
        return ChartElement(self, "series", id)

    def get_series(self):
        """Return stable series IDs and display labels without renderer state."""
        if self.kind == "radial":
            raise AttributeError("pies have slices instead of series")
        return {
            item["id"]: item["label"]
            for item in self.figure.get_settings()[self.kind]["series"]
        }

    def get_categories(self):
        """Return stable category IDs and display labels."""
        if self.kind == "radial":
            raise AttributeError("pies have slices instead of categories")
        return {
            item["id"]: item["label"]
            for item in self.figure.get_settings()[self.kind]["categories"]
        }

    def get_slice_count(self, *, detail=False):
        if self.kind != "radial":
            raise AttributeError("slice count requires a pie/donut")
        chart = self.figure.get_settings()[self.kind]
        return (
            len(chart["split"]["children"])
            if detail and chart.get("split")
            else (0 if detail else len(chart["slices"]))
        )

    def cell(self, category, series):
        """One categorical bar/box, addressed by category and series IDs."""
        return ChartElement(self, "cell", (category, series))

    def slice(self, index, *, detail=False):
        """One original pie slice, or one child in the detail chart."""
        return ChartElement(self, "detail" if detail else "slice", index)

    def clear_overrides(self):
        def edit(chart):
            if "overrides" not in chart:
                raise AttributeError("this chart has no cell overrides")
            chart["overrides"] = []

        return self._edit(edit)

    def set_ring_spacing(self, spacing=None):
        if self.kind != "radar":
            raise AttributeError("ring spacing requires radar")
        return self._edit(
            lambda chart: chart.update(
                ring_spacing=None
                if spacing is None
                else _number(spacing, "ring spacing", positive=True)
            )
        )

    def set_split(self, index, values, *, labels=None, colors=None, inner_radius=None):
        """Create a pie detail chart. Child values must sum to the parent slice."""
        from .figure import _color, _COLORS

        if self.kind != "radial":
            raise AttributeError("split requires a pie/donut")
        values = list(values)
        labels = (
            [str(i + 1) for i in range(len(values))] if labels is None else list(labels)
        )
        colors = (
            [_COLORS[i % len(_COLORS)] for i in range(len(values))]
            if colors is None
            else list(colors)
        )
        if len(labels) != len(values) or len(colors) != len(values):
            raise ValueError("values, labels and colors must have equal length")
        children = [
            dict(
                label=str(label),
                value=_number(value, "slice value"),
                color=_color(color),
                explode=0.0,
                style=None,
                labels=None,
                label_format=None,
                label_color=None,
            )
            for label, value, color in zip(labels, values, colors)
        ]
        return self._edit(
            lambda chart: chart.update(
                split=dict(
                    slice_index=index,
                    children=children,
                    kind="Pie"
                    if inner_radius is None
                    else {
                        "Donut": dict(
                            inner_radius=_number(inner_radius, "inner radius")
                        )
                    },
                )
            )
        )

    def set_split_inner_radius(self, fraction=None):
        def edit(chart):
            if self.kind != "radial" or chart.get("split") is None:
                raise AttributeError("chart has no detail split")
            chart["split"]["kind"] = (
                "Pie"
                if fraction is None
                else {"Donut": dict(inner_radius=_number(fraction, "inner radius"))}
            )

        return self._edit(edit)

    def decoration(
        self, name, *, side=None, category=None, series=None, index=None, detail=False
    ):
        """Position a named chart decoration in points; IDs survive reordering."""
        simple = dict(title="ChartTitle", legend="Legend", data="DataArea")
        sides = dict(left="Left", right="Right", top="Top", bottom="Bottom")
        if name in simple:
            element = simple[name]
        elif name in ("axis", "ticklabels", "axis_title"):
            if side not in sides:
                raise ValueError("side must be left/right/top/bottom")
            element = {
                dict(axis="Axis", ticklabels="AxisLabel", axis_title="AxisTitle")[
                    name
                ]: sides[side]
            }
        elif name == "value_label":
            element = {"DataLabel": dict(category_id=category, series_id=series)}
        elif name == "spoke_label":
            element = {"SpokeLabel": dict(category_id=category)}
        elif name == "slice_label":
            element = {"RadialLabel": dict(group=int(detail), index=index)}
        elif name == "annotation":
            element = {"Annotation": index}
        else:
            raise ValueError("unknown chart decoration")
        return ChartDecoration(self, element)

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


class ChartElement:
    def __init__(self, chart, kind, key):
        self.chart, self.kind, self.key = chart, kind, key
        self._node(chart.figure.get_settings()[chart.kind], create=False)

    def _node(self, chart, *, create=True):
        if self.kind in ("slice", "detail"):
            if self.chart.kind != "radial":
                raise AttributeError("slice appearance requires a pie")
            if self.kind == "detail" and not chart.get("split"):
                raise ValueError("chart has no split")
            items = (
                chart["slices"] if self.kind == "slice" else chart["split"]["children"]
            )
            if (
                isinstance(self.key, bool)
                or not isinstance(self.key, int)
                or not 0 <= self.key < len(items)
            ):
                raise ValueError("slice index out of range")
            return items[self.key]
        if self.chart.kind == "radial":
            raise AttributeError("pies have slices instead of series")
        if self.kind == "series":
            item = next((s for s in chart["series"] if s["id"] == self.key), None)
            if item is None:
                raise ValueError("unknown series ID")
            return item
        if self.chart.kind not in ("categorical", "boxplot"):
            raise AttributeError("cell overrides require categorical bars or boxes")
        category, series = self.key
        if category not in [c["id"] for c in chart["categories"]] or series not in [
            s["id"] for s in chart["series"]
        ]:
            raise ValueError("unknown category or series ID")
        target = dict(category_id=category, series_id=series)
        item = next((s for s in chart["overrides"] if s["target"] == target), None)
        if item is None:
            item = dict(target=target, color=None, style=None, labels=None)
            if self.chart.kind == "categorical":
                item["label_format"] = None
            if create:
                chart["overrides"].append(item)
        return item

    def _edit(self, operation):
        self.chart._edit(lambda chart: operation(chart, self._node(chart)))
        return self

    def get_style(self):
        """Return this override's public keywords, or None when it inherits."""
        from ._appearance import style_values, convert

        item = self._node(
            self.chart.figure.get_settings()[self.chart.kind], create=False
        )
        style = item.get("style")
        if style is None:
            return None
        if self.chart.kind != "radar":
            return style_values(self.chart.kind, style, self.chart.figure.dpi)
        fields = dict(
            linewidth=("line_width_px", "length"),
            facecolor=("fill", "color"),
            marker=("marker", "shape"),
            markersize=("marker_size_px", "length"),
        )
        return {
            name: None
            if style.get(key) is None
            else convert(style[key], kind, self.chart.figure.dpi, decode=True)
            for name, (key, kind) in fields.items()
        }

    def set_style(self, **properties):
        """Override this element. Native full styles snapshot chart defaults;
        radar per-series fields continue to inherit when set to None.
        """
        from ._appearance import edit_style, convert

        def edit(chart, item):
            if self.chart.kind == "radar":
                fields = dict(
                    linewidth=("line_width_px", "length"),
                    facecolor=("fill", "color"),
                    marker=("marker", "shape"),
                    markersize=("marker_size_px", "length"),
                )
                if set(properties) - fields.keys():
                    raise ValueError(
                        "radar series style supports linewidth, facecolor, marker, markersize"
                    )
                style = item.setdefault("style", None) or dict.fromkeys(
                    v[0] for v in fields.values()
                )
                for name, value in properties.items():
                    key, kind = fields[name]
                    style[key] = (
                        None
                        if value is None
                        else convert(value, kind, self.chart.figure.dpi)
                    )
                item["style"] = style
            else:
                style = copy.deepcopy(
                    chart["style"] if item.get("style") is None else item["style"]
                )
                edit_style(self.chart.kind, style, self.chart.figure.dpi, properties)
                item["style"] = style

        return self._edit(edit)

    def reset_style(self):
        return self._edit(lambda chart, item: item.update(style=None))

    def set_color(self, color):
        from .figure import _color

        if color is None and self.kind != "cell":
            raise ValueError("only cell colors may inherit")
        return self._edit(
            lambda chart, item: item.update(
                color=None if color is None else _color(color)
            )
        )

    def set_label(self, text):
        if self.kind == "cell":
            raise AttributeError("cell labels follow chart value formats")
        return self._edit(lambda chart, item: item.update(label=str(text)))

    def set_explode(self, fraction):
        if self.kind not in ("slice", "detail"):
            raise AttributeError("explode requires a pie slice")
        return self._edit(
            lambda chart, item: item.update(explode=_number(fraction, "explode"))
        )

    def set_value_labels(self, *, position=..., format=..., color=...):
        if self.kind == "series":
            raise AttributeError(
                "series label placement uses chart defaults; override a cell"
            )
        from .figure import _color

        def edit(chart, item):
            if position is not ...:
                item["labels"] = (
                    None if position is None else _placement(self.chart.kind, position)
                )
            if format is not ...:
                if "label_format" not in item:
                    raise AttributeError("this element has no label format override")
                if format is not None and format not in _FORMATS:
                    raise ValueError("unknown label format")
                item["label_format"] = None if format is None else _FORMATS[format]
            if color is not ...:
                if self.kind not in ("slice", "detail"):
                    raise AttributeError("label color overrides require a pie slice")
                item["label_color"] = None if color is None else _color(color)

        return self._edit(edit)


class ChartDecoration:
    def __init__(self, chart, element):
        self.chart, self.element = chart, element

    def set_offset(self, offset):
        values = [
            _number(v, "decoration offset") * self.chart.figure.dpi / 72 for v in offset
        ]
        if len(values) != 2:
            raise ValueError("offset requires two components")

        def edit(chart):
            offsets = chart["decorations"]["offsets"]
            item = next(
                (item for item in offsets if item["element"] == self.element), None
            )
            if item is None:
                offsets.append(dict(element=copy.deepcopy(self.element), offset=values))
            else:
                item["offset"] = values

        return self.chart._edit(edit)

    def remove(self):
        def edit(chart):
            offsets = chart["decorations"]["offsets"]
            offsets[:] = [item for item in offsets if item["element"] != self.element]

        return self.chart._edit(edit)
