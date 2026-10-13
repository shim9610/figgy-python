from __future__ import annotations

import copy
import json
import keyword
import math
from pathlib import Path
import pprint
import re
import threading
import weakref

import numpy as np

from ._native import NativeFigure

_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
_NAMED = {"blue": "#0000ff", "red": "#ff0000", "green": "#008000", "black": "#000000", "white": "#ffffff", "orange": "#ffa500", "purple": "#800080", "gray": "#808080", "grey": "#808080", "b": "#0000ff", "r": "#ff0000", "g": "#008000", "k": "#000000", "w": "#ffffff"}
_MARKERS = {"o": "CircleFilled", "s": "SquareFilled", "^": "TriangleFilled", "v": "TriangleDownFilled", "D": "DiamondFilled", "+": "Plus", "x": "Cross", "*": "StarFilled"}
_LINES = {"-": "Solid", "--": "Dash", ":": "Dot", "-.": "DashDot"}


def _color(value):
    if isinstance(value, str):
        value = _NAMED.get(value.lower(), value)
        if re.fullmatch(r"#[0-9a-fA-F]{3}", value):
            value = "#" + "".join(c * 2 for c in value[1:])
        if not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", value):
            raise ValueError("color must be a named color, #RGB/#RRGGBB/#RRGGBBAA, or an RGB(A) tuple")
        values = [int(value[i:i+2], 16) / 255 for i in range(1, len(value), 2)]
    else:
        values = list(value)
    if len(values) == 3:
        values.append(1.0)
    if len(values) != 4 or any(not math.isfinite(float(v)) or not 0 <= v <= 1 for v in values):
        raise ValueError("RGB(A) channels must be finite values in [0, 1]")
    return dict(zip("rgba", map(float, values)))


def _array(value):
    value = np.asarray(value)
    if value.ndim != 1 or not value.size or value.dtype.kind not in "fiu":
        raise ValueError("data must be a non-empty one-dimensional numeric array")
    dtype = np.float32 if value.dtype == np.dtype(np.float32) else np.float64
    return np.ascontiguousarray(value, dtype=dtype)


def _segments(text):
    return [{"text": c, "bold": False, "italic": False, "underline": False,
             "superscript": False, "subscript": False, "greek": False} for c in str(text)]


def _text(value):
    return "".join(s["text"] for s in value["segments"])


class Artist:
    """A stable series handle. Data lives in the Rust renderer's column pool."""

    def __init__(self, fig, series_id):
        self.figure = fig
        self.id = series_id

    def set_color(self, value):
        return self.figure.update(self.id, color=value)

    def set_linewidth(self, value):
        return self.figure.update(self.id, linewidth=value)

    def set_label(self, value):
        return self.figure.update(self.id, label=value)

    def set(self, **kwargs):
        return self.figure.update(self.id, **kwargs)


