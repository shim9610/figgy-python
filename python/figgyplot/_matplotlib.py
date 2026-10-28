"""Public plotting objects; renderer-specific storage stays behind these handles."""

import copy
import json
import math
from dataclasses import dataclass
from contextlib import contextmanager

import numpy as np


@dataclass(frozen=True)
class Bbox:
    x0: float
    y0: float
    width: float
    height: float

    @property
    def bounds(self):
        return self.x0, self.y0, self.width, self.height

    @property
    def x1(self):
        return self.x0 + self.width

    @property
    def y1(self):
        return self.y0 + self.height

    def get_points(self):
        return np.array([[self.x0, self.y0], [self.x1, self.y1]])

    def frozen(self):
        return self


@dataclass(frozen=True)
class Transform:
    axes: object
    kind: str


def canvas_size(state):
    layout = state["identity"].get("layout")
    if layout:
        return tuple(layout["size"])
    areas = [state["config"]["chart_area"]] + [
        p["config"]["chart_area"] for p in state["config"].get("subplots", [])
    ]
    return max(p["x"] + p["width"] for p in areas), max(
        p["y"] + p["height"] for p in areas
    )


def _number(value, name, *, positive=False):
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(
            f"{name} must be finite" + (" and positive" if positive else "")
        )
    return value


class Text:
    """A stable chart/axis title, with sizes in points and ordinary text setters."""

    def __init__(self, axes, role):
        self.axes, self.role = axes, role

    def _node(self, state):
        from ._charts import family

        kind = family(state)
        if kind:
            if self.role != "title":
                raise NotImplementedError(
                    "independent bounded axis-label typography is not supported by the renderer"
                )
            from ._chart_text import title_options

            return title_options(state[kind])
        if self.role == "ylabel" and self.axes.overlay_id:
            return self.axes._overlay(state)["y_axis"]["title_option"]
        cfg = self.axes._config(state)
        sides = {
            "xlabel": "bottom_x",
            "ylabel": "left_y",
            "toplabel": "top_x",
            "rightlabel": "right_y",
        }
        return (
            cfg["chart_title"]
            if self.role == "title"
            else cfg[sides[self.role]]["title_option"]
        )

    def get_text(self):
        from .figure import _text
        from ._charts import family

        state = self.axes.figure.get_settings()
        kind = family(state)
        if kind and self.role != "title":
            horizontal = state[kind].get("direction") == "Horizontal"
            return state[kind][
                "value_title"
                if (self.role == "xlabel") == horizontal
                else "category_title"
            ]
        return _text(self._node(state)["text"])

    def set_text(self, value):
        self.set(text=value)

    def get_fontsize(self):
        return (
            self._node(self.axes.figure.get_settings())["text"]["font_size"]
            * 72
            / self.axes.figure.dpi
        )

    def get_color(self):
        c = self._node(self.axes.figure.get_settings())["text"]["color"]
        return tuple(c[k] for k in "rgba")

    def get_fontfamily(self):
        return [self._node(self.axes.figure.get_settings())["text"]["font"]]

    def get_visible(self):
        return self._node(self.axes.figure.get_settings())["visible"]

    def get_fontweight(self):
        segments = self._node(self.axes.figure.get_settings())["text"]["segments"]
        weights = {s["bold"] for s in segments}
        if len(weights) > 1:
            raise NotImplementedError("this rich text has mixed font weights")
        return "bold" if weights == {True} else "normal"

    def get_fontstyle(self):
        styles = {
            s["italic"]
            for s in self._node(self.axes.figure.get_settings())["text"]["segments"]
        }
        if len(styles) > 1:
            raise NotImplementedError("this rich text has mixed font styles")
        return "italic" if styles == {True} else "normal"

    def set(self, **properties):
        from .figure import _color

        aliases = {
            "size": "fontsize",
            "family": "fontfamily",
            "weight": "fontweight",
            "style": "fontstyle",
        }
        properties = {aliases.get(k, k): v for k, v in properties.items()}
        allowed = {
            "fontsize",
            "fontfamily",
            "fontweight",
            "fontstyle",
            "color",
            "visible",
            "text",
            "multialignment",
        }
        if set(properties) - allowed:
            raise ValueError(
                "unsupported Text properties: "
                + ", ".join(sorted(set(properties) - allowed))
            )
        fig = self.axes.figure
        state = fig.get_settings()
        node = self._node(state)
        rich = node["text"]
        for key, value in properties.items():
            if key == "fontsize":
                rich["font_size"] = (
                    _number(value, "fontsize", positive=True) * fig.dpi / 72
                )
            elif key == "fontfamily":
                font = value[0] if isinstance(value, (list, tuple)) else value
                rich["font"] = fig._check_font(font)
            elif key == "color":
                rich["color"] = _color(value)
            elif key == "visible":
                node["visible"] = bool(value)
            elif key == "multialignment":
                if value not in ("left", "center", "right"):
                    raise ValueError("multialignment must be left, center or right")
                rich["align"] = value.title()
            elif key == "text":
                from .figure import _segments
                from ._charts import family

                if family(state):
                    from ._chart_text import set_title_text

                    set_title_text(state[family(state)], value)
                else:
                    rich["segments"] = _segments(value)
            elif key in ("fontweight", "fontstyle"):
                if key == "fontweight":
                    if value not in ("normal", "bold", 400, 700):
                        raise NotImplementedError(
                            "renderer supports normal and bold font weights"
                        )
                    flag = "bold"
                    enabled = value in ("bold", 700)
                else:
                    if value not in ("normal", "italic"):
                        raise NotImplementedError(
                            "renderer supports normal and italic font styles"
                        )
                    flag = "italic"
                    enabled = value != "normal"
                for segment in rich["segments"]:
                    segment[flag] = enabled
        if (
            self.role == "title"
            and not state.get("categorical")
            and not state.get("boxplot")
            and not state.get("radar")
            and not state.get("radial")
        ):
            if set(properties) & {
                "fontsize",
                "fontfamily",
                "text",
                "visible",
                "fontweight",
                "fontstyle",
            }:
                from ._native import fitted_chart_title_margin

                cfg = self.axes._config(state)
                cfg["chart_title"]["top_margin"] = fitted_chart_title_margin(
                    json.dumps(cfg, allow_nan=False)
                )
        fig.apply_settings(state)
        return self

    def set_fontsize(self, value):
        self.set(fontsize=value)

    def set_color(self, value):
        self.set(color=value)

    def set_fontfamily(self, value):
        self.set(fontfamily=value)

    def set_fontweight(self, value):
        self.set(fontweight=value)

    def set_fontstyle(self, value):
        self.set(fontstyle=value)

    def set_visible(self, value):
        self.set(visible=value)

    def set_multialignment(self, value):
        self.set(multialignment=value)

    def set_offset(self, offset):
        """Figgy extension: title offset in points in the title's local frame."""
        x, y = offset
        fig = self.axes.figure
        state = fig.get_settings()
        node = self._node(state)
        if "offset_x" not in node:
            raise NotImplementedError("bounded title offsets are automatic")
        node["offset_x"] = _number(x, "x offset") * fig.dpi / 72
        node["offset_y"] = _number(y, "y offset") * fig.dpi / 72
        fig.apply_settings(state)

    def set_layout_height(self, height):
        """Figgy extension: reserve a title band, in points, without moving data."""
        if self.role != "title":
            raise NotImplementedError("only chart titles have a title band")
        fig = self.axes.figure
        state = fig.get_settings()
        node = self._node(state)
        if "top_margin" not in node:
            raise NotImplementedError("bounded title layout is automatic")
        value = _number(height, "title band height") * fig.dpi / 72
        if value < 0:
            raise ValueError("title band height must be nonnegative")
        node["top_margin"] = value
        fig.apply_settings(state)


