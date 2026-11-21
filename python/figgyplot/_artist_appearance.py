"""Named styles, resident data references and per-element appearance controls."""

import copy
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class MarkerStyle:
    color: object = None
    marker: object = None
    markersize: object = None
    fillstyle: object = None


@dataclass(frozen=True)
class ErrorBarStyle:
    color: object = None
    linewidth: object = None
    capsize: object = None
    capthick: object = None


@dataclass(frozen=True)
class BinStyle:
    facecolor: object = None
    edgecolor: object = None
    linewidth: object = None
    gap: object = None
    width: object = None


_PARTS = {
    "markers": (
        "scatter",
        MarkerStyle,
        dict(
            color=("point_color", "color"),
            marker=("point_shape", "marker"),
            markersize=("point_size", "diameter"),
        ),
        "point",
    ),
    "errors": (
        "err_style",
        ErrorBarStyle,
        dict(
            color=("error_bar_color", "color"),
            linewidth=("error_bar_width", "length"),
            capsize=("error_bar_cap_size", "length"),
            capthick=("cap_width", "length"),
        ),
        "error_bar",
    ),
    "bins": (
        "bar",
        BinStyle,
        dict(
            facecolor=("fill_color", "color"),
            edgecolor=("border_color", "color"),
            linewidth=("border_width", "length"),
            gap=("gap_px", "length"),
            width=("width_ratio", "number"),
        ),
        "bar",
    ),
}


def _style(value, part, dpi, decode=False):
    from .figure import _color, _MARKERS
    from ._validation import number as _number

    _, cls, fields, _ = _PARTS[part]
    if not decode and not isinstance(value, cls):
        raise TypeError("expected " + cls.__name__)
    result = {}
    for name, (key, kind) in fields.items():
        item = value.get(key) if decode else getattr(value, name)
        if item is None:
            continue
        if decode:
            if kind == "color":
                item = tuple(item[c] for c in "rgba")
            elif kind == "marker":
                from ._markers import decode_marker

                item, fillstyle = decode_marker(item)
                if fillstyle is not None:
                    result["fillstyle"] = fillstyle
            elif kind in ("length", "diameter"):
                item = item * (144 if kind == "diameter" else 72) / dpi
            result[name] = item
        else:
            if kind == "color":
                item = _color(item)
            elif kind == "marker":
                item = _MARKERS.get(item, item)
            else:
                item = _number(item, name)
                if item < 0:
                    raise ValueError(name + " must be nonnegative")
                if kind in ("length", "diameter"):
                    item *= dpi / (144 if kind == "diameter" else 72)
            result[key] = item
    if not decode and part == "markers" and value.fillstyle is not None:
        from ._markers import encode_marker

        if value.marker is None:
            raise ValueError("fillstyle requires an explicit marker")
        result["point_shape"] = encode_marker(value.marker, value.fillstyle)
    return cls(**result) if decode else result


@dataclass(frozen=True)
class ColumnReference:
    figure: object
    name: str

    def __repr__(self):
        return "ColumnReference(" + repr(self.name) + ")"


@dataclass(frozen=True)
class GridReference:
    figure: object
    columns: tuple
    axis: str = "y"
    coordinates: str = "centers"

    def _native(self):
        if self.axis not in ("x", "y") or self.coordinates not in ("centers", "edges"):
            raise ValueError("grid axis is x/y; coordinates are centers/edges")
        return dict(
            columns=[_column(v, self.figure) for v in self.columns],
            orientation="ColumnsAreY" if self.axis == "y" else "ColumnsAreX",
            grid_layout=self.coordinates.title(),
        )


def _column(value, figure):
    from ._document import identifier

    if isinstance(value, ColumnReference):
        if value.figure is not figure:
            raise ValueError("column belongs to another Figure")
        return value.name
    if not isinstance(value, str):
        raise TypeError("source must be a resident column reference or column name")
    return identifier(value)


def _grid(value, figure):
    return GridReference(
        figure,
        tuple(value["columns"]),
        "y" if value["orientation"] == "ColumnsAreY" else "x",
        value["grid_layout"].lower(),
    )


class DataRegistry:
    def __init__(self, figure):
        self.figure = figure

    def column(self, name):
        return ColumnReference(self.figure, _column(name, self.figure))

    def __getitem__(self, name):
        return self.column(name)

    def grid(self, columns, *, axis="y", coordinates="centers"):
        result = GridReference(self.figure, tuple(columns), axis, coordinates)
        result._native()
        return result

    def keys(self):
        return tuple(json.loads(self.figure._native.column_extents_json()))

    def add(self, name, values):
        from .figure import _array

        self.figure._require_data_edit()
        self.figure._require_open()
        name = _column(name, self.figure)
        with self.figure._lock:
            if name in self.keys():
                raise ValueError("column already exists: " + name)
            self.figure._native.upload_column(name, _array(values))
            self.figure._changed()
        return self.column(name)