class Figure:
    """One editable chart document, with a persistent native renderer.

    ``figsize`` is inches, ``dpi`` defines the logical canvas size. Arrays are
    uploaded once; subsequent renders and settings changes reuse native columns.
    Upload borrows contiguous float32/float64 buffers while holding the GIL.
    Rendering, initialization, GPU fitting and picking release the GIL.
    """

    def __init__(self, figsize=(8, 5), dpi=120, *, pool_bytes=8 * 1024**2):
        if not math.isfinite(float(dpi)) or dpi <= 0:
            raise ValueError("dpi must be positive and finite")
        figsize = tuple(map(float, figsize))
        if len(figsize) != 2 or any(not math.isfinite(v) or v <= 0 for v in figsize):
            raise ValueError("figsize must contain two positive finite inch values")
        width, height = (round(v * float(dpi)) for v in figsize)
        self.dpi = float(dpi)
        self._lock = threading.RLock()
        self._native = NativeFigure(width, height, pool_bytes)
        self._default_config = copy.deepcopy(self.get_settings()["config"])
        self._widgets = weakref.WeakSet()
        self._windows = []
        self._selection = None
        self._next_series = 0
        self.axes = [Axes(self)]

    def _require_open(self):
        if self._native is None:
            raise RuntimeError("Figure is closed")

    @property
    def revision(self):
        with self._lock:
            self._require_open()
            return self._native.revision

    @property
    def info(self):
        with self._lock:
            self._require_open()
            return json.loads(self._native.info_json())

    def get_settings(self):
        with self._lock:
            self._require_open()
            return json.loads(self._native.settings_json())

    def apply_settings(self, settings, *, expected_revision=None, reset=False):
        """Replace accepted settings for existing series; source arrays are not copied."""
        with self._lock:
            self._require_open()
            if expected_revision is not None and expected_revision != self.revision:
                raise ValueError("stale edit: the Figure changed; refresh and retry")
            if reset:
                settings = copy.deepcopy(settings)
                settings["config"] = _merge(copy.deepcopy(self._default_config), settings["config"])
            self._native.apply_settings(json.dumps(settings, allow_nan=False))
        self._changed()
        return self

    def _changed(self):
        for widget in list(self._widgets):
            widget.refresh()
        for window in list(self._windows):
            window.refresh()

    def update(self, target, **properties):
        """Edit a stable series/decorative target using familiar property names."""
        with self._lock:
            self._require_open()
            state = self.get_settings()
            cfg = state["config"]
            series = next((s for s in state["series"] if s["series_id"] == target), None)
            if series is not None:
                style = next(iter(series["render_type"].values()))
                for key, value in properties.items():
                    if key == "color":
                        matched = False
                        for kind, field in [("line", "line_color"), ("scatter", "point_color"), ("bar", "bar_color")]:
                            if kind in style:
                                style[kind][field] = _color(value)
                                matched = True
                        if not matched:
                            raise ValueError("use cmap/vmin/vmax for field colors")
                    elif key == "linewidth" and "line" in style:
                        style["line"]["line_width"] = float(value) * self.dpi / 72
                    elif key == "markersize" and "scatter" in style:
                        style["scatter"]["point_size"] = float(value) * self.dpi / 144
                    elif key == "linestyle" and "line" in style:
                        style["line"]["line_style"] = _LINES.get(value, value)
                    elif key == "label":
                        label = copy.deepcopy(cfg["legend"]["content"])
                        label["segments"] = _segments(value)
                        series["label"] = label
                    elif key in ("cmap", "vmin", "vmax") and "matrix" in style:
                        bar = cfg["colorbar"]
                        if key == "cmap":
                            bar["colormap"] = _colormap(value)
                        else:
                            bar["axis"]["min" if key == "vmin" else "max"] = float(value)
                    else:
                        raise ValueError(f"unsupported series property: {key}")
            else:
                if target == "chart_title":
                    node, rich = cfg["chart_title"], cfg["chart_title"]["text"]
                elif target == "legend":
                    node, rich = cfg["legend"], cfg["legend"]["content"]
                elif target.startswith("axis_title_"):
                    axis = _axis_key(target.removeprefix("axis_title_"))
                    node, rich = cfg[axis]["title_option"], cfg[axis]["title_option"]["text"]
                elif target.startswith("tick_labels_"):
                    node = cfg[_axis_key(target.removeprefix("tick_labels_"))]["label_style"]
                    rich = None
                elif target.startswith("axis_"):
                    node = cfg[_axis_key(target.removeprefix("axis_"))]
                    rich = None
                else:
                    raise ValueError(f"unknown editable target: {target}")
                for key, value in properties.items():
                    if key == "text" and rich is not None:
                        rich["segments"] = _segments(value)
                    elif key in ("color", "fontsize", "font"):
                        field = {"color": "color", "fontsize": "font_size", "font": "font"}[key]
                        if key == "fontsize":
                            value = float(value) * self.dpi / 72
                            if not math.isfinite(value) or value <= 0:
                                raise ValueError("fontsize must be positive and finite")
                        if rich is not None:
                            rich[field] = _color(value) if key == "color" else value
                        elif key == "color" and "line_color" in node:
                            node["line_color"] = _color(value)
                        elif field in node:
                            node[field] = _color(value) if key == "color" else value
                        else:
                            raise ValueError(f"unsupported property for {target}: {key}")
                    elif key == "offset" and "offset_x" in node:
                        node["offset_x"], node["offset_y"] = map(float, value)
                    elif key in node and key in ("visible", "line_width", "line_visible", "major_spacing", "min", "max"):
                        node[key] = value
                    else:
                        raise ValueError(f"unsupported property for {target}: {key}")
            # Reject bad sizes before they reach GPU geometry creation.
            for spec in state["series"]:
                for style in spec["render_type"].values():
                    for kind, field in [("line", "line_width"), ("scatter", "point_size")]:
                        if kind in style and (not math.isfinite(style[kind][field]) or style[kind][field] <= 0):
                            raise ValueError(f"{field} must be positive and finite")
            self._native.apply_settings(json.dumps(state, allow_nan=False))
        self._changed()
        return self

    def render_rgba(self, *, scale=1.0):
        """Synchronously render and read back a (height, width, 4) uint8 array."""
        with self._lock:
            self._require_open()
            w, h, data = self._native.render_rgba(float(scale))
            return np.frombuffer(data, dtype=np.uint8).reshape(h, w, 4)

    def to_png(self, *, scale=1.0):
        with self._lock:
            self._require_open()
            return self._native.render_png(float(scale))

    def savefig(self, filename, *, dpi=None, scale=None):
        """Write PNG directly, without opening a window or importing a GUI."""
        if dpi is not None and scale is not None:
            raise ValueError("choose dpi or scale, not both")
        data = self.to_png(scale=(float(dpi) / self.dpi if dpi is not None else (1.0 if scale is None else scale)))
        if hasattr(filename, "write"):
            filename.write(data)
        else:
            path = Path(filename)
            if path.suffix.lower() != ".png":
                raise ValueError("savefig currently supports .png")
            path.write_bytes(data)

    def to_code(self, variable="fig"):
        """Executable settings snapshot for a Figure created with the same series IDs."""
        if not variable.isidentifier() or keyword.iskeyword(variable):
            raise ValueError("variable must be a Python identifier")
        settings = self.get_settings()
        settings["config"] = _diff(self._default_config, settings["config"])
        # Canvas dimensions remain explicit so replay does not depend on figsize.
        settings["config"]["chart_area"] = self.get_settings()["config"]["chart_area"]
        return f"from figgy import text_segments\n\n{variable}.apply_settings(\n{pprint.pformat(_code_tree(settings), width=100, sort_dicts=False)},\nreset=True,\n)\n"

    def select(self, x, y, *, edit_area=False):
        with self._lock:
            self._require_open()
            hit = self._native.hit_test(float(x), float(y))
            if hit in (None, "data_area") and not edit_area:
                picked = json.loads(self._native.pick_json(float(x), float(y)))
                hit = picked["target"] if picked else None
            else:
                self._native.clear_data_selection()
            self._selection = hit
            return hit

    def select_object(self, target):
        with self._lock:
            self._require_open()
            if not any(s["series_id"] == target for s in self.get_settings()["series"]):
                self._native.bounds_json(target)  # Validate through renderer element IDs.
            self._native.clear_data_selection()
            self._selection = target

    def selection_bounds(self):
        with self._lock:
            self._require_open()
            if self._selection is None or any(s["series_id"] == self._selection for s in self.get_settings()["series"]):
                return None
            return json.loads(self._native.bounds_json(self._selection))

    def drag(self, target, dx, dy, *, handle=None):
        with self._lock:
            self._require_open()
            moved = self._native.drag(target, float(dx), float(dy), handle)
        if moved:
            self._changed()
        return moved

    def fit(self, padding=0.05):
        with self._lock:
            self._require_open()
            self._native.fit(float(padding))
        self._changed()
        return self

    def widget(self):
        from .widget import FigureWidget
        widget = FigureWidget(self)
        self._widgets.add(widget)
        return widget

    def _repr_mimebundle_(self, **kwargs):
        # Keep a live widget referenced; Jupyter displays the model once per output.
        return self.widget()._repr_mimebundle_(**kwargs)

    def show(self, *, block=True):
        from .desktop import show
        return show(self, block=block)

    def close(self):
        with self._lock:
            for widget in list(self._widgets):
                widget.close()
            for window in list(self._windows):
                window.close()
            self._windows.clear()
            self._native = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _axis_key(side):
    try:
        return {"bottom": "bottom_x", "top": "top_x", "left": "left_y", "right": "right_y"}[side]
    except KeyError:
        raise ValueError(f"unknown axis side: {side}") from None