class Spine:
    def __init__(self, axes, side):
        self.axes, self.side = axes, side

    def _node(self, state):
        self.axes.figure._require_cartesian()
        if self.side == "right" and self.axes.overlay_id:
            return self.axes._overlay(state)["y_axis"]
        return self.axes._config(state)[
            {
                "bottom": "bottom_x",
                "top": "top_x",
                "left": "left_y",
                "right": "right_y",
            }[self.side]
        ]

    def get_visible(self):
        return self._node(self.axes.figure.get_settings())["line_visible"]

    def get_linewidth(self):
        return (
            self._node(self.axes.figure.get_settings())["line_width"]
            * 72
            / self.axes.figure.dpi
        )

    def get_edgecolor(self):
        c = self._node(self.axes.figure.get_settings())["line_color"]
        return tuple(c[k] for k in "rgba")

    def set(self, **properties):
        from .figure import _color, _LINES

        fig = self.axes.figure
        state = fig.get_settings()
        node = self._node(state)
        for key, value in properties.items():
            if key == "visible":
                node["line_visible"] = bool(value)
            elif key in ("color", "edgecolor"):
                node["line_color"] = _color(value)
            elif key in ("linewidth", "lw"):
                node["line_width"] = _number(value, "linewidth") * fig.dpi / 72
            elif key in ("linestyle", "ls"):
                node["line_style"] = _LINES.get(value, value)
            else:
                raise ValueError(f"unsupported spine property: {key}")
        fig.apply_settings(state)
        return self

    def set_visible(self, value):
        self.set(visible=value)

    def set_color(self, value):
        self.set(color=value)

    def set_edgecolor(self, value):
        self.set(edgecolor=value)

    def set_linewidth(self, value):
        self.set(linewidth=value)

    def set_linestyle(self, value):
        self.set(linestyle=value)

    def set_position(self, position):
        if (
            not isinstance(position, (tuple, list))
            or len(position) != 2
            or position[0] != "outward"
        ):
            raise NotImplementedError("spine position supports (outward, points) only")
        fig = self.axes.figure
        state = fig.get_settings()
        node = self._node(state)
        node["line_offset"] = _number(position[1], "spine offset") * fig.dpi / 72
        fig.apply_settings(state)

    def get_position(self):
        return "outward", self._node(self.axes.figure.get_settings())[
            "line_offset"
        ] * 72 / self.axes.figure.dpi


