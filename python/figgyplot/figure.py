from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import re
import threading
import warnings
import weakref

import numpy as np

from ._native import NativeFigure, __version__, fitted_chart_title_margin, font_family_available, segments_plain_text, text_segments_json

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


class RenderWarning(UserWarning):
    """A tick setting the renderer could not draw as written and replaced."""


_ALIGN = {"left": "Left", "center": "Center", "right": "Right"}


def _segments(text):
    # The renderer's own plain-text segments, including its mapping of
    # Unicode superscript/subscript characters (e.g. "10⁻³") to styled ones.
    return json.loads(text_segments_json(str(text)))


def _segments_text(segments):
    """The text whose segments are exactly ``segments``, or None."""
    return segments_plain_text(json.dumps(segments))


def _timeout(value):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("timeout must be positive and finite (seconds)") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be positive and finite (seconds)")
    return value


def _text(value):
    text = _segments_text(value["segments"])
    return "".join(s["text"] for s in value["segments"]) if text is None else text


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


class RadialArtist:
    """Handle for a bounded pie/donut document; slice indices stay stable."""

    def __init__(self, figure):
        self.figure = figure

    def set_style(self, **properties):
        self.figure.set_radial_style(**properties)
        return self

    def set_slice(self, index, **properties):
        if "color" in properties:
            properties["color"] = _color(properties["color"])
        if "material" in properties:
            properties.setdefault("style", {})["material"] = _material(properties.pop("material"))
        self.figure.configure_radial(slices={index: properties})
        return self

    def set_values(self, values):
        values = _array(values)
        with self.figure._lock:
            state = self.figure.get_settings()
            slices = state["radial"]["slices"]
            if values.size != len(slices):
                raise ValueError("set_values requires the same number of slices")
            for item, value in zip(slices, values):
                item["value"] = float(value)
            interaction = state["radial"]["interaction"]
            for key in ("selected", "hovered"):
                target = interaction[key]
                if target is not None and target["group"] == 0 and slices[target["index"]]["value"] == 0:
                    interaction[key] = None
                    if key == "hovered":
                        interaction["hover_progress"] = 0.0
            self.figure.apply_settings(state)
        return self


