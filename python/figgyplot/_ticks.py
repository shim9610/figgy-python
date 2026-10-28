"""One tick-option translator for plot axes, overlays and colorbars.

Callers supply detached SSOT nodes and commit them once. This module neither
constructs Figures nor clones documents; grid-less axes reject grid options.
"""

import copy
import math

from ._validation import number as _number

_ALLOWED = {
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


def _prepare_options(fig, options):
    """Validate/convert once per call, regardless of the number of axes."""
    from .figure import _color, _LINES

    result = dict(options)
    unit = fig.dpi / 72
    for name, value in options.items():
        if name in ("color", "colors", "labelcolor", "grid_color"):
            result[name] = _color(value)
        elif name in ("length", "width", "grid_linewidth", "labelsize"):
            number = _number(value, name, positive=name == "labelsize")
            if number < 0:
                raise ValueError(name + " must be nonnegative")
            result[name] = number * unit
        elif name == "grid_alpha":
            result[name] = _number(value, name)
        elif name == "grid_linestyle":
            result[name] = _LINES.get(value, value)
        elif name == "labelfontfamily":
            result[name] = fig._check_font(value)
        elif name == "direction":
            if value not in ("in", "out", "inout"):
                raise ValueError("direction must be in, out or inout")
            result[name] = {"in": "Inside", "out": "Outside", "inout": "Both"}[value]
        elif name == "pad":
            raise NotImplementedError(
                "independent tick padding is not supported by this renderer"
            )
    return result


def apply_tick_params(
    fig, targets, *, grid=None, axis="both", which="major", reset=False, **kwargs
):
    if axis not in ("x", "y", "both") or which not in ("major", "minor", "both"):
        raise ValueError("invalid axis or which")
    if set(kwargs) - _ALLOWED:
        raise ValueError(
            "unsupported tick parameters: " + ", ".join(sorted(set(kwargs) - _ALLOWED))
        )
    if grid is None and any(name.startswith("grid_") for name in kwargs):
        raise NotImplementedError("colorbar axes have no grid to style")
    kwargs = _prepare_options(fig, kwargs)
    for side, node, defaults in targets:
        label = node["label_style"]
        if reset:
            base = defaults
            for field in ("tick", "major_tick_length", "minor_tick_length"):
                node[field] = copy.deepcopy(base[field])
            node["label_style"] = label = copy.deepcopy(base["label_style"])
        for name, value in kwargs.items():
            if name == "direction":
                node["tick"] = value
            elif name == "length":
                if which in ("major", "both"):
                    node["major_tick_length"] = value
                if which in ("minor", "both"):
                    node["minor_tick_length"] = value
            elif name in ("color", "colors"):
                color = value
                if node["line_visible"] and color != node["line_color"]:
                    raise NotImplementedError(
                        "renderer shares tick and spine colors; set spine color explicitly first"
                    )
                node["line_color"] = dict(color)
            elif name == "labelcolor":
                label["color"] = dict(value)
            elif name == "width":
                width = value
                if node["line_visible"] and not math.isclose(
                    width, node["line_width"], rel_tol=1e-6
                ):
                    raise NotImplementedError(
                        "renderer shares tick and spine widths; set spine linewidth explicitly first"
                    )
                node["line_width"] = width
            elif name == "labelsize":
                label["font_size"] = value
            elif name == "labelfontfamily":
                label["label_font"] = value
            elif name == "label" + side:
                label["label_visible"] = bool(value)
                if value:
                    label["visible"] = True
        if side in kwargs:
            if not kwargs[side]:
                node["tick"] = "None"
            elif node["tick"] == "None":
                node["tick"] = defaults["tick"]
        if "colors" in kwargs:
            label["color"] = dict(kwargs["colors"])
    if grid is None:
        return
    for dimension in ("x", "y"):
        if axis not in (dimension, "both"):
            continue
        for kind in ("major", "minor"):
            if which not in (kind, "both"):
                continue
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
                    grid[prefix + "_color"] = dict(value)
                elif field == "alpha":
                    grid[prefix + "_color"]["a"] = value
                elif field == "width":
                    grid[prefix + "_width"] = value
                else:
                    grid[prefix + "_style"] = value