class Axis:
    def __init__(self, axes, dimension, side=None):
        self.axes, self.dimension, self.side = axes, dimension, side

    @property
    def label(self):
        return Text(
            self.axes,
            {"top": "toplabel", "right": "rightlabel"}.get(
                self.side, "xlabel" if self.dimension == "x" else "ylabel"
            ),
        )

    def set_label_text(self, label, **kwargs):
        self.label.set(text=label, **kwargs)
        return self.label

    def get_view_interval(self):
        node = self._nodes(self.axes.figure.get_settings())[0]
        values = [node["min"], node["max"]]
        return np.array(values[::-1] if node["inverted"] else values)

    def set_view_interval(self, vmin, vmax, ignore=False):
        low = _number(vmin, "minimum")
        high = _number(vmax, "maximum")
        if low == high:
            raise ValueError("limits must be different")
        fig = self.axes.figure
        state = fig.get_settings()
        node = self._nodes(state)[0]
        node.update(min=min(low, high), max=max(low, high), inverted=low > high)
        fig.apply_settings(state)

    def set_tick_params(self, which="major", reset=False, **kwargs):
        return self.axes._tick_params(
            axis=self.dimension,
            which=which,
            reset=reset,
            sides=None if self.side is None else [self.side],
            **kwargs,
        )

    def _nodes(self, state):
        self.axes.figure._require_cartesian()
        cfg = self.axes._config(state)
        if self.side:
            key = {
                "bottom": "bottom_x",
                "top": "top_x",
                "left": "left_y",
                "right": "right_y",
            }[self.side]
            return [
                self.axes._overlay(state)["y_axis"]
                if self.axes.overlay_id and self.side == "right"
                else cfg[key]
            ]
        if self.dimension == "y" and self.axes.overlay_id:
            return [self.axes._overlay(state)["y_axis"]]
        return [
            cfg[k]
            for k in (
                ("bottom_x", "top_x")
                if self.dimension == "x"
                else ("left_y", "right_y")
            )
        ]

    def set_major_locator(self, locator):
        from .ticker import AutoLocator, LogLocator, MultipleLocator
        from . import _document

        fig = self.axes.figure
        state = fig.get_settings()
        nodes = self._nodes(state)
        if isinstance(locator, AutoLocator):
            low, high = nodes[0]["min"], nodes[0]["max"]
            return getattr(self.axes, "set_" + self.dimension + "lim")(low, high)
        if isinstance(locator, LogLocator):
            if nodes[0]["scale"] != "Logarithmic":
                raise ValueError("LogLocator requires a logarithmic axis")
            for node in nodes:
                node["major_spacing"] = math.log10(locator.base)
            return fig.apply_settings(state)
        if not hasattr(locator, "tick_values"):
            raise TypeError("locator must provide tick_values(vmin,vmax)")
        if nodes[0]["scale"] != "Linear":
            raise NotImplementedError("MultipleLocator requires a linear axis")
        values = np.asarray(
            locator.tick_values(nodes[0]["min"], nodes[0]["max"]), dtype=float
        )
        diffs = np.diff(values)
        if (
            len(diffs) < 1
            or not np.isfinite(values).all()
            or not np.allclose(diffs, diffs[0])
            or diffs[0] <= 0
        ):
            raise NotImplementedError(
                "the renderer supports regular major tick locators"
            )
        step = locator.base if isinstance(locator, MultipleLocator) else float(diffs[0])
        if not np.allclose(values / step, np.round(values / step), rtol=0, atol=1e-7):
            raise NotImplementedError(
                "offset or arbitrary-position major ticks need renderer support"
            )
        for node in nodes:
            node["major_spacing"] = step
        key = (
            {
                "bottom": "bottom_x",
                "top": "top_x",
                "left": "left_y",
                "right": "right_y",
            }[self.side]
            if self.side
            else "bottom_x"
            if self.dimension == "x"
            else "left_y"
        )
        if self.axes.overlay_id and self.dimension == "y":
            key = "y_axis"
        _document.set_tick_mode(
            state, self.axes.subplot_id, self.axes.overlay_id, key, False, spacing=step
        )
        fig.apply_settings(state)

    def set_layout_margin(self, value):
        """Figgy extension: outer axis margin in points."""
        fig = self.axes.figure
        state = fig.get_settings()
        for node in self._nodes(state):
            node["out_margin"] = _number(value, "axis margin") * fig.dpi / 72
        fig.apply_settings(state)

    def set_ticklabel_offset(self, offset):
        """Figgy extension: numeric-label translation in points."""
        fig = self.axes.figure
        state = fig.get_settings()
        x, y = offset
        for node in self._nodes(state):
            node["label_style"]["label_offset_x"] = (
                _number(x, "x offset") * fig.dpi / 72
            )
            node["label_style"]["label_offset_y"] = (
                _number(y, "y offset") * fig.dpi / 72
            )
        fig.apply_settings(state)

    def get_major_locator(self):
        from .ticker import MultipleLocator

        return MultipleLocator(
            self._nodes(self.axes.figure.get_settings())[0]["major_spacing"]
        )

    def set_tick_auto(self, automatic=True):
        """Figgy extension: keep the current spacing but choose future auto/fixed ticks."""
        from . import _document

        fig = self.axes.figure
        state = fig.get_settings()
        sides = (
            [self.side]
            if self.side
            else ["bottom", "top"]
            if self.dimension == "x"
            else ["left", "right"]
        )
        for side in sides:
            key = {
                "bottom": "bottom_x",
                "top": "top_x",
                "left": "left_y",
                "right": "right_y",
            }[side]
            if self.axes.overlay_id and self.dimension == "y":
                key = "y_axis"
            _document.set_tick_mode(
                state,
                self.axes.subplot_id,
                self.axes.overlay_id,
                key,
                bool(automatic),
                paired=False,
            )
        fig.apply_settings(state)

    def set_minor_locator(self, locator):
        from .ticker import AutoMinorLocator

        if not isinstance(locator, AutoMinorLocator):
            # Matplotlib's public object has no subdivision getter; accepting a
            # guessed private attribute would conceal a different contract.
            raise NotImplementedError(
                "use figgyplot.ticker.AutoMinorLocator for renderer subdivisions"
            )
        fig = self.axes.figure
        state = fig.get_settings()
        for node in self._nodes(state):
            node["minor_count"] = locator.n - 1
        fig.apply_settings(state)

    def set_major_formatter(self, formatter):
        from .ticker import SignificantFormatter

        if not isinstance(formatter, SignificantFormatter):
            raise NotImplementedError(
                "arbitrary tick labels are not supported; use figgyplot.ticker.SignificantFormatter"
            )
        fig = self.axes.figure
        state = fig.get_settings()
        for node in self._nodes(state):
            node["label_style"].update(
                format={
                    "plain": "Decimal",
                    "scientific": "Scientific",
                    "power": "Power",
                }[formatter.style],
                significant_digits=formatter.precision,
            )
        fig.apply_settings(state)


class LegendFrame:
    def __init__(self, legend):
        self.legend = legend

    def set(self, **kwargs):
        from .figure import _color

        fig = self.legend.axes.figure
        state = fig.get_settings()
        node = self.legend._node(state)
        for key, value in kwargs.items():
            if key == "facecolor":
                node["bg_color"] = _color(value)
            elif key == "edgecolor":
                node["border_color"] = _color(value)
            elif key == "alpha":
                alpha = _number(value, "alpha")
                if not 0 <= alpha <= 1:
                    raise ValueError("alpha must be in 0..1")
                node["bg_color"]["a"] = node["border_color"]["a"] = alpha
            else:
                raise NotImplementedError(
                    f"legend frame property {key!r} is not supported"
                )
        fig.apply_settings(state)

    def set_facecolor(self, value):
        self.set(facecolor=value)

    def set_edgecolor(self, value):
        self.set(edgecolor=value)

    def set_alpha(self, value):
        self.set(alpha=value)

    def get_facecolor(self):
        color = self.legend._node(self.legend.axes.figure.get_settings())["bg_color"]
        return tuple(color[k] for k in "rgba")

    def get_edgecolor(self):
        color = self.legend._node(self.legend.axes.figure.get_settings())[
            "border_color"
        ]
        return tuple(color[k] for k in "rgba")


class Legend:
    def __init__(self, axes):
        self.axes = axes

    def _node(self, state):
        from ._charts import family

        if family(state):
            raise NotImplementedError(
                "bounded legend typography is part of chart label styling"
            )
        if self.axes.overlay_id:
            owner = self.axes._overlay(state)
            if owner.get("legend") is None:
                raise ValueError("create the secondary legend with legend() first")
            return owner["legend"]
        return self.axes._config(state)["legend"]

    def get_frame(self):
        return LegendFrame(self)

    def get_visible(self):
        from ._charts import family

        state = self.axes.figure.get_settings()
        kind = family(state)
        return state[kind]["legend"] if kind else self._node(state)["visible"]

    def set_visible(self, value):
        from ._charts import family

        fig = self.axes.figure
        state = fig.get_settings()
        kind = family(state)
        if kind:
            state[kind]["legend"] = bool(value)
        else:
            self._node(state)["visible"] = bool(value)
        fig.apply_settings(state)

    def set_loc(self, value):
        from .figure import _legend_corner

        fig = self.axes.figure
        state = fig.get_settings()
        self._node(state)["corner"] = _legend_corner(value)
        fig.apply_settings(state)

    def set_fontsize(self, value):
        fig = self.axes.figure
        state = fig.get_settings()
        self._node(state)["content"]["font_size"] = (
            _number(value, "fontsize", positive=True) * fig.dpi / 72
        )
        fig.apply_settings(state)

    def set_offset(self, offset):
        """Figgy extension: offset the legend by points in screen directions."""
        fig = self.axes.figure
        state = fig.get_settings()
        node = self._node(state)
        node["offset_x"], node["offset_y"] = (
            _number(v, "legend offset") * fig.dpi / 72 for v in offset
        )
        fig.apply_settings(state)