class Figure:
    """One editable chart document, with a persistent native renderer.

    ``figsize`` is inches, ``dpi`` defines the logical canvas size. Arrays are
    uploaded once; subsequent renders and settings changes reuse native columns.
    Upload borrows contiguous float32/float64 buffers while holding the GIL.
    Rendering, initialization, GPU fitting and picking release the GIL.
    """

    def __init__(self, figsize=(8, 5), dpi=120, *, pool_bytes=8 * 1024**2, backend="auto", retain_notebook_data=False):
        if not math.isfinite(float(dpi)) or dpi <= 0:
            raise ValueError("dpi must be positive and finite")
        figsize = tuple(map(float, figsize))
        if len(figsize) != 2 or any(not math.isfinite(v) or v <= 0 for v in figsize):
            raise ValueError("figsize must contain two positive finite inch values")
        width, height = (round(v * float(dpi)) for v in figsize)
        self.dpi = float(dpi)
        self._lock = threading.RLock()
        if backend == "auto":
            try:
                from IPython import get_ipython
                shell = get_ipython()
                backend = "webgpu" if shell is not None and getattr(shell, "kernel", None) is not None else "native"
            except ImportError:
                backend = "native"
        if backend not in ("native", "webgpu"):
            raise ValueError("backend must be auto/native/webgpu")
        self.backend = backend
        if backend == "webgpu":
            from .notebook import NotebookData
            self._native = NotebookData(width, height, pool_bytes, retain_notebook_data)
        else:
            self._native = NativeFigure(width, height, pool_bytes, self.dpi)
        self._default_config = copy.deepcopy(self.get_settings()["config"])
        self._widgets = weakref.WeakSet()
        self._windows = []
        self._selection = None
        self._next_series = 0
        self.axes = [Axes(self)]

    def _require_open(self):
        if self._native is None:
            raise RuntimeError("Figure is closed")

    def _require_cartesian(self):
        if self.get_settings().get("radial") is not None:
            raise ValueError("pie/donut charts have no Cartesian axes; use radial properties or slice selection")

    @property
    def revision(self):
        with self._lock:
            self._require_open()
            return self._native.revision

    @property
    def info(self):
        with self._lock:
            self._require_open()
            info = json.loads(self._native.info_json())
            if self.backend == "webgpu":
                info["transfer_snapshot_bytes"] = sum(len(v[1]) for v in self._native.columns.values())
                info["browser"] = [dict(w.browser_info, status=w.status) for w in self._widgets]
            return info

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

    def _check_font(self, value):
        """Reject a font family the native text stack would silently replace."""
        if not isinstance(value, str):
            raise ValueError("font must be a font family name")
        # The browser backend resolves fonts in the page, where only the
        # bundled face is available; there is nothing installed to check.
        if self.backend == "native" and not font_family_available(value):
            raise ValueError(
                f"unknown font family {value!r}: it is neither installed nor the bundled "
                "'Liberation Sans' (use '' for the default font)"
            )
        return value

    def _report_render_warnings(self):
        for message in self._native.take_render_warnings():
            warnings.warn(message, RenderWarning, stacklevel=3)

    def update(self, target, **properties):
        """Edit a stable series/decorative target using familiar property names."""
        if not isinstance(target, str) or not target:
            raise ValueError("editable target must be a non-empty string")
        radial_document = self.get_settings().get("radial") is not None
        if radial_document and target != "chart_title":
            raise ValueError("use radial properties or set_slice() to edit a pie/donut")
        if radial_document and target == "chart_title":
            radial = {}
            for key, value in properties.items():
                if key == "text":
                    radial["title"] = str(value)
                elif key == "fontsize":
                    radial["font_size"] = float(value) * self.dpi / 72
                elif key == "font":
                    radial["font_family"] = self._check_font(value)
                else:
                    raise ValueError(f"unsupported radial title property: {key}")
            return self.configure_radial(**radial)
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
                        for kind, field in [("line", "line_color"), ("scatter", "point_color"), ("bar", "fill_color")]:
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
                    axis = _axis_key(target[len("axis_title_"): ])
                    node, rich = cfg[axis]["title_option"], cfg[axis]["title_option"]["text"]
                elif target.startswith("tick_labels_"):
                    node = cfg[_axis_key(target[len("tick_labels_"): ])]["label_style"]
                    rich = None
                elif target.startswith("axis_"):
                    node = cfg[_axis_key(target[len("axis_"): ])]
                    rich = None
                else:
                    raise ValueError(f"unknown editable target: {target}")
                for key, value in properties.items():
                    if key == "text" and rich is not None:
                        rich["segments"] = _segments(value)
                    elif key == "align" and rich is not None:
                        if not isinstance(value, str) or value.lower() not in _ALIGN:
                            raise ValueError("align must be 'left', 'center' or 'right'")
                        rich["align"] = _ALIGN[value.lower()]
                    elif key in ("color", "fontsize", "font"):
                        field = {"color": "color", "fontsize": "font_size", "font": "font"}[key]
                        if key == "font":
                            value = self._check_font(value)
                            if rich is None and "label_font" in node:
                                field = "label_font"
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
                        if key in ("min", "max") and "range_locked" in node:
                            # An explicit range edit: later fits keep it.
                            node["range_locked"] = True
                    else:
                        raise ValueError(f"unsupported property for {target}: {key}")
                # Like the renderer's title helpers, derive the title band from
                # the new text: a title taller than the band (multi-line or
                # enlarged) grows it instead of being clipped at the top.
                if target == "chart_title" and {"text", "fontsize", "font"} & properties.keys():
                    cfg["chart_title"]["top_margin"] = fitted_chart_title_margin(json.dumps(cfg, allow_nan=False))
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
            if self.backend != "native":
                raise RuntimeError("render_rgba requires a native GPU; use browser export via await fig.to_png_async()")
            w, h, data = self._native.render_rgba(float(scale))
            self._report_render_warnings()
            return np.frombuffer(data, dtype=np.uint8).reshape(h, w, 4)

    def to_png(self, *, scale=1.0):
        with self._lock:
            self._require_open()
            if self.backend != "native":
                raise RuntimeError("Browser export is asynchronous: await fig.to_png_async() or await fig.savefig_async(path)")
            data = self._native.render_png(float(scale))
            self._report_render_warnings()
            return data

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

    def configure(self, *, config=None, series=None, reset=False):
        """Apply advanced layout/style patches to existing plotted data.

        ``series`` maps stable series IDs to style patches. Source columns and
        series IDs remain owned by the existing Figure. ``reset`` resets layout
        to this Figure's defaults before applying the optional patches.
        """
        with self._lock:
            state = self.get_settings()
            if reset:
                state["config"] = copy.deepcopy(self._default_config)
                state.pop("background", None)
            if config is not None:
                if "draw_style" in config:
                    state["config"].pop("draw_style", None)
                state["config"] = _merge(state["config"], config)
            if series is not None:
                existing = {s["series_id"]: s for s in state["series"]}
                for sid, patch in series.items():
                    if sid not in existing:
                        raise ValueError(f"unknown series: {sid}")
                    if any(k in patch for k in ("series_id", "x_column", "y_column")):
                        raise ValueError("configure edits styles, not source columns or IDs")
                    _merge(existing[sid], patch)
            return self.apply_settings(state)

    def set_facecolor(self, color):
        """Set the chart background for native and browser rendering/export."""
        with self._lock:
            state = self.get_settings()
            if state.get("radial") is not None:
                state["radial"]["background"] = _color(color)
            else:
                rgba = _color(color)
                if rgba == _color("white"):
                    state.pop("background", None)
                else:
                    state["background"] = rgba
            return self.apply_settings(state)

    def set_draw_style(self, mode="precise", **options):
        """Use precise/sketch/milkyway/constellation with upstream parameters.

        Sketch draws line, scatter and errorbar series; bars, heatmaps and
        contours are not supported. Milkyway accepts line-only series.
        Constellation requires marker lines. These restrictions also apply to
        later additions and raw settings edits.
        """
        if mode not in ("precise", "sketch", "milkyway", "constellation"):
            raise ValueError("draw style must be precise, sketch, milkyway or constellation")
        if self.get_settings().get("radial") is not None:
            raise ValueError("use set_radial_style(material=...) for pie/donut charts")
        return self.configure(config={"draw_style": {"mode": mode, **options}})

    def configure_radial(self, *, style=None, slices=None, expected_slices=None, **properties):
        """Patch an existing pie/donut, preserving its values unless explicitly set.

        ``slices`` maps existing zero-based indices to appearance/label patches.
        Use the radial artist's ``set_values`` to replace category values.
        Advanced fields follow the upstream serialized radial model.
        """
        with self._lock:
            state = self.get_settings()
            if state.get("radial") is None:
                raise ValueError("create a pie or donut before configuring radial properties")
            chart = state["radial"]
            if expected_slices is not None and len(chart["slices"]) != expected_slices:
                raise ValueError("radial style replay requires the same slice count")
            if "slices" in properties or "value" in properties:
                raise ValueError("use set_values to change radial data")
            _merge(chart, properties)
            if style is not None:
                _merge(chart["style"], style)
            if slices is not None:
                for index, patch in slices.items():
                    if isinstance(index, bool) or not isinstance(index, (int, np.integer)) or not 0 <= index < len(chart["slices"]):
                        raise ValueError("slice index is out of range")
                    if "value" in patch:
                        raise ValueError("use set_values to change radial data")
                    if isinstance(patch.get("style"), dict) and chart["slices"][index]["style"] is None:
                        chart["slices"][index]["style"] = copy.deepcopy(chart["style"])
                    _merge(chart["slices"][index], patch)
            return self.apply_settings(state)

    def set_radial_style(self, *, material=None, **properties):
        """Edit upstream radial material, texture, camera, corners and outlines."""
        if material is not None:
            properties["material"] = _material(material)
        return self.configure_radial(style=properties)

    def to_code(self, variable="fig"):
        """Readable Python setters for an existing Figure with the same series.

        Font sizes are exported in points, using this Figure's DPI. Recreate the
        original plot at the same DPI before replaying its settings.
        """
        from ._codegen import settings_to_code
        return settings_to_code(self.get_settings(), self._default_config, self.dpi, variable)

    def select(self, x, y, *, edit_area=False):
        with self._lock:
            self._require_open()
            if self.backend != "native":
                raise RuntimeError("select requires backend='native'; pick data in the WebGPU widget")
            if self.get_settings().get("radial") is not None:
                if edit_area:
                    raise ValueError("radial selection addresses slices, not Cartesian plot-area handles")
                self._selection = json.loads(self._native.pick_json(float(x), float(y)))
                self._changed()
                return self._selection
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
            self._require_cartesian()
            if self.backend != "native":
                raise RuntimeError("select_object requires backend='native'; select objects in the WebGPU widget")
            if not any(s["series_id"] == target for s in self.get_settings()["series"]):
                self._native.bounds_json(target)  # Validate through renderer element IDs.
            self._native.clear_data_selection()
            self._selection = target

    def selection_bounds(self):
        with self._lock:
            self._require_open()
            if self.get_settings().get("radial") is not None:
                return None
            if self._selection is None or any(s["series_id"] == self._selection for s in self.get_settings()["series"]):
                return None
            return json.loads(self._native.bounds_json(self._selection))

    def drag(self, target, dx, dy, *, handle=None):
        with self._lock:
            self._require_open()
            self._require_cartesian()
            if self.backend != "native":
                raise RuntimeError("drag requires backend='native'; drag objects in the WebGPU widget")
            moved = self._native.drag(target, float(dx), float(dy), handle)
        if moved:
            self._changed()
        return moved

    def fit(self, padding=0.05):
        with self._lock:
            self._require_open()
            self._require_cartesian()
            self._native.fit(float(padding))
        self._changed()
        return self

    def widget(self, *, backend=None, auto_prepare=True):
        """Create a browser view; auto_prepare=False defers GPU initialization.

        Display the returned widget, then await prepare_async(). Repeated calls
        reuse the same widget and its original auto_prepare choice.
        """
        if self.get_settings().get("radial") is not None:
            raise RuntimeError("Pie/donut editing uses native show(); use to_png() for static notebook output")
        self._require_open()
        if backend not in (None, "webgpu", "png"):
            raise ValueError("widget backend must be webgpu or png")
        if not isinstance(auto_prepare, bool):
            raise ValueError("auto_prepare must be a boolean")
        if backend == "png":
            if self.backend != "native":
                raise RuntimeError("PNG fallback requires a native kernel GPU")
            from .widget import PNGFigureWidget
            widget = PNGFigureWidget(self)
        else:
            if self.backend != "webgpu":
                raise RuntimeError("Create Figure(backend='webgpu') for browser rendering, or explicitly use widget(backend='png') for kernel PNG fallback")
            from .widget import FigureWidget
            existing = next((w for w in self._widgets if isinstance(w, FigureWidget)), None)
            if existing is not None:
                return existing
            widget = FigureWidget(self, auto_prepare=auto_prepare)
        self._widgets.add(widget)
        return widget

    def prepare(self):
        """Prewarm native GPU pipelines and execute the current document once.

        This explicit operation releases the GIL, performs one completed RGBA
        readback, and does not encode PNG. Preparation is specific to this GPU,
        renderer and target format; future surface/format changes may compile.
        """
        if self.backend != "native":
            raise RuntimeError("Browser GPU preparation is asynchronous: await fig.prepare_async()")
        with self._lock:
            self._require_open()
            return json.loads(self._native.prepare_json())

    async def prepare_async(self, *, timeout=180):
        """Prepare a mounted browser GPU, or call native prepare().

        Browser reports include initialization/upload time if deferred and a
        separate prewarm_ms. No PNG is generated. This is process/view-local
        preparation, not a persistent shader cache or install-time compilation.
        """
        timeout = _timeout(timeout)
        if self.backend == "native":
            return self.prepare()
        with self._lock:
            self._require_open()
        return await self.widget().request("prepare", timeout=timeout)

    async def sync(self, *, timeout=30):
        """Await pending browser edits; settings getters return accepted revisions."""
        timeout = _timeout(timeout)
        if self.backend == "webgpu":
            await self.widget().request("barrier", timeout=timeout)
        return self.get_settings()

    async def to_png_async(self, *, scale=1.0, timeout=60):
        timeout = _timeout(timeout)
        if self.backend == "native":
            return self.to_png(scale=scale)
        return await self.widget().request("export", scale=float(scale), timeout=timeout)

    async def savefig_async(self, filename, *, dpi=None, scale=None, timeout=60):
        if dpi is not None and scale is not None:
            raise ValueError("choose dpi or scale, not both")
        value = float(dpi) / self.dpi if dpi is not None else (1.0 if scale is None else float(scale))
        data = await self.to_png_async(scale=value, timeout=timeout)
        if hasattr(filename, "write"):
            filename.write(data)
        else:
            path = Path(filename)
            if path.suffix.lower() != ".png":
                raise ValueError("savefig currently supports .png")
            path.write_bytes(data)

    def _repr_mimebundle_(self, **kwargs):
        if self.get_settings().get("radial") is not None:
            return {"image/png": self.to_png()}
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
            if threading.current_thread() is threading.main_thread() and self.backend == "native":
                from .desktop import poll_events
                poll_events()
            self._native = None
            if self.backend == "native":
                from ._native import collect_gpu
                collect_gpu()

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
    if not isinstance(base, dict):
        base = {}
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