def _merge(base, patch):
    for key, value in patch.items():
        base[key] = _merge(base.get(key, {}), value) if isinstance(value, dict) else copy.deepcopy(value)
    return base


def _diff(base, value):
    result = {}
    for key, current in value.items():
        if key not in base or base[key] != current:
            if isinstance(current, dict) and isinstance(base.get(key), dict):
                result[key] = _diff(base[key], current)
            else:
                result[key] = copy.deepcopy(current)
    return result


class _CodeExpression:
    def __init__(self, expression):
        self.expression = expression

    def __repr__(self):
        return self.expression


def _code_tree(value):
    if isinstance(value, dict):
        result = {}
        for key, current in value.items():
            if key == "segments" and isinstance(current, list):
                text = "".join(s["text"] for s in current)
                if current == _segments(text):
                    result[key] = _CodeExpression(f"text_segments({text!r})")
                    continue
            result[key] = _code_tree(current)
        return result
    if isinstance(value, list):
        return [_code_tree(v) for v in value]
    return value


def text_segments(text):
    """Build plain renderer RichSegment values, including safe Unicode text."""
    return _segments(text)


def _colormap(value):
    try:
        return {"viridis": "Viridis", "magma": "Magma", "turbo": "Turbo", "gray": "GrayScale", "grey": "GrayScale", "rdbu": "RdBu"}[value.lower()]
    except (KeyError, AttributeError):
        raise ValueError("cmap must be viridis, magma, turbo, gray or RdBu") from None