class ArtistMethods:
    def _spec(self, state):
        try:
            return next(s for s in state["series"] if s["series_id"] == self.id)
        except StopIteration:
            raise ValueError(f"artist {self.id!r} no longer exists") from None

    def _body(self, state):
        return next(iter(self._spec(state)["render_type"].values()))

    def get_gid(self):
        return self.id

    def get_label(self):
        from .figure import _text

        label = self._spec(self.figure.get_settings()).get("label")
        return "" if label is None else _text(label)

    def get_color(self):
        body = self._body(self.figure.get_settings())
        for part, key in [
            ("line", "line_color"),
            ("scatter", "point_color"),
            ("bar", "fill_color"),
            ("style", "color"),
        ]:
            if key in body.get(part, {}):
                return tuple(body[part][key][k] for k in "rgba")
        raise NotImplementedError(
            "this artist uses a color scale rather than one color"
        )

    def get_linewidth(self):
        body = self._body(self.figure.get_settings())
        for part, key in [
            ("line", "line_width"),
            ("bar", "border_width"),
            ("style", "width_px"),
        ]:
            if key in body.get(part, {}):
                return body[part][key] * 72 / self.figure.dpi
        raise AttributeError("artist has no line")

    def get_markersize(self):
        scatter = self._body(self.figure.get_settings()).get("scatter")
        if scatter is None:
            raise AttributeError("artist has no stored marker size; add a marker first")
        return scatter["point_size"] * 144 / self.figure.dpi

    def set_markersize(self, value):
        return self.figure.update(self.id, markersize=value)

    def get_linestyle(self):
        from .figure import _LINES

        value = self._body(self.figure.get_settings())["line"]["line_style"]
        return {v: k for k, v in _LINES.items()}.get(value, value)

    def set_linestyle(self, value):
        return self.figure.update(self.id, linestyle=value)

    def get_marker(self):
        from .figure import _MARKERS

        scatter = self._body(self.figure.get_settings()).get("scatter")
        if scatter is None:
            return "None"
        value = scatter["point_shape"]
        return {v: k for k, v in _MARKERS.items()}.get(value, value)

    def set_marker(self, value):
        from .figure import _MARKERS

        fig = self.figure
        state = fig.get_settings()
        body = self._body(state)
        if value in (None, "", "None", "none", " "):
            if set(self._spec(state)["render_type"]) == {"Line"}:
                return
            raise NotImplementedError(
                "removing markers while retaining their hidden style is not supported"
            )
        if "scatter" not in body:
            spec = self._spec(state)
            if set(spec["render_type"]) != {"Line"}:
                raise NotImplementedError("this artist has no editable point markers")
            # A renderer variant is a storage detail, not a reason to make users
            # recreate or upload a plotted line merely to add markers.
            body["scatter"] = dict(
                point_shape="CircleFilled",
                point_color=copy.deepcopy(body["line"]["line_color"]),
                point_size=6 * fig.dpi / 144,
            )
            spec["render_type"] = {"ScatterLine": body}
        body["scatter"]["point_shape"] = _MARKERS.get(value, value)
        fig.apply_settings(state)

    def set_facecolor(self, value):
        from .figure import _color

        fig = self.figure
        state = fig.get_settings()
        body = self._body(state)
        if "fill_color" in body.get("line", {}):
            body["line"]["fill_color"] = _color(value)
        elif "fill_color" in body.get("bar", {}):
            body["bar"]["fill_color"] = _color(value)
        elif "scatter" in body:
            body["scatter"]["point_color"] = _color(value)
        else:
            raise NotImplementedError("this artist has no independent face color")
        fig.apply_settings(state)

    def set_edgecolor(self, value):
        from .figure import _color

        fig = self.figure
        state = fig.get_settings()
        body = self._body(state)
        if "bar" not in body:
            raise NotImplementedError(
                "this renderer has no independent marker edge color"
            )
        body["bar"]["border_color"] = _color(value)
        fig.apply_settings(state)

    def set_baseline(self, value):
        """Figgy extension: baseline of an existing histogram."""
        fig = self.figure
        state = fig.get_settings()
        self._body(state)["bar"]["baseline"] = _number(value, "baseline")
        fig.apply_settings(state)

    def set_bar_width(self, ratio=1.0, *, gap=0.0):
        """Figgy extension: fraction of each bin and gap in points."""
        ratio = _number(ratio, "bar width")
        gap = _number(gap, "bar gap")
        if not 0 < ratio <= 1 or gap < 0:
            raise ValueError("bar width must be in (0,1] and gap nonnegative")
        fig = self.figure
        state = fig.get_settings()
        self._body(state)["bar"].update(width_ratio=ratio, gap_px=gap * fig.dpi / 72)
        fig.apply_settings(state)

    def set_orientation(self, value):
        """Figgy extension: use an existing histogram's horizontal/vertical mapping."""
        if value not in ("horizontal", "vertical"):
            raise ValueError("orientation must be horizontal or vertical")
        fig = self.figure
        state = fig.get_settings()
        self._body(state)["bar"]["orientation"] = value.title()
        fig.apply_settings(state)

    def set_errorbar_style(self, *, color, width, capsize, capthick):
        """Figgy extension: restyle existing errors with errorbar argument units."""
        from .figure import _color

        fig = self.figure
        state = fig.get_settings()
        body = self._body(state)
        if "err_style" not in body:
            raise AttributeError("artist has no error bars")
        values = [_number(v, "errorbar size") for v in [width, capsize, capthick]]
        if min(values) < 0:
            raise ValueError("errorbar sizes must be nonnegative")
        node = body["err_style"]
        node["error_bar_color"] = _color(color)
        for key, value in zip(
            ("error_bar_width", "error_bar_cap_size", "cap_width"), values
        ):
            node[key] = value * fig.dpi / 72
        fig.apply_settings(state)

    def set_drawstyle(self, value):
        modes = {
            "default": "Linear",
            "steps-pre": "StepPre",
            "steps-post": "StepPost",
            "steps-mid": "StepMid",
        }
        if value not in modes:
            raise ValueError("unsupported drawstyle")
        fig = self.figure
        state = fig.get_settings()
        self._body(state)["line"]["interpolation"] = modes[value]
        fig.apply_settings(state)

    def set_cmap(self, value):
        self.figure.update(self.id, cmap=value)

    def set_clim(self, vmin=None, vmax=None):
        if vmax is None and vmin is not None and not np.isscalar(vmin):
            vmin, vmax = vmin
        props = {k: v for k, v in [("vmin", vmin), ("vmax", vmax)] if v is not None}
        self.figure.update(self.id, **props)

    def get_clim(self):
        axis = self._colorbar()["axis"]
        return axis["min"], axis["max"]

    def get_cmap(self):
        return self._colorbar()["colormap"]

    def _colorbar(self):
        state = self.figure.get_settings()
        body = self._body(state)
        if not (
            "matrix" in body
            or body.get("scatter", {}).get("point_color_map")
            or body.get("style", {}).get("color_map")
        ):
            raise AttributeError("artist is not scalar-mapped")
        for ax in self.figure.axes:
            if any(s["series_id"] == self.id for s in ax._owned_series(state)):
                return ax._config(state)["colorbar"]
        raise ValueError("artist has no owning Axes")

    def set_alpha(self, value):
        alpha = _number(value, "alpha")
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be in 0..1")
        fig = self.figure
        state = fig.get_settings()
        body = self._body(state)
        if body.get("scatter", {}).get("point_color_map") or body.get("style", {}).get(
            "color_map"
        ):
            raise NotImplementedError(
                "independent scalar-mapped opacity requires renderer support"
            )

        def opacity(node):
            if isinstance(node, dict) and set(node) == set("rgba"):
                node["a"] = alpha
                return True
            values = (
                node.values()
                if isinstance(node, dict)
                else node
                if isinstance(node, list)
                else ()
            )
            changed = False
            for value in values:
                # Visit every per-point/bin override, not just the base color.
                changed = opacity(value) or changed
            return changed

        found = False
        for part in ("line", "scatter", "bar", "style", "err_style"):
            found = opacity(body.get(part, {})) or found
        if not found:
            raise NotImplementedError("scalar-mapped opacity requires renderer support")
        fig.apply_settings(state)