class ArtistData:
    def __init__(self, artist):
        self.artist = artist

    def __getattr__(self, role):
        fig = self.artist.figure
        spec = self.artist._spec(fig.get_settings())
        body = next(iter(spec["render_type"].values()))
        if role in ("x", "y"):
            return ColumnReference(fig, spec[role + "_column"])
        if role == "values" and "matrix" in body:
            return _grid(body["matrix"], fig)
        if role in ("u", "v") and "components" in body:
            kind, components = next(iter(body["components"].items()))
            value = components[role]
            return _grid(value, fig) if kind == "Grid" else ColumnReference(fig, value)
        if role == "color":
            if body.get("scatter", {}).get("point_color_map"):
                return ColumnReference(
                    fig, body["scatter"]["point_color_map"]["column"]
                )
            if body.get("style", {}).get("color_map"):
                kind, value = next(iter(body["style"]["color_map"].items()))
                return (
                    _grid(value, fig) if kind == "Grid" else ColumnReference(fig, value)
                )
        if role == "size" and body.get("scatter", {}).get("point_size_map"):
            return ColumnReference(fig, body["scatter"]["point_size_map"]["column"])
        if role in ("marker_indices", "error_indices"):
            part = "scatter" if role == "marker_indices" else "err_style"
            prefix = "point" if role == "marker_indices" else "error_bar"
            column = body.get(part, {}).get(prefix + "_style_index_column")
            if column:
                return ColumnReference(fig, column)
        raise AttributeError("this artist has no " + role + " data source")


def _domain(figure, column, domain):
    from ._validation import number as _number

    if domain is None:
        bounds = json.loads(figure._native.column_extents_json()).get(column)
        if not bounds or any(v is None for v in bounds):
            raise ValueError("source has no finite resident bounds")
        low, high = bounds
        if low == high:
            high = low + max(1.0, abs(low) * 0.01)
    else:
        low, high = domain
    low, high = _number(low, "domain minimum"), _number(high, "domain maximum")
    if low >= high:
        raise ValueError("mapping domain must be increasing")
    return low, high


