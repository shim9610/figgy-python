"""Public styled text runs shared by titles, labels, legends and annotations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextRun:
    """One styled span. Font size is in points; width/dashes use em units.

    script is normal, super or sub. None color/fontsize inherits the parent.
    rule draws a line in place of glyphs; fill shades below a legend rule.
    """

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    script: str = "normal"
    greek: bool = False
    color: object = None
    fontsize: object = None
    width: object = None
    rule: bool = False
    dashes: object = None
    fill: object = None

    def _segments(self, dpi):
        from .figure import _color
        from ._matplotlib import _number

        if not isinstance(self.text, str) or self.script not in (
            "normal",
            "super",
            "sub",
        ):
            raise ValueError("TextRun requires text and script normal/super/sub")
        for flag in (self.bold, self.italic, self.underline, self.greek, self.rule):
            if not isinstance(flag, bool):
                raise TypeError("text style switches must be bool")
        style = dict(
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            superscript=self.script == "super",
            subscript=self.script == "sub",
            greek=self.greek,
        )
        for key, value in (("color", self.color), ("rule_band", self.fill)):
            if value is not None:
                style[key] = _color(value)
        if self.fontsize is not None:
            style["font_size"] = (
                _number(self.fontsize, "fontsize", positive=True) * dpi / 72
            )
        if self.width is not None:
            style["field_em"] = _number(self.width, "width", positive=True)
        if self.rule:
            style["rule"] = True
        if self.dashes is not None:
            style["rule_dash"] = [
                _number(v, "dash length", positive=True) for v in self.dashes
            ]
        return [dict(text=char, **style) for char in self.text]


def run_expression(segments, dpi, name="TextRun"):
    """Render compact public spans without exposing per-glyph schema records."""
    from ._api_codegen import _color_literal, _points

    groups = []
    for segment in segments:
        style = {k: v for k, v in segment.items() if k != "text"}
        if groups and groups[-1][1] == style:
            groups[-1][0] += segment["text"]
        else:
            groups.append([segment["text"], style])
    expressions = []
    for text, style in groups:
        args = [repr(text)]
        for key in ("bold", "italic", "underline", "greek", "rule"):
            if style.get(key):
                args.append(key + "=True")
        if style.get("superscript") and style.get("subscript"):
            raise ValueError(
                "simultaneous subscript and superscript require exact recovery"
            )
        if style.get("superscript") or style.get("subscript"):
            args.append(
                "script=" + repr("super" if style.get("superscript") else "sub")
            )
        for public, native in (("color", "color"), ("fill", "rule_band")):
            if style.get(native) is not None:
                args.append(public + "=" + repr(_color_literal(style[native])))
        if style.get("font_size") is not None:
            args.append("fontsize=" + repr(_points(style["font_size"], dpi)))
        for public, native in (("width", "field_em"), ("dashes", "rule_dash")):
            if style.get(native) is not None:
                args.append(public + "=" + repr(style[native]))
        expressions.append(name + "(" + ", ".join(args) + ")")
    return "[" + ", ".join(expressions) + "]"
