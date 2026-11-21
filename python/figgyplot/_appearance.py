"""Private translations for public appearance controls, with point-based lengths."""

import copy


# Public names are independent of serialized containers and pixel suffixes.
_COMMON = {
    "material": ("material", "material"),
    "texture_strength": ("texture_strength", "number"),
    "texture_scale": ("texture_scale", "number"),
    "gloss": ("gloss", "number"),
    "emphasis_brightness": ("emphasis_brightness", "number"),
}
_BOUNDED = {
    "categorical": dict(
        _COMMON,
        corner_radius=("corner_radius", "length"),
        outline=("outline", "bool"),
        linewidth=("outline_width", "length"),
        edgecolor=("outline_color", "color"),
    ),
    "boxplot": dict(
        _COMMON,
        corner_radius=("corner_radius", "length"),
        outline=("outline", "bool"),
        linewidth=("outline_width", "length"),
        edgecolor=("outline_color", "color"),
        median_width=("median_width", "length"),
        median_color=("median_color", "color"),
        whisker_width=("whisker_width", "length"),
        whisker_color=("whisker_color", "color"),
        caps=("caps", "bool"),
        cap_ratio=("cap_ratio", "number"),
        notch=("notched", "bool"),
        notch_depth=("notch_depth", "number"),
        showmeans=("show_mean", "bool"),
        mean_size=("mean_size", "length"),
        mean_color=("mean_color", "color"),
        showfliers=("show_outliers", "bool"),
        fliersize=("outlier_size", "length"),
        fliercolor=("outlier_color", "color"),
        fliermarker=("outlier_shape", "shape"),
        flierfilled=("outlier_filled", "bool"),
    ),
    "radial": {
        **{k: v for k, v in _COMMON.items() if k != "emphasis_brightness"},
        "tilt": ("tilt_degrees", "number"),
        "depth": ("depth", "number"),
        "bevel": ("bevel", "number"),
        "gap": ("gap_degrees", "number"),
        "roughness": ("roughness", "number"),
        "light": ("light", "vector"),
        "shadow": ("shadow", "bool"),
        "inner_corner": ("inner_corner", "number"),
        "outer_corner": ("outer_corner", "number"),
        "rim": ("outline/rim", "bool"),
        "separators": ("outline/separators", "bool"),
        "emphasis": ("outline/emphasis", "bool"),
        "linewidth": ("outline/width", "length"),
        "edgecolor": ("outline/color", "color"),
        "hover_lift": ("hover_lift", "number"),
        "hover_brightness": ("hover_brightness", "number"),
        "texture_angle": ("texture_angle_degrees", "number"),
    },
    "radar": {
        "startangle": ("start_angle_degrees", "angle"),
        "clockwise": ("clockwise", "bool"),
        "grid_shape": ("grid_shape", "title"),
        "spokecolor": ("spoke_color", "color"),
        "ringcolor": ("ring_color", "color"),
        "linewidth": ("line_width_px", "length"),
        "fill_alpha": ("fill_opacity", "number"),
        "marker": ("marker", "shape"),
        "markersize": ("marker_size_px", "length"),
        "emphasis_brightness": ("emphasis_brightness", "number"),
    },
}
_SHAPES = {
    "o": "Circle",
    "s": "Square",
    "^": "Triangle",
    "D": "Diamond",
    "x": "Cross",
    "+": "Plus",
    "*": "Star",
}


def convert(value, kind, dpi, *, decode=False):
    from .figure import _color, _material
    from ._validation import number as _number

    if decode:
        if kind == "color":
            return tuple(value[k] for k in "rgba")
        if kind == "length":
            return value * 72 / dpi
        if kind == "angle":
            return -value
        if kind == "material":
            return {"BrushedMetal": "brushed_metal", "SatinMetal": "satin_metal"}.get(
                value, value.lower()
            )
        if kind == "shape":
            return {v: k for k, v in _SHAPES.items()}.get(value, value.lower())
        if kind == "title":
            return value.lower()
        return copy.deepcopy(value)
    if kind == "color":
        return _color(value)
    if kind == "material":
        return _material(value)
    if kind == "bool":
        if not isinstance(value, bool):
            raise TypeError("visibility and style switches require bool")
        return value
    if kind == "shape":
        return _SHAPES.get(value, str(value).title())
    if kind == "title":
        return str(value).title()
    if kind == "vector":
        values = [_number(v, "light direction") for v in value]
        if len(values) != 3:
            raise ValueError("light must contain three components")
        return values
    number = _number(value, "style value")
    if kind == "length":
        if number < 0:
            raise ValueError("style lengths must be nonnegative")
        return number * dpi / 72
    return -number if kind == "angle" else number


def style_values(kind, style, dpi):
    result = {}
    for name, (path, conversion) in _BOUNDED[kind].items():
        value = style
        for key in path.split("/"):
            value = value[key]
        result[name] = convert(value, conversion, dpi, decode=True)
    return result


def edit_style(kind, style, dpi, properties):
    unknown = set(properties) - _BOUNDED[kind].keys()
    if unknown:
        raise ValueError(
            "unsupported " + kind + " style options: " + ", ".join(sorted(unknown))
        )
    for name, value in properties.items():
        path, conversion = _BOUNDED[kind][name]
        keys = path.split("/")
        node = style
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = convert(value, conversion, dpi)