class AxesMethods:
    @property
    def chart(self):
        """Figgy's named appearance controls for bounded chart families."""
        from ._chart_artist import ChartAppearance

        return ChartAppearance(self)

    def get_panel_position(self):
        """Figgy extension: outer panel bounds, in Figure fractions."""
        state = self.figure.get_settings()
        w, h = canvas_size(state)
        area = self._config(state)["chart_area"]
        return Bbox(
            area["x"] / w,
            1 - (area["y"] + area["height"]) / h,
            area["width"] / w,
            area["height"] / h,
        )

    def set_panel_position(self, bounds):
        """Figgy extension: position the panel including its labels and title."""
        left, bottom, width, height = map(
            float, bounds.bounds if hasattr(bounds, "bounds") else bounds
        )
        if (
            not all(math.isfinite(v) for v in [left, bottom, width, height])
            or width <= 0
            or height <= 0
        ):
            raise ValueError("invalid panel position")
        state = self.figure.get_settings()
        w, h = canvas_size(state)
        self._config(state)["chart_area"] = dict(
            x=round(left * w),
            y=round((1 - bottom - height) * h),
            width=round(width * w),
            height=round(height * h),
        )
        self.figure.apply_settings(state)

    @property
    def transAxes(self):
        return Transform(self, "axes fraction")

    @property
    def transData(self):
        return Transform(self, "data")

    def secondary_xaxis(self, location, functions=None, **kwargs):
        if location not in ("top", "bottom") or functions is not None or kwargs:
            raise NotImplementedError(
                "only an existing top/bottom axis with the same transform is supported"
            )
        return SecondaryAxes(self, "x", location)

    def secondary_yaxis(self, location, functions=None, **kwargs):
        if location not in ("left", "right") or functions is not None or kwargs:
            raise NotImplementedError(
                "only an existing left/right axis with the same transform is supported"
            )
        return SecondaryAxes(self, "y", location)

    def set_xticks(self, ticks, labels=None, *, minor=False, **kwargs):
        return self._set_ticks("x", ticks, labels, minor, kwargs)

    def set_yticks(self, ticks, labels=None, *, minor=False, **kwargs):
        return self._set_ticks("y", ticks, labels, minor, kwargs)

    def _set_ticks(self, dim, ticks, labels, minor, kwargs):
        from .ticker import MultipleLocator

        if labels is not None or minor or kwargs:
            raise NotImplementedError(
                "explicit labels/minor ticks need renderer support; use tick_params for styling"
            )
        values = np.asarray(ticks, dtype=float)
        steps = np.diff(values)
        if (
            len(steps) < 1
            or not np.isfinite(values).all()
            or steps[0] <= 0
            or not np.allclose(steps, steps[0])
            or not np.allclose(values / steps[0], np.round(values / steps[0]))
        ):
            raise NotImplementedError(
                "the renderer supports regular zero-aligned ticks only"
            )
        # Explicit positions must cover the complete view; otherwise a spacing
        # would introduce ticks the caller did not request.
        low, high = sorted(getattr(self, "get_" + dim + "lim")())
        expected = (
            np.arange(math.ceil(low / steps[0]), math.floor(high / steps[0]) + 1)
            * steps[0]
        )
        if values.shape != expected.shape or not np.allclose(values, expected):
            raise NotImplementedError(
                "tick positions must cover the view; arbitrary tick clipping needs renderer support"
            )
        getattr(self, dim + "axis").set_major_locator(MultipleLocator(steps[0]))

    def _plot_rectangle(self, state=None):
        state = self.figure.get_settings() if state is None else state
        from ._native import editor_catalog_json

        catalog = json.loads(
            editor_catalog_json(json.dumps(state, allow_nan=False), None)
        )
        owner = next(
            item for item in catalog if item["id"] == "panel/" + self.subplot_id
        )
        bounds = next(
            field["value"]
            for field in owner["fields"]
            if field["id"] == "Plot area/bounds"
        )
        if len(bounds) != 4:
            raise NotImplementedError(
                "automatic bounded plot geometry is not exposed by the renderer"
            )
        area = self._config(state)["chart_area"]
        return [bounds[0] + area["x"], bounds[1] + area["y"], bounds[2], bounds[3]]

    def get_position(self, original=False):
        state = self.figure.get_settings()
        width, height = canvas_size(state)
        x, y, w, h = self._plot_rectangle(state)
        return Bbox(x / width, 1 - (y + h) / height, w / width, h / height)

    def set_position(self, pos, which="both"):
        if which != "both":
            raise NotImplementedError(
                "the renderer has one active/original plot rectangle"
            )
        values = pos.bounds if hasattr(pos, "bounds") else pos
        left, bottom, width, height = map(float, values)
        if (
            not all(math.isfinite(v) for v in [left, bottom, width, height])
            or width <= 0
            or height <= 0
        ):
            raise ValueError("invalid axes position")
        state = self.figure.get_settings()
        w, h = canvas_size(state)
        area = self._config(state)["chart_area"]
        bounds = [
            left * w - area["x"],
            (1 - bottom - height) * h - area["y"],
            width * w,
            height * h,
        ]
        self.figure.edit_property(
            "panel/" + self.subplot_id, "Plot area/bounds", bounds
        )

    @property
    def xaxis(self):
        return Axis(self, "x")

    @property
    def yaxis(self):
        return Axis(self, "y")

    @property
    def title(self):
        return Text(self, "title")

    @property
    def spines(self):
        return {side: Spine(self, side) for side in ["left", "right", "bottom", "top"]}

    @property
    def lines(self):
        return [
            self.figure._artist_for(s["series_id"])
            for s in self._owned_series(self.figure.get_settings())
            if next(iter(s["render_type"])) in ("Line", "ScatterLine")
        ]

    @property
    def collections(self):
        return [
            self.figure._artist_for(s["series_id"])
            for s in self._owned_series(self.figure.get_settings())
            if next(iter(s["render_type"])) in ("Scatter", "Vector")
        ]

    def get_lines(self):
        return self.lines

    def get_xaxis(self):
        return self.xaxis

    def get_yaxis(self):
        return self.yaxis

    def get_legend(self):
        from ._charts import family

        state = self.figure.get_settings()
        kind = family(state)
        if kind:
            return Legend(self) if state[kind].get("legend") else None
        node = (
            self._overlay(state).get("legend")
            if self.overlay_id
            else self._config(state)["legend"]
        )
        return (
            Legend(self)
            if node and (node["visible"] or node["content"]["segments"])
            else None
        )

    def get_xlabel(self):
        return self.xaxis.label.get_text()

    def get_ylabel(self):
        return self.yaxis.label.get_text()

    def get_title(self):
        return self.title.get_text()

    def get_xlim(self):
        from ._charts import family

        state = self.figure.get_settings()
        kind = family(state)
        if kind:
            if (
                kind in ("categorical", "boxplot")
                and state[kind]["direction"] == "Horizontal"
                and state[kind]["value_range"] is not None
            ):
                return tuple(state[kind]["value_range"])
            raise NotImplementedError(
                "the renderer does not expose automatic bounded-axis limits"
            )
        cfg = self._config(self.figure.get_settings())["bottom_x"]
        values = (cfg["min"], cfg["max"])
        return values[::-1] if cfg["inverted"] else values

    def get_ylim(self):
        from ._charts import family

        state = self.figure.get_settings()
        kind = family(state)
        if kind:
            if (
                kind in ("categorical", "boxplot", "radar")
                and state[kind].get("direction", "Vertical") == "Vertical"
                and state[kind]["value_range"] is not None
            ):
                return tuple(state[kind]["value_range"])
            raise NotImplementedError(
                "the renderer does not expose automatic bounded-axis limits"
            )
        cfg = (
            self._overlay(state)["y_axis"]
            if self.overlay_id
            else self._config(state)["left_y"]
        )
        values = (cfg["min"], cfg["max"])
        return values[::-1] if cfg["inverted"] else values

    def xaxis_inverted(self):
        return self.get_xlim()[0] > self.get_xlim()[1]

    def yaxis_inverted(self):
        return self.get_ylim()[0] > self.get_ylim()[1]

    def set(self, **properties):
        supported = {"title", "xlabel", "ylabel", "xlim", "ylim", "xscale", "yscale"}
        if set(properties) - supported:
            raise AttributeError(
                "unsupported Axes properties: "
                + ", ".join(sorted(set(properties) - supported))
            )
        result = []
        with self.figure.batch_update():
            for key, value in properties.items():
                method = getattr(self, "set_" + key)
                result.append(
                    method(*value) if key in ("xlim", "ylim") else method(value)
                )
        return result

    def _limits(self, dimension, first, second, minimum, maximum):
        from ._charts import family

        if minimum is not None:
            if first is not None:
                raise TypeError("both lower limit and its alias were supplied")
            first = minimum
        if maximum is not None:
            if second is not None:
                raise TypeError("both upper limit and its alias were supplied")
            second = maximum
        if second is None and first is not None and not np.isscalar(first):
            first, second = first
        if first is None or second is None:
            old = getattr(self, "get_" + dimension + "lim")()
            first = old[0] if first is None else first
            second = old[1] if second is None else second
        first = _number(first, "limit")
        second = _number(second, "limit")
        if first == second:
            raise ValueError("limits must be different")
        kind = family(self.figure.get_settings())
        if kind and first > second:
            raise NotImplementedError(
                "this bounded renderer does not support reversed value axes"
            )
        with self.figure.batch_update():
            self._set_bounds(dimension, min(first, second), max(first, second))
            if not kind:
                state = self.figure.get_settings()
                cfg = self._config(state)
                keys = (
                    ("bottom_x", "top_x") if dimension == "x" else ("left_y", "right_y")
                )
                for key in keys:
                    node = (
                        self._overlay(state)["y_axis"]
                        if self.overlay_id and dimension == "y"
                        else cfg[key]
                    )
                    node["inverted"] = first > second
                self.figure.apply_settings(state)
        return first, second

    def tick_params(self, axis="both", which="major", reset=False, **kwargs):
        return self._tick_params(axis=axis, which=which, reset=reset, **kwargs)

    def _tick_params(
        self, axis="both", which="major", reset=False, sides=None, **kwargs
    ):
        """Style ticks in points using Matplotlib names; reject unsupported options."""
        from .figure import _color, _LINES

        if axis not in ("x", "y", "both") or which not in ("major", "minor", "both"):
            raise ValueError("invalid axis or which")
        allowed = {
            "direction",
            "length",
            "width",
            "color",
            "pad",
            "labelsize",
            "labelcolor",
            "colors",
            "labelfontfamily",
            "bottom",
            "top",
            "left",
            "right",
            "labelbottom",
            "labeltop",
            "labelleft",
            "labelright",
            "grid_color",
            "grid_alpha",
            "grid_linewidth",
            "grid_linestyle",
        }
        if set(kwargs) - allowed:
            raise ValueError(
                "unsupported tick parameters: "
                + ", ".join(sorted(set(kwargs) - allowed))
            )
        fig = self.figure
        fig._require_cartesian()
        state = fig.get_settings()
        cfg = self._config(state)
        unit = fig.dpi / 72
        sides = sides or [
            s
            for s in ("bottom", "top", "left", "right")
            if axis == "both" or (axis == "x") == (s in ("bottom", "top"))
        ]
        for side in sides:
            key = {
                "bottom": "bottom_x",
                "top": "top_x",
                "left": "left_y",
                "right": "right_y",
            }[side]
            node = (
                self._overlay(state)["y_axis"]
                if self.overlay_id and side == "right"
                else cfg[key]
            )
            if self.overlay_id and axis == "y" and side == "left":
                continue
            label = node["label_style"]
            if reset:
                base = fig._default_config[key]
                for field in ("tick", "major_tick_length", "minor_tick_length"):
                    node[field] = copy.deepcopy(base[field])
                node["label_style"] = label = copy.deepcopy(base["label_style"])
            for name, value in kwargs.items():
                if name == "direction":
                    if value not in ("in", "out", "inout"):
                        raise ValueError("direction must be in, out or inout")
                    node["tick"] = {"in": "Inside", "out": "Outside", "inout": "Both"}[
                        value
                    ]
                elif name == "length":
                    length = _number(value, "length") * unit
                    if length < 0:
                        raise ValueError("length must be nonnegative")
                    if which in ("major", "both"):
                        node["major_tick_length"] = length
                    if which in ("minor", "both"):
                        node["minor_tick_length"] = length
                elif name in ("color", "colors"):
                    color = _color(value)
                    if node["line_visible"] and color != node["line_color"]:
                        raise NotImplementedError(
                            "renderer shares tick and spine colors; set spine color explicitly first"
                        )
                    node["line_color"] = color
                elif name == "labelcolor":
                    label["color"] = _color(value)
                elif name == "width":
                    width = _number(value, "width") * unit
                    if node["line_visible"] and not math.isclose(
                        width, node["line_width"], rel_tol=1e-6
                    ):
                        raise NotImplementedError(
                            "renderer shares tick and spine widths; set spine linewidth explicitly first"
                        )
                    node["line_width"] = width
                elif name == "labelsize":
                    label["font_size"] = (
                        _number(value, "labelsize", positive=True) * unit
                    )
                elif name == "labelfontfamily":
                    label["label_font"] = fig._check_font(value)
                elif name == "pad":
                    raise NotImplementedError(
                        "independent tick padding is not supported by this renderer"
                    )
                elif name == "label" + side:
                    label["label_visible"] = bool(value)
                    if value:
                        label["visible"] = True
            if side in kwargs:
                if not kwargs[side]:
                    node["tick"] = "None"
                elif node["tick"] == "None":
                    node["tick"] = fig._default_config[key]["tick"]
            if "colors" in kwargs:
                label["color"] = _color(kwargs["colors"])
        for dimension in ("x", "y"):
            if axis not in (dimension, "both"):
                continue
            for kind in ("major", "minor"):
                if which not in (kind, "both"):
                    continue
                grid = cfg["grid"]
                prefix = kind + "_" + dimension
                for name, field in [
                    ("grid_color", "color"),
                    ("grid_alpha", "alpha"),
                    ("grid_linewidth", "width"),
                    ("grid_linestyle", "style"),
                ]:
                    if name not in kwargs:
                        continue
                    value = kwargs[name]
                    if field == "color":
                        grid[prefix + "_color"] = _color(value)
                    elif field == "alpha":
                        grid[prefix + "_color"]["a"] = _number(value, "grid_alpha")
                    elif field == "width":
                        grid[prefix + "_width"] = (
                            _number(value, "grid_linewidth") * unit
                        )
                    else:
                        grid[prefix + "_style"] = _LINES.get(value, value)
        fig.apply_settings(state)


