"""Matplotlib marker symbols and full/none fill mapped to native shapes."""


def decode_marker(shape):
    from .figure import _MARKERS

    reverse = {value: key for key, value in _MARKERS.items()}
    if shape in reverse:
        return reverse[shape], None
    if shape + "Filled" in reverse:
        return reverse[shape + "Filled"], "none"
    raise ValueError("unknown native marker shape")


def encode_marker(marker, fillstyle="full"):
    from .figure import _MARKERS

    if fillstyle not in ("full", "none"):
        raise ValueError("fillstyle must be full or none")
    if marker not in _MARKERS:
        raise ValueError("unknown marker symbol")
    shape = _MARKERS[marker]
    if fillstyle == "none":
        return shape.removesuffix("Filled")
    return {"Cross": "CrossFilled", "Plus": "PlusFilled"}.get(shape, shape)