class Axes:
    def __init__(self, figure):
        self.figure = figure
        self._manual_x = False
        self._manual_y = False

    def _add(self, x, y, render_type, label=None, id=None, extra_columns=()):
        fig = self.figure
        with fig._lock:
            fig._require_open()
            sid = id if id is not None else f"series_{fig._next_series}"
            if not isinstance(sid, str) or not sid:
                raise ValueError("series ID must be a non-empty string")
            if sid in ("chart_title", "legend", "data_area", "colorbar", "colorbar_axis", "colorbar_tick_labels", "colorbar_title") or sid.startswith(("axis_", "tick_labels_")):
                raise ValueError("series ID conflicts with a renderer decoration ID")
            if any(s["series_id"] == sid for s in fig.get_settings()["series"]):
                raise ValueError(f"duplicate series ID: {sid}")
            names = (f"{sid}/x", f"{sid}/y")
            uploaded = []
            try:
                for name, array in [(names[0], x), (names[1], y), *extra_columns]:
                    fig._native.upload_column(name, array)
                    uploaded.append(name)
                spec = {"series_id": sid, "label": None, "x_column": names[0], "y_column": names[1], "render_type": render_type}
                if label is not None:
                    rich = copy.deepcopy(fig.get_settings()["config"]["legend"]["content"])
                    rich["segments"] = _segments(label)
                    spec["label"] = rich
                fig._native.add_series(json.dumps(spec, allow_nan=False))
            except Exception:
                for name in reversed(uploaded):
                    fig._native.remove_column(name)
                raise
            fig._next_series += 1
            old = fig.get_settings()
            fig._native.fit(0.05)
            if self._manual_x or self._manual_y:
                fitted = fig.get_settings()
                for key in (["bottom_x", "top_x"] if self._manual_x else []) + (["left_y", "right_y"] if self._manual_y else []):
                    fitted["config"][key] = old["config"][key]
                fig._native.apply_settings(json.dumps(fitted, allow_nan=False))
        fig._changed()
        return Artist(fig, sid)

    def plot(self, x, y=None, fmt=None, *, color=None, linewidth=1.5, linestyle="-", marker=None, markersize=4, label=None, id=None):
        marker_only_format = False
        if isinstance(y, str):
            if fmt is not None:
                raise ValueError("format string was provided twice")
            fmt, y = y, None
        if fmt is not None:
            remaining = str(fmt)
            has_line = False
            for candidate in ("--", "-.", ":", "-"):
                if candidate in remaining:
                    linestyle = candidate
                    has_line = True
                    remaining = remaining.replace(candidate, "", 1)
                    break
            for c in remaining:
                if c in "bgrkw" and color is None:
                    color = c
                elif c in _MARKERS and marker is None:
                    marker = c
                else:
                    raise ValueError(f"unsupported plot format: {fmt}")
            marker_only_format = marker is not None and not has_line and linestyle == "-"
        if y is None:
            y = _array(x)
            x = np.arange(y.size, dtype=np.float64)
        else:
            x, y = _array(x), _array(y)
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        color = _color(color if color is not None else _COLORS[self.figure._next_series % len(_COLORS)])
        if not math.isfinite(float(linewidth)) or linewidth <= 0 or not math.isfinite(float(markersize)) or markersize <= 0:
            raise ValueError("line and marker sizes must be positive and finite")
        # Python API uses points; renderer uses pixel widths and marker radii.
        line = {"line_style": _LINES.get(linestyle, linestyle), "line_color": color, "line_width": float(linewidth) * self.figure.dpi / 72}
        style = {"Line": {"line": line}}
        if marker is not None:
            scatter = {"point_color": color, "point_size": float(markersize) * self.figure.dpi / 144, "point_shape": _MARKERS.get(marker, marker)}
            style = {"Scatter": {"scatter": scatter}} if marker_only_format else {"ScatterLine": {"line": line, "scatter": scatter}}
        return [self._add(x, y, style, label, id)]

    def scatter(self, x, y, *, s=16, color=None, marker="o", label=None, id=None):
        x, y = _array(x), _array(y)
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        if not math.isfinite(float(s)) or s <= 0:
            raise ValueError("s must be positive and finite")
        style = {"Scatter": {"scatter": {"point_color": _color(color if color is not None else _COLORS[self.figure._next_series % len(_COLORS)]), "point_shape": _MARKERS.get(marker, marker), "point_size": math.sqrt(s) * self.figure.dpi / 144}}}
        return self._add(x, y, style, label, id)

    def imshow(self, z, *, extent=None, origin="upper", cmap="viridis", vmin=None, vmax=None, interpolation="nearest", id=None):
        z = np.asarray(z)
        if z.ndim != 2 or min(z.shape) < 2 or z.dtype.kind not in "fiu":
            raise ValueError("imshow expects a numeric matrix with at least 2 rows and columns")
        if origin not in ("upper", "lower") or interpolation not in ("nearest", "bilinear"):
            raise ValueError("origin must be upper/lower and interpolation nearest/bilinear")
        h, w = z.shape
        ext = (-0.5, w - 0.5, -0.5, h - 0.5) if extent is None else tuple(map(float, extent))
        if len(ext) != 4 or not all(math.isfinite(v) for v in ext) or ext[0] >= ext[1] or ext[2] >= ext[3]:
            raise ValueError("extent requires increasing finite x/y bounds")
        x = np.linspace(ext[0], ext[1], w + 1)
        y = np.linspace(ext[2], ext[3], h + 1)
        sid = id if id is not None else f"series_{self.figure._next_series}"
        columns = [(f"{sid}/z/{i}", _array(row)) for i, row in enumerate(z)]
        style = {"Heatmap": {"matrix": {"columns": [n for n, _ in columns], "orientation": "ColumnsAreY", "grid_layout": "Edges"},
                              "fill": {"mode": "Continuous", "shading": "Flat" if interpolation == "nearest" else "Interpolated", "opacity": 1.0}}}
        finite = z[np.isfinite(z)]
        if not finite.size:
            raise ValueError("matrix has no finite values")
        low = float(finite.min()) if vmin is None else float(vmin)
        high = float(finite.max()) if vmax is None else float(vmax)
        if low == high:
            high = low + 1
        if not math.isfinite(low) or not math.isfinite(high) or low >= high:
            raise ValueError("vmin and vmax must be finite and increasing")
        # Renderer defaults own colorbar layout; obtain them from a native helper.
        from ._native import default_colorbar_json
        state = self.figure.get_settings()
        bar = json.loads(default_colorbar_json())
        bar["colormap"] = _colormap(cmap)
        bar["axis"]["min"], bar["axis"]["max"] = low, high
        bar["axis"]["major_spacing"] = (high - low) / 5
        state["config"]["colorbar"] = bar
        self.figure.apply_settings(state)
        artist = self._add(x, y, style, id=id, extra_columns=columns)
        state = self.figure.get_settings()
        for key in ("left_y", "right_y"):
            state["config"][key]["inverted"] = origin == "upper"
        self.figure.apply_settings(state)
        self.set_xlim(ext[0], ext[1]); self.set_ylim(ext[2], ext[3])
        return artist

    def set_title(self, text, **kwargs):
        return self.figure.update("chart_title", text=text, **kwargs)

    def set_xlabel(self, text, **kwargs):
        return self.figure.update("axis_title_bottom", text=text, **kwargs)

    def set_ylabel(self, text, **kwargs):
        return self.figure.update("axis_title_left", text=text, **kwargs)

    def _set_scale(self, axis, scale):
        scales = {"linear": "Linear", "log": "Logarithmic"}
        if scale not in scales:
            raise ValueError("scale must be 'linear' or 'log'")
        with self.figure._lock:
            state = self.figure.get_settings()
            keys = ("bottom_x", "top_x") if axis == "x" else ("left_y", "right_y")
            if scale == "log" and any(state["config"][key]["min"] <= 0 for key in keys):
                raise ValueError(f"log scale requires positive bounds; call set_{axis}lim first")
            for key in keys:
                node = state["config"][key]
                node["scale"] = scales[scale]
                node["major_spacing"] = 1.0 if scale == "log" else (node["max"] - node["min"]) / 5
            self.figure.apply_settings(state)

    def set_xscale(self, scale):
        """Choose linear/log scaling; logarithmic bounds must already be positive."""
        return self._set_scale("x", scale)

    def set_yscale(self, scale):
        """Choose linear/log scaling; logarithmic bounds must already be positive."""
        return self._set_scale("y", scale)

    def get_xscale(self):
        return "log" if self.figure.get_settings()["config"]["bottom_x"]["scale"] == "Logarithmic" else "linear"

    def get_yscale(self):
        return "log" if self.figure.get_settings()["config"]["left_y"]["scale"] == "Logarithmic" else "linear"

    def set_xlim(self, left, right):
        with self.figure._lock:
            self.figure._require_open()
            self.figure._native.set_range("x", float(left), float(right))
            self._manual_x = True
        self.figure._changed()
        return (left, right)

    def set_ylim(self, bottom, top):
        with self.figure._lock:
            self.figure._require_open()
            self.figure._native.set_range("y", float(bottom), float(top))
            self._manual_y = True
        self.figure._changed()
        return (bottom, top)

    def grid(self, visible=True):
        state = self.figure.get_settings()
        state["config"]["grid"]["show_major_x"] = bool(visible)
        state["config"]["grid"]["show_major_y"] = bool(visible)
        self.figure.apply_settings(state)

    def legend(self, visible=True):
        from ._native import rebuild_legend_json
        state = self.figure.get_settings()
        state["config"]["legend"]["content"] = json.loads(rebuild_legend_json(json.dumps(state["series"]), json.dumps(state["config"]["legend"]["content"])))
        state["config"]["legend"]["visible"] = bool(visible)
        self.figure.apply_settings(state)


def figure(*args, **kwargs):
    return Figure(*args, **kwargs)


def subplots(nrows=1, ncols=1, **kwargs):
    """Return a Figure and Axes. The initial release supports one panel."""
    if (nrows, ncols) != (1, 1):
        raise NotImplementedError("multiple panels are not supported in 0.1")
    fig = Figure(**kwargs)
    return fig, fig.axes[0]