class SecondaryAxes:
    """Handle to an existing boundary; transformed secondary scales are guarded."""

    def __init__(self, axes, dimension, side):
        self.axes, self.dimension, self.side = axes, dimension, side

    @property
    def xaxis(self):
        if self.dimension != "x":
            raise AttributeError("this secondary axis is vertical")
        return Axis(self.axes, "x", self.side)

    @property
    def yaxis(self):
        if self.dimension != "y":
            raise AttributeError("this secondary axis is horizontal")
        return Axis(self.axes, "y", self.side)

    def tick_params(self, **kwargs):
        return self.axes._tick_params(axis=self.dimension, sides=[self.side], **kwargs)

    def set_xlabel(self, text, **kwargs):
        return self.xaxis.set_label_text(text, **kwargs)

    def set_ylabel(self, text, **kwargs):
        return self.yaxis.set_label_text(text, **kwargs)


class ColorbarText(Text):
    def _node(self, state):
        return self.axes._config(state)["colorbar"]["axis"]["title_option"]


class Colorbar:
    """The shared color scale of scalar-mapped artists on one panel."""

    def __init__(self, mappable, axes):
        self.mappable, self.axes = mappable, axes

    @property
    def ax(self):
        return ColorbarAxes(self.axes)

    def set_label(self, label, **kwargs):
        handle = ColorbarText(self.axes, "colorbar")
        handle.set(text=label, **kwargs)
        return handle

    def set_clim(self, *args, **kwargs):
        self.mappable.set_clim(*args, **kwargs)

    def remove(self):
        fig = self.axes.figure
        state = fig.get_settings()
        self.axes._config(state)["colorbar"]["visible"] = False
        fig.apply_settings(state)


