"""Named annotation editing; coordinate conversion stays explicit."""

import copy


def anchor(xy, coords):
    from ._matplotlib import _number

    x, y = (_number(v, "coordinate") for v in xy)
    if coords == "axes fraction":
        return {"Ratio": dict(x=x, y=1 - y)}
    if coords not in ("data", "ratio"):
        raise ValueError(
            "coords must be data, ratio (top-left), or axes fraction (bottom-left)"
        )
    return {coords.title(): dict(x=x, y=y)}


class AnnotationEditing:
    def _rich_text(self):
        kind, body = next(
            iter(self._find(self.figure.get_settings())[2]["kind"].items())
        )
        rich = body.get("label" if kind == "ReferenceLine" else "text")
        if rich is None:
            raise AttributeError("annotation has no text label")
        return rich

    def get_color(self):
        color = self._rich_text()["color"]
        return tuple(color[k] for k in "rgba")

    def get_fontfamily(self):
        return [self._rich_text()["font"]]

    def _edit(self, operation):
        state = self.figure.get_settings()
        item = self._find(state)[2]
        name, body = next(iter(item["kind"].items()))
        operation(name, body)
        self.figure.apply_settings(state)
        return self

    def set_style(
        self,
        *,
        color=None,
        linewidth=None,
        linestyle=None,
        head_length=None,
        head_width=None,
    ):
        """Edit a reference-line/arrow stroke or a span fill; lengths are points."""
        from .figure import _color, _LINES
        from ._matplotlib import _number

        def edit(name, body):
            if name == "Span":
                if any(
                    v is not None
                    for v in (linewidth, linestyle, head_length, head_width)
                ):
                    raise AttributeError("spans support a fill color only")
                if color is not None:
                    body["fill"] = _color(color)
                return
            if name not in ("ReferenceLine", "Arrow"):
                raise AttributeError("text frames use set_bbox")
            style = body["style"]
            line = style["line"] if name == "Arrow" else style
            if color is not None:
                line["color"] = _color(color)
            if linewidth is not None:
                line["width"] = _number(linewidth, "linewidth") * self.figure.dpi / 72
            if linestyle is not None:
                if linestyle not in _LINES:
                    raise ValueError("linestyle must be -, --, : or -.")
                line["style"] = _LINES[linestyle]
            for key, value in (
                ("head_length", head_length),
                ("head_width", head_width),
            ):
                if value is not None:
                    if name != "Arrow":
                        raise AttributeError("arrow heads require an arrow")
                    style[key] = _number(value, key) * self.figure.dpi / 72

        return self._edit(edit)

    def set_bbox(
        self, *, facecolor="white", edgecolor="black", linewidth=1, pad=4, visible=True
    ):
        """Set/remove a text frame. Padding is in points, independent of font size."""
        from .figure import _color
        from ._matplotlib import _number

        def edit(name, body):
            if name != "Text":
                raise AttributeError("only text annotations have a frame")
            body["box_style"] = (
                None
                if not visible
                else dict(
                    fill=_color(facecolor),
                    border_color=_color(edgecolor),
                    border_width=_number(linewidth, "linewidth") * self.figure.dpi / 72,
                    padding=_number(pad, "padding") * self.figure.dpi / 72,
                )
            )

        return self._edit(edit)

    def set_endpoints(self, start, end, *, coords="data", endcoords=None):
        """Move both arrow endpoints, including mixed data/fraction coordinates."""

        def edit(name, body):
            if name != "Arrow":
                raise AttributeError("endpoints require an arrow")
            body["from"] = anchor(start, coords)
            body["to"] = anchor(end, coords if endcoords is None else endcoords)

        return self._edit(edit)

    def set_value(self, value):
        from ._matplotlib import _number

        def edit(name, body):
            if name != "ReferenceLine":
                raise AttributeError("set_value requires a reference line")
            body["value"] = _number(value, "value")

        return self._edit(edit)

    def set_bounds(self, low, high):
        from ._matplotlib import _number

        def edit(name, body):
            if name != "Span":
                raise AttributeError("set_bounds requires a span")
            body["from"], body["to"] = _number(low, "low"), _number(high, "high")

        return self._edit(edit)

    def set_label(
        self,
        text,
        *,
        fontsize=11,
        color="black",
        fontfamily=None,
        multialignment="left",
    ):
        """Set optional text on a reference line or arrow; None removes it."""
        from .figure import _color, _segments
        from ._matplotlib import _number

        def edit(name, body):
            if name not in ("Arrow", "ReferenceLine"):
                raise AttributeError("use set_text for text annotations")
            key = "label" if name == "ReferenceLine" else "text"
            if text is None:
                body[key] = None
                return
            if multialignment not in ("left", "center", "right"):
                raise ValueError("multialignment must be left, center or right")
            rich = copy.deepcopy(self.figure._default_config["legend"]["content"])
            rich.update(
                segments=_segments(text, dpi=self.figure.dpi),
                color=_color(color),
                font_size=_number(fontsize, "fontsize", positive=True)
                * self.figure.dpi
                / 72,
            )
            rich.pop("align", None)
            if multialignment != "left":
                rich["align"] = multialignment.title()
            if fontfamily is not None:
                rich["font"] = self.figure._check_font(fontfamily)
            body[key] = rich

        return self._edit(edit)

    def set_multialignment(self, alignment):
        if alignment not in ("left", "center", "right"):
            raise ValueError("alignment must be left, center or right")

        def edit(name, body):
            rich = body.get("label" if name == "ReferenceLine" else "text")
            if rich is None:
                raise AttributeError("annotation has no label")
            rich.pop("align", None)
            if alignment != "left":
                rich["align"] = alignment.title()

        return self._edit(edit)
