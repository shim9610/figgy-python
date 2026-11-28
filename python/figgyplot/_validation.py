"""Numeric public-argument validation, independent of plotting objects."""
import math


def number(value, name, *, positive=False):
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(
            f"{name} must be finite" + (" and positive" if positive else "")
        )
    return value