class ColorbarAxis(Axis):
    def _nodes(self, state):
        return [self.axes._config(state)["colorbar"]["axis"]]

    @property
    def label(self):
        return ColorbarText(self.axes, "colorbar")

    def set_tick_params(self, which="major", reset=False, **kwargs):
        fig = self.axes.figure
        state = fig.get_settings()
        cfg = self.axes._config(state)
        axis = cfg["colorbar"]["axis"]
        side = cfg["colorbar"]["side"]
        # Reuse the same public tick argument translator on an isolated model
        # view; the transaction changes only the actual shared colorbar axis.
        key = "right_y" if side in ("Left", "Right") else "bottom_x"
        proxy = _StateFigure(state, fig._default_config, fig.dpi)
        ax = proxy._axes_for(self.axes.subplot_id)
        ax._config(proxy._state)[key] = copy.deepcopy(axis)
        ax._tick_params(
            axis="y" if key == "right_y" else "x",
            which=which,
            reset=reset,
            sides=["right" if key == "right_y" else "bottom"],
            **kwargs,
        )
        cfg["colorbar"]["axis"] = ax._config(proxy._state)[key]
        fig.apply_settings(state)


class ColorbarAxes:
    def __init__(self, axes):
        self.axes = axes

    @property
    def yaxis(self):
        return ColorbarAxis(self.axes, "y")

    @property
    def xaxis(self):
        return ColorbarAxis(self.axes, "x")

    def tick_params(self, axis="both", **kwargs):
        return self.yaxis.set_tick_params(**kwargs)