def _code_tree(value, segments_function="text_segments"):
    if isinstance(value, dict):
        result = {}
        for key, current in value.items():
            if key == "segments" and isinstance(current, list):
                text = _segments_text(current)
                if text is not None:
                    result[key] = _CodeExpression(f"{segments_function}({text!r})")
                    continue
            result[key] = _code_tree(current, segments_function)
        return result
    if isinstance(value, list):
        return [_code_tree(v, segments_function) for v in value]
    return value


def text_segments(text):
    """Build renderer RichSegment values for ``text``.

    Unicode superscript/subscript characters such as ``"10⁻³"`` become
    superscript/subscript segments, exactly as the renderer maps them.
    """
    return _segments(text)


def _colormap(value):
    try:
        return {"viridis": "Viridis", "magma": "Magma", "turbo": "Turbo", "gray": "GrayScale", "grey": "GrayScale", "rdbu": "RdBu"}[value.lower()]
    except (KeyError, AttributeError):
        raise ValueError("cmap must be viridis, magma, turbo, gray or RdBu") from None


def _material(value):
    names = {"flat": "Flat", "matte": "Matte", "ceramic": "Ceramic",
             "brushed_metal": "BrushedMetal", "paper": "Paper", "wood": "Wood",
             "satin_metal": "SatinMetal", "toon": "Toon", "enamel": "Enamel",
             "hatch": "Hatch", "pearl": "Pearl"}
    if not isinstance(value, str) or value.lower().replace("-", "_") not in names:
        raise ValueError("unknown radial material; choose " + ", ".join(names))
    return names[value.lower().replace("-", "_")]


