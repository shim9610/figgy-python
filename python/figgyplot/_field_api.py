"""Scalar-field appearance and explicit contour-label placement."""

import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class ContourLabel:
    """A label on a contour level, in data coordinates with a data tangent."""

    level: int
    x: float
    y: float
    tangent: tuple = (1, 0)


class ContourAppearance:
    def __init__(self, artist):
        self.artist = artist
        self.figure = artist.figure
        self._node(self.figure.get_settings())

    def _node(self, state):
        body = self.artist._body(state)
        if "contour" not in body:
            raise AttributeError("this artist has no contour lines")
        return body["contour"]

    def _edit(self, operation):
        state = self.figure.get_settings()
        operation(self._node(state))
        self.figure.apply_settings(state)
        return self

    def set_levels(self, levels):
        from ._validation import number as _number

        values = [_number(v, "contour level") for v in levels]
        return self._edit(lambda node: node.update(levels=values))

    def get_levels(self):
        return tuple(self._node(self.figure.get_settings())["levels"])

    def set_style(self, *, color=None, linewidth=None, linestyle=None, colors=...):
        from .figure import _color, _LINES
        from ._validation import number as _number

        def edit(node):
            if color is not None:
                node["line"]["line_color"] = _color(color)
            if linewidth is not None:
                node["line"]["line_width"] = (
                    _number(linewidth, "linewidth") * self.figure.dpi / 72
                )
            if linestyle is not None:
                if linestyle not in _LINES:
                    raise ValueError("linestyle must be -, --, : or -.")
                node["line"]["line_style"] = _LINES[linestyle]
            if colors is not ...:
                if colors is None:
                    node.pop("per_level_color", None)
                else:
                    node["per_level_color"] = [_color(v) for v in colors]

        return self._edit(edit)

    def set_labels(
        self,
        visible=True,
        *,
        fontsize=None,
        color=None,
        formatter=None,
        spacing=None,
        positions=None,
        background=...,
        padding=None,
    ):
        """Style labels or place ContourLabel records; positions=[] restores auto placement.

        visible=None removes label configuration. Lengths use points.
        """
        from .figure import _color
        from ._validation import number as _number
        from .ticker import SignificantFormatter

        def edit(node):
            if visible is None:
                node.pop("labels", None)
                return
            labels = node.setdefault(
                "labels",
                dict(
                    visible=True,
                    font_size=12.0,
                    color=_color("black"),
                    format="Decimal",
                    significant_digits=3,
                    spacing_px=100.0,
                    anchors=[],
                    bg_padding_px=0.0,
                ),
            )
            labels["visible"] = bool(visible)
            for public, key in (
                (fontsize, "font_size"),
                (spacing, "spacing_px"),
                (padding, "bg_padding_px"),
            ):
                if public is not None:
                    labels[key] = _number(public, key) * self.figure.dpi / 72
            if color is not None:
                labels["color"] = _color(color)
            if formatter is not None:
                if not isinstance(formatter, SignificantFormatter):
                    raise TypeError(
                        "formatter requires SignificantFormatter or TimestampFormatter"
                    )
                labels.update(
                    format=formatter._format(), significant_digits=formatter.precision
                )
            if background is not ...:
                if background is None:
                    labels.pop("bg_color", None)
                else:
                    labels["bg_color"] = _color(background)
            if positions is not None:
                anchors = []
                for position in positions:
                    if not isinstance(position, ContourLabel):
                        raise TypeError("positions must contain ContourLabel values")
                    if (
                        isinstance(position.level, bool)
                        or not isinstance(position.level, int)
                        or position.level < 0
                    ):
                        raise ValueError("label level must be a nonnegative index")
                    tx, ty = position.tangent
                    anchors.append(
                        dict(
                            level_index=position.level,
                            x=_number(position.x, "x"),
                            y=_number(position.y, "y"),
                            tx=_number(tx, "tangent"),
                            ty=_number(ty, "tangent"),
                        )
                    )
                labels["anchors"] = anchors

        return self._edit(edit)


def set_grid(artist, source):
    """Bind an already registered matrix without uploading or transposing data."""
    from ._artist_appearance import GridReference

    if not isinstance(source, GridReference) or source.figure is not artist.figure:
        raise ValueError("source must be a grid registered with this Figure")
    state = artist.figure.get_settings()
    body = artist._body(state)
    if "matrix" not in body:
        raise AttributeError("artist is not a scalar field")
    body["matrix"] = copy.deepcopy(source._native())
    artist.figure.apply_settings(state)
    return artist