class FigureMethods:
    def clear_annotations(self):
        """Remove the document annotation layer; resident chart data is untouched."""
        from ._charts import family

        state = self.get_settings()
        owner = state[family(state)] if family(state) else state["config"]
        owner.pop("annotations", None)
        if "decorations" in owner:
            owner["decorations"]["selected"] = None
        self.apply_settings(state)

    def reset_style(self):
        """Reset Cartesian decorations without discarding data or panel ownership.

        This Figgy extension is intended for replaying an exported style recipe.
        Data mappings, ranges, layout rectangles and projection remain resident.
        """
        self._require_cartesian()
        state = self.get_settings()
        state.pop("background", None)
        for spec in state["series"]:
            body = next(iter(spec["render_type"].values()))
            for part in ("scatter", "err_style", "bar"):
                if part not in body:
                    continue
                # Remove optional per-element appearance, retaining column
                # bindings and numerical data-to-color/size mappings.
                for key in list(body[part]):
                    if key.endswith(("style_overrides", "style_table")) or key.endswith(
                        "style_index_column"
                    ):
                        body[part].pop(key)
            if "line" in body:
                for key in ("fill", "fill_color", "interpolation"):
                    body["line"].pop(key, None)
        for cfg in [state["config"]] + [
            p["config"] for p in state["config"].get("subplots", [])
        ]:
            cfg.pop("draw_style", None)
            cfg.pop("annotations", None)
            for key in (
                "chart_title",
                "grid",
                "legend",
                "bottom_x",
                "top_x",
                "left_y",
                "right_y",
            ):
                old = cfg[key]
                cfg[key] = copy.deepcopy(self._default_config[key])
                if key.endswith(("_x", "_y")):
                    for field in ("min", "max", "scale", "inverted", "major_spacing"):
                        cfg[key][field] = old[field]
            for overlay in cfg.get("overlays", []):
                old = overlay["y_axis"]
                overlay["y_axis"] = copy.deepcopy(self._default_config["right_y"])
                for field in ("min", "max", "scale", "inverted", "major_spacing"):
                    overlay["y_axis"][field] = old[field]
                if overlay.get("legend") is not None:
                    overlay["legend"] = copy.deepcopy(self._default_config["legend"])
            if cfg.get("colorbar") is not None:
                from ._native import default_colorbar_json

                old = cfg["colorbar"]
                cfg["colorbar"] = json.loads(default_colorbar_json())
                cfg["colorbar"]["colormap"] = old["colormap"]
                for key in ("min", "max", "major_spacing", "scale"):
                    cfg["colorbar"]["axis"][key] = old["axis"][key]
        self.apply_settings(state)

    def artist(self, gid):
        """Look up an existing artist by its stable public ID."""
        if not any(s["series_id"] == gid for s in self.get_settings()["series"]):
            raise ValueError(f"artist {gid!r} no longer exists")
        return self._artist_for(gid)

    def colorbar(self, mappable, ax=None, *, label=None, **kwargs):
        if kwargs:
            raise NotImplementedError(
                "colorbar layout options are not yet part of the Matplotlib subset"
            )
        if mappable.figure is not self:
            raise ValueError("mappable belongs to another Figure")
        mappable._colorbar()
        owners = [
            a
            for a in self.axes
            if any(
                s["series_id"] == mappable.id
                for s in a._owned_series(self.get_settings())
            )
        ]
        owner = owners[0]
        if ax is not None and (
            ax.figure is not self or ax.subplot_id != owner.subplot_id
        ):
            raise ValueError("colorbar must belong to the mappable panel")
        with self.batch_update():
            state = self.get_settings()
            owner._config(state)["colorbar"]["visible"] = True
            self.apply_settings(state)
            bar = Colorbar(mappable, owner)
            if label is not None:
                bar.set_label(label)
        return bar

    @contextmanager
    def batch_update(self):
        """Commit existing-artist style/layout edits once, or roll them all back.

        Create plot data outside this block. Nested blocks are supported; failed
        inner blocks restore their entry state. Resident columns are untouched.
        """
        with self._lock:
            previous = self._style_batch
            revision = self.revision
            self._style_batch = (
                self.get_settings() if previous is None else copy.deepcopy(previous)
            )
            try:
                yield self
            except BaseException:
                self._style_batch = previous
                raise
            else:
                candidate = self._style_batch
                self._style_batch = previous
                if previous is None:
                    self.apply_settings(candidate, expected_revision=revision)
                else:
                    self._style_batch = candidate

    def get_size_inches(self):
        return np.array(canvas_size(self.get_settings())) / self.dpi

    def get_figwidth(self):
        return self.get_size_inches()[0]

    def get_figheight(self):
        return self.get_size_inches()[1]

    def get_dpi(self):
        return self.dpi

    def set_size_inches(self, w, h=None, forward=True):
        if h is None:
            w, h = w
        w = _number(w, "width", positive=True)
        h = _number(h, "height", positive=True)
        from ._document import place_grid

        state = self.get_settings()
        old_w, old_h = canvas_size(state)
        new_w, new_h = round(w * self.dpi), round(h * self.dpi)
        if new_w < 1 or new_h < 1:
            raise ValueError("figure size must be at least one logical pixel")
        layout = state["identity"].get("layout")
        if layout:
            layout["size"] = [new_w, new_h]
            place_grid(state)
        else:
            for cfg in [state["config"]] + [
                p["config"] for p in state["config"].get("subplots", [])
            ]:
                area = cfg["chart_area"]
                for key, scale in [
                    ("x", new_w / old_w),
                    ("width", new_w / old_w),
                    ("y", new_h / old_h),
                    ("height", new_h / old_h),
                ]:
                    area[key] = round(area[key] * scale)
        self.apply_settings(state)


def _StateFigure(state, defaults, dpi):
    """CPU-only view used by translators, never a second plotting backend.

    Calls the actual public setters against copied state. It cannot read/upload
    columns, draw, or acquire the native Figure lock (Copy Python holds it).
    """
    from .figure import Figure
    import threading

    class StateFigure(Figure):
        def __init__(self):
            self._state = copy.deepcopy(state)
            self._default_config = copy.deepcopy(defaults)
            self.dpi = dpi
            self.backend = "webgpu"
            self._style_batch = None
            self._lock = threading.RLock()
            self._style_defaults = None
            self._axes_handles = {}
            self._artist_handles = {}
            self._native = object()
            self.axes = [
                self._axes_for(p["id"], overlay)
                for p in state["identity"]["panels"]
                for overlay in [None, *p["overlays"]]
            ]
            from ._document import Subplots

            self.subplots = Subplots(self)

        @property
        def revision(self):
            return 0

        def get_settings(self):
            return json.loads(
                json.dumps(
                    self._style_batch if self._style_batch is not None else self._state,
                    allow_nan=False,
                )
            )

        def apply_settings(self, settings, **kwargs):
            resolved = json.loads(json.dumps(settings, allow_nan=False))
            if self._style_batch is not None:
                self._style_batch = resolved
            else:
                self._state = resolved
            return self

        def _changed(self):
            pass

        def close(self):
            self._native = None

    return StateFigure()