class ElementAppearance:
    """Shared marker/error/bin defaults, palettes and sparse overrides."""

    def __init__(self, artist, part):
        self.artist, self.part = artist, part

    def __getitem__(self, index):
        return ElementStyle(self, index)

    @property
    def palette(self):
        if self.part == "bins":
            raise AttributeError("histogram bins have sparse overrides only")
        return Palette(self)

    def _node(self, state):
        key = _PARTS[self.part][0]
        body = self.artist._body(state)
        if key not in body:
            raise AttributeError("this artist has no " + self.part)
        return body[key]

    def set(self, **properties):
        cls = _PARTS[self.part][1]
        state = self.artist.figure.get_settings()
        self._node(state).update(
            _style(cls(**properties), self.part, self.artist.figure.dpi)
        )
        self.artist.figure.apply_settings(state)
        return self

    def get_style(self):
        return _style(
            self._node(self.artist.figure.get_settings()),
            self.part,
            self.artist.figure.dpi,
            True,
        )

    def set_palette(self, entries, *, source=None):
        if self.part == "bins":
            raise NotImplementedError(
                "histograms support bin overrides, not a style-index palette"
            )
        state = self.artist.figure.get_settings()
        node = self._node(state)
        prefix = _PARTS[self.part][3]
        if entries is None:
            node.pop(prefix + "_style_table", None)
            node.pop(prefix + "_style_index_column", None)
        else:
            node[prefix + "_style_table"] = [
                _style(v, self.part, self.artist.figure.dpi) for v in entries
            ]
            if source is None:
                node.pop(prefix + "_style_index_column", None)
            else:
                node[prefix + "_style_index_column"] = _column(
                    source, self.artist.figure
                )
        self.artist.figure.apply_settings(state)
        return self

    def get_palette(self):
        prefix = _PARTS[self.part][3]
        entries = self._node(self.artist.figure.get_settings()).get(
            prefix + "_style_table"
        )
        return (
            None
            if entries is None
            else [_style(v, self.part, self.artist.figure.dpi, True) for v in entries]
        )

    def set_overrides(self, styles):
        state = self.artist.figure.get_settings()
        node = self._node(state)
        key = _PARTS[self.part][3] + "_style_overrides"
        if styles is None:
            node.pop(key, None)
        else:
            pairs = styles.items() if hasattr(styles, "items") else styles
            entries = []
            for index, style in pairs:
                from numbers import Integral

                if (
                    isinstance(index, bool)
                    or not isinstance(index, Integral)
                    or index < 0
                ):
                    raise ValueError("override indices must be nonnegative integers")
                entries.append(
                    dict(
                        index=int(index),
                        **_style(style, self.part, self.artist.figure.dpi),
                    )
                )
            node[key] = entries
        self.artist.figure.apply_settings(state)
        return self

    def get_overrides(self):
        entries = self._node(self.artist.figure.get_settings()).get(
            _PARTS[self.part][3] + "_style_overrides"
        )
        return (
            None
            if entries is None
            else [
                (v["index"], _style(v, self.part, self.artist.figure.dpi, True))
                for v in entries
            ]
        )

    def map_color(self, source, *, clim=None, cmap=None):
        if self.part != "markers":
            raise AttributeError("color-value mapping requires point markers")
        from ._color_scale import _set_colorbar

        fig = self.artist.figure
        state = fig.get_settings()
        node = self._node(state)
        if source is None:
            node.pop("point_color_map", None)
        else:
            column = _column(source, fig)
            low, high = _domain(fig, column, clim)
            owner = self.artist._panel_axes(state)
            config = owner._config(state)
            current = config.get("colorbar", {}).get("colormap", "Viridis")
            _set_colorbar(config, current if cmap is None else cmap, low, high)
            node["point_color_map"] = {"column": column}
        fig.apply_settings(state)
        return self

    def map_size(self, source, *, domain=None, markersizes=(4, 16), scale="area"):
        if self.part != "markers":
            raise AttributeError("size-value mapping requires point markers")
        from ._validation import number as _number

        fig = self.artist.figure
        state = fig.get_settings()
        node = self._node(state)
        if source is None:
            node.pop("point_size_map", None)
        else:
            if scale not in ("area", "radius"):
                raise ValueError("size scale must be area or radius")
            column = _column(source, fig)
            low, high = _domain(fig, column, domain)
            small, large = (_number(v, "marker size") for v in markersizes)
            if not 0 <= small <= large:
                raise ValueError("marker size range must be nonnegative and increasing")
            node["point_size_map"] = dict(
                column=column,
                domain_min=low,
                domain_max=high,
                min_px=small * fig.dpi / 144,
                max_px=large * fig.dpi / 144,
                scale=scale.title(),
            )
        fig.apply_settings(state)
        return self


class ElementStyle:
    def __init__(self, appearance, index, palette=False):
        from numbers import Integral

        if isinstance(index, bool) or not isinstance(index, Integral) or index < 0:
            raise ValueError("style index must be a nonnegative integer")
        self.appearance, self.index, self.palette = appearance, int(index), palette

    def set(self, **properties):
        appearance = self.appearance
        fig = appearance.artist.figure
        state = fig.get_settings()
        node = appearance._node(state)
        _, cls, fields, prefix = _PARTS[appearance.part]
        patch = _style(cls(**properties), appearance.part, fig.dpi)
        if self.palette:
            entries = node.get(prefix + "_style_table")
            if entries is None or self.index >= len(entries):
                raise IndexError("palette entry does not exist")
            targets = [entries[self.index]]
            target = targets[0]
        else:
            entries = node.setdefault(prefix + "_style_overrides", [])
            targets = [v for v in entries if v["index"] == self.index]
            if not targets:
                target = {"index": self.index}
                entries.append(target)
                targets = [target]
            else:
                target = targets[-1]
        for name, value in properties.items():
            if value is None:
                for entry in targets:
                    entry.pop(
                        "point_shape" if name == "fillstyle" else fields[name][0], None
                    )
        target.update(patch)
        fig.apply_settings(state)
        return self

    def get_override(self):
        appearance = self.appearance
        node = appearance._node(appearance.artist.figure.get_settings())
        prefix = _PARTS[appearance.part][3]
        if self.palette:
            entries = node.get(prefix + "_style_table") or []
            if self.index >= len(entries):
                raise IndexError("palette entry does not exist")
            value = entries[self.index]
        else:
            value = {}
            for item in node.get(prefix + "_style_overrides") or []:
                if item["index"] == self.index:
                    value.update(item)
        return _style(value, appearance.part, appearance.artist.figure.dpi, True)

    def remove(self):
        if self.palette:
            raise NotImplementedError(
                "replace the palette explicitly when changing its slot numbering"
            )
        appearance = self.appearance
        fig = appearance.artist.figure
        state = fig.get_settings()
        node = appearance._node(state)
        key = _PARTS[appearance.part][3] + "_style_overrides"
        node[key] = [v for v in node.get(key) or [] if v["index"] != self.index]
        fig.apply_settings(state)