class Axes:
    def __init__(self, figure):
        self.figure = figure

    def set_draw_style(self, mode="precise", **options):
        return self.figure.set_draw_style(mode, **options)

    def pie(self, values, *, labels=None, colors=None, explode=None, startangle=90,
            inner_radius=None, material="flat", tilt=0, depth=0,
            labels_position="outside", label_format="name_percent", **style):
        """Create a native pie/donut using the upstream bounded radial renderer.

        Values are nonnegative with a positive sum; at most 64 slices. Material
        does not imply extrusion: choose tilt/depth explicitly for a 3D view.
        ``startangle=90`` starts at the top; slices proceed clockwise.
        """
        fig = self.figure
        if fig.backend != "native":
            raise RuntimeError("Pie/donut charts currently require backend='native'")
        values = _array(values)
        count = values.size
        if not 1 <= count <= 64 or not np.isfinite(values).all() or (values < 0).any() or not np.isfinite(values.sum()) or values.sum() <= 0:
            raise ValueError("pie/donut needs 1..64 finite nonnegative values with a positive finite sum")
        labels = [f"Slice {i + 1}" for i in range(count)] if labels is None else list(labels)
        colors = [_COLORS[i % len(_COLORS)] for i in range(count)] if colors is None else list(colors)
        explode = [0.0] * count if explode is None else list(explode)
        if not len(labels) == len(colors) == len(explode) == count:
            raise ValueError("labels, colors and explode must match the number of values")
        placements = {"none": "None", "inside": "Inside", "outside": "Outside"}
        formats = {"name": "Name", "value": "Value", "percent": "Percent", "name_percent": "NamePercent",
                   "name_value": "NameValue", "value_percent": "ValuePercent", "name_value_percent": "NameValuePercent"}
        if labels_position not in placements or label_format not in formats:
            raise ValueError("unsupported radial label placement/format")
        from ._native import default_radial_json
        chart = json.loads(default_radial_json())
        title = fig.get_settings()["config"]["chart_title"]["text"]
        chart.update(title=_text(title), font_size=11 * fig.dpi / 72,
                     kind="Pie" if inner_radius is None else {"Donut": {"inner_radius": float(inner_radius)}},
                     start_angle_degrees=-float(startangle), labels=placements[labels_position],
                     label_format=formats[label_format])
        chart["style"].update(material=_material(material), tilt_degrees=float(tilt), depth=float(depth), **style)
        chart["slices"] = [dict(label=str(label), value=float(value), color=_color(color),
                                explode=float(offset), style=None, labels=None, label_format=None, label_color=None)
                           for value, label, color, offset in zip(values, labels, colors, explode)]
        with fig._lock:
            fig._require_open()
            fig._native.set_radial(json.dumps(chart, allow_nan=False))
        fig._changed()
        return RadialArtist(fig)

    def donut(self, values, *, inner_radius=0.5, **kwargs):
        """Create a donut; accepts the same labels/material/style options as pie."""
        return self.pie(values, inner_radius=inner_radius, **kwargs)

    def _add(self, x, y, render_type, label=None, id=None, extra_columns=(), config=None, bounds=None):
        fig = self.figure
        with fig._lock:
            fig._require_open()
            if fig.get_settings().get("radial") is not None:
                raise ValueError("create a separate Figure for Cartesian series")
            mode = fig.get_settings()["config"].get("draw_style", {}).get("mode", "precise")
            if mode == "milkyway" and "Line" not in render_type:
                raise ValueError("Milkyway supports line-only series; scatter and marker lines are disabled")
            if mode == "constellation" and "ScatterLine" not in render_type:
                raise ValueError("Constellation requires line series with markers (plot(..., marker='o'))")
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
                fig._native.add_series_fitted(
                    json.dumps(spec, allow_nan=False),
                    json.dumps(config, allow_nan=False) if config is not None else None,
                    bounds,
                )
            except Exception:
                for name in reversed(uploaded):
                    fig._native.remove_column(name)
                raise
            fig._next_series += 1
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
        bar = json.loads(default_colorbar_json())
        bar["colormap"] = _colormap(cmap)
        bar["axis"]["min"], bar["axis"]["max"] = low, high
        bar["axis"]["major_spacing"] = (high - low) / 5
        with self.figure._lock:
            config = self.figure.get_settings()["config"]
            config["colorbar"] = bar
            for key in ("left_y", "right_y"):
                config[key]["inverted"] = origin == "upper"
            return self._add(x, y, style, id=id, extra_columns=columns, config=config, bounds=ext)

    def set_title(self, text, **kwargs):
        return self.figure.update("chart_title", text=text, **kwargs)

    def set_xlabel(self, text, **kwargs):
        self.figure._require_cartesian()
        return self.figure.update("axis_title_bottom", text=text, **kwargs)

    def set_ylabel(self, text, **kwargs):
        self.figure._require_cartesian()
        return self.figure.update("axis_title_left", text=text, **kwargs)

    def _set_scale(self, axis, scale):
        self.figure._require_cartesian()
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
        self.figure._require_cartesian()
        return "log" if self.figure.get_settings()["config"]["bottom_x"]["scale"] == "Logarithmic" else "linear"

    def get_yscale(self):
        self.figure._require_cartesian()
        return "log" if self.figure.get_settings()["config"]["left_y"]["scale"] == "Logarithmic" else "linear"

    def set_xlim(self, left, right):
        self.figure._require_cartesian()
        with self.figure._lock:
            self.figure._require_open()
            self.figure._native.set_range("x", float(left), float(right))
        self.figure._changed()
        return (left, right)

    def set_ylim(self, bottom, top):
        self.figure._require_cartesian()
        with self.figure._lock:
            self.figure._require_open()
            self.figure._native.set_range("y", float(bottom), float(top))
        self.figure._changed()
        return (bottom, top)

    def _set_lim_keeping_ticks(self, keys, low, high):
        low, high = float(low), float(high)
        if not math.isfinite(low) or not math.isfinite(high) or low >= high:
            raise ValueError("range must be finite and increasing")
        with self.figure._lock:
            self.figure._require_open()
            state = self.figure.get_settings()
            for key in keys:
                axis = state["config"][key]
                axis["min"], axis["max"] = low, high
                axis["range_locked"] = True
            self.figure.apply_settings(state)
        return (low, high)

    def set_xlim_without_tick_auto(self, left, right):
        """Set the x range only; tick spacing and labels stay as configured.

        ``set_xlim`` re-derives readable ticks for the new range. Use this when
        the tick settings were chosen explicitly and must be kept.
        """
        self.figure._require_cartesian()
        return self._set_lim_keeping_ticks(("bottom_x", "top_x"), left, right)

    def set_ylim_without_tick_auto(self, bottom, top):
        """Set the y range only; tick spacing and labels stay as configured."""
        self.figure._require_cartesian()
        return self._set_lim_keeping_ticks(("left_y", "right_y"), bottom, top)

    def grid(self, visible=True):
        self.figure._require_cartesian()
        state = self.figure.get_settings()
        state["config"]["grid"]["show_major_x"] = bool(visible)
        state["config"]["grid"]["show_major_y"] = bool(visible)
        self.figure.apply_settings(state)

    def legend(self, visible=True):
        self.figure._require_cartesian()
        from ._native import rebuild_legend_json
        state = self.figure.get_settings()
        state["config"]["legend"]["content"] = json.loads(rebuild_legend_json(json.dumps(state["series"]), json.dumps(state["config"]["legend"]["content"])))
        state["config"]["legend"]["visible"] = bool(visible)
        self.figure.apply_settings(state)


def figure(*args, **kwargs):
    return Figure(*args, **kwargs)


def subplots(nrows=1, ncols=1, **kwargs):
    """Return a Figure and Axes. A Figure currently has one panel."""
    if (nrows, ncols) != (1, 1):
        raise NotImplementedError(f"multiple panels are not supported in figgyplot {__version__}")
    fig = Figure(**kwargs)
    return fig, fig.axes[0]
