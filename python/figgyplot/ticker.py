"""Matplotlib-shaped regular tick locators; no Matplotlib runtime dependency."""

import math
import numpy as np


class MultipleLocator:
    def __init__(self, base=1.0, offset=0.0):
        self.base = float(base)
        self.offset = float(offset)
        if (
            not math.isfinite(self.base)
            or self.base <= 0
            or not math.isfinite(self.offset)
        ):
            raise ValueError("base must be positive and finite; offset must be finite")

    def tick_values(self, vmin, vmax):
        low, high = sorted((float(vmin), float(vmax)))
        first = math.floor((low - self.offset) / self.base) * self.base + self.offset
        return (
            first + np.arange(0, math.ceil((high - first) / self.base) + 2) * self.base
        )


class AutoMinorLocator:
    def __init__(self, n=None):
        self.n = 5 if n is None else int(n)
        if self.n < 1:
            raise ValueError("minor subdivisions must be positive")


class AutoLocator:
    """Use the renderer's automatic regular tick calculation for the view."""


class LogLocator:
    """Regular logarithmic major ticks. The renderer uses base-10 exponents."""

    def __init__(self, base=10.0):
        self.base = float(base)
        if not math.isfinite(self.base) or self.base <= 1:
            raise ValueError(
                "logarithmic locator base must be finite and greater than one"
            )


class SignificantFormatter:
    """Figgy extension: numeric labels with significant digits and notation.

    ``style`` is plain, scientific or power. This is deliberately distinct from
    Matplotlib's arbitrary string/callable formatters, which require explicit
    per-tick labels that the current renderer does not support.
    """

    def __init__(self, precision=3, style="plain"):
        self.precision = int(precision)
        self.style = style
        if not 1 <= self.precision <= 15 or style not in (
            "plain",
            "scientific",
            "power",
        ):
            raise ValueError(
                "precision must be 1..15; style plain, scientific or power"
            )