class Palette:
    def __init__(self, appearance):
        self.appearance = appearance

    def __getitem__(self, index):
        return ElementStyle(self.appearance, index, True)

    def set(self, entries, *, source=None):
        return self.appearance.set_palette(entries, source=source)

    def append(self, style=None):
        cls = _PARTS[self.appearance.part][1]
        values = self.appearance.get_palette() or []
        values.append(cls() if style is None else style)
        self.appearance.set_palette(values, source=self.source)
        return self[len(values) - 1]

    @property
    def source(self):
        app = self.appearance
        name = app._node(app.artist.figure.get_settings()).get(
            _PARTS[app.part][3] + "_style_index_column"
        )
        return None if name is None else ColumnReference(app.artist.figure, name)

    def set_source(self, source):
        return self.appearance.set_palette(self.appearance.get_palette(), source=source)


class VectorAppearance:
    def __init__(self, artist):
        self.artist = artist

    def _style(self, state):
        body = self.artist._body(state)
        if "components" not in body:
            raise AttributeError("this artist is not a vector field")
        return body["style"]

    def set(
        self,
        *,
        color=None,
        linewidth=None,
        head_length=None,
        head_width=None,
        min_length=None,
        pivot=None,
        scale=None,
        units=None,
    ):
        from .figure import _color
        from ._validation import number as _number

        fig = self.artist.figure
        state = fig.get_settings()
        style = self._style(state)
        if color is not None:
            style["color"] = _color(color)
        for value, key in [
            (linewidth, "width_px"),
            (head_length, "head_length_px"),
            (head_width, "head_width_px"),
            (min_length, "min_length_px"),
        ]:
            if value is not None:
                value = _number(value, key)
                if value < 0:
                    raise ValueError("vector sizes must be nonnegative")
                style[key] = value * fig.dpi / 72
        if pivot is not None:
            if pivot not in ("tail", "middle", "tip"):
                raise ValueError("vector pivot must be tail, middle or tip")
            style["pivot"] = pivot.title()
        if scale is not None or units is not None:
            kind, params = next(iter(style["scale"].items()))
            old = next(iter(params.values()))
            units = ("data" if kind == "Data" else "pixels") if units is None else units
            if units not in ("data", "pixels"):
                raise ValueError("vector units must be data or pixels")
            number = _number(old if scale is None else scale, "vector scale")
            if number == 0:
                raise ValueError("vector scale cannot be zero")
            style["scale"] = (
                {"Data": dict(factor=number)}
                if units == "data"
                else {"Pixels": dict(px_per_unit=number)}
            )
        fig.apply_settings(state)
        return self

    def map_color(self, source, *, clim=None, cmap=None):
        from ._color_scale import _set_colorbar

        fig = self.artist.figure
        state = fig.get_settings()
        style = self._style(state)
        if source is None:
            style.pop("color_map", None)
        else:
            if isinstance(source, GridReference):
                if source.figure is not fig:
                    raise ValueError("grid belongs to another Figure")
                binding = source._native()
                style["color_map"] = {"Grid": binding}
                bounds = []
                if clim is None:
                    extents = json.loads(fig._native.column_extents_json())
                    bounds = [extents.get(name) for name in binding["columns"]]
                    bounds = [v for v in bounds if v and all(x is not None for x in v)]
                    if not bounds:
                        raise ValueError("grid has no finite resident bounds")
                    low, high = min(v[0] for v in bounds), max(v[1] for v in bounds)
                    if low == high:
                        high = low + max(1.0, abs(low) * 0.01)
                    clim = (low, high)
                low, high = _domain(fig, "", clim)
            else:
                name = _column(source, fig)
                style["color_map"] = {"Column": name}
                low, high = _domain(fig, name, clim)
            owner = self.artist._panel_axes(state)
            config = owner._config(state)
            current = config.get("colorbar", {}).get("colormap", "Viridis")
            _set_colorbar(config, current if cmap is None else cmap, low, high)
        fig.apply_settings(state)
        return self
