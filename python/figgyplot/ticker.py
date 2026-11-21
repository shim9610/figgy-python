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

    Use ``style`` to select plain, scientific, power, degrees, radians or
    percent notation.
    """

    def __init__(self, precision=3, style="plain"):
        self.precision = int(precision)
        self.style = style
        if not 1 <= self.precision <= 15 or style not in (
            "plain",
            "scientific",
            "power",
            "degrees",
            "radians",
            "percent",
        ):
            raise ValueError(
                "precision must be 1..15 and style must be plain, scientific, "
                "power, degrees, radians or percent"
            )

    def _format(self):
        return dict(
            plain="Decimal",
            scientific="Scientific",
            power="Power",
            degrees="Degrees",
            radians="Radians",
            percent="Percent",
        )[self.style]


class AutoFormatter(SignificantFormatter):
    """Derive number formatting from the axis ticks and view range."""

    def __init__(
        self,
        precision=3,
        *,
        uniform_decimals=True,
        notation="power",
        exponent_low=-5,
        exponent_high=6,
    ):
        super().__init__(precision)
        if not isinstance(uniform_decimals, bool):
            raise TypeError("uniform_decimals must be bool")
        if notation not in ("power", "scientific", "engineering"):
            raise ValueError("notation must be power, scientific or engineering")
        if any(
            not isinstance(value, (int, np.integer)) or not -128 <= value <= 127
            for value in (exponent_low, exponent_high)
        ):
            raise ValueError("exponent limits must be signed 8-bit integers")
        self.uniform_decimals = uniform_decimals
        self.notation = notation
        self.exponent_low = int(exponent_low)
        self.exponent_high = int(exponent_high)

    def _format(self):
        return {
            "Auto": {
                "uniform_decimals": self.uniform_decimals,
                "notation": self.notation.title(),
                "exponent_low": self.exponent_low,
                "exponent_high": self.exponent_high,
            }
        }


class PlainFormatter(SignificantFormatter):
    """Format each number with optional fixed decimal places."""

    def __init__(self, *, decimals=None, trim_zeros=False, precision=3):
        super().__init__(precision)
        if decimals is not None and (
            not isinstance(decimals, (int, np.integer)) or not 0 <= decimals <= 255
        ):
            raise ValueError("decimals must be None or an integer from 0 to 255")
        if not isinstance(trim_zeros, bool):
            raise TypeError("trim_zeros must be bool")
        self.decimals = None if decimals is None else int(decimals)
        self.trim_zeros = trim_zeros

    def _format(self):
        return {"Plain": {"decimals": self.decimals, "trim_zeros": self.trim_zeros}}


class TimestampFormatter(SignificantFormatter):
    """Unix timestamp labels without changing source values or axis limits.

    Units are s/ms/us/ns. Timezone is a fixed UTC offset in minutes.
    Use step to fix the calendar period and period_labels to center labels.
    An origin with a prefix or labels gives relative or custom period labels.
    """

    def __init__(
        self,
        pattern=None,
        *,
        unit="s",
        timezone=0,
        fractional_digits=None,
        calendar=True,
        precision=3,
        step=None,
        week_start="monday",
        period_labels=False,
        origin=None,
        prefix=None,
        labels=None,
    ):
        super().__init__(precision)
        if unit not in ("s", "ms", "us", "ns"):
            raise ValueError("timestamp unit must be s, ms, us or ns")
        if (
            not isinstance(timezone, (int, np.integer))
            or not -(2**31) <= timezone < 2**31
        ):
            raise ValueError("timezone must be a signed integer UTC offset in minutes")
        if fractional_digits is not None and (
            not isinstance(fractional_digits, (int, np.integer))
            or not 0 <= fractional_digits <= 9
        ):
            raise ValueError("fractional_digits must be None or an integer from 0 to 9")
        if pattern is not None:
            if not isinstance(pattern, str):
                raise TypeError("timestamp pattern must be a string")
            import re

            if any(
                not token or token not in "YmbdHMSf%"
                for token in re.findall(r"%(.)?", pattern)
            ):
                raise ValueError(
                    "supported timestamp patterns are %Y %m %b %d %H %M %S %f and %%"
                )
        if not isinstance(calendar, bool):
            raise TypeError("calendar must be bool")
        self.pattern, self.unit, self.timezone = pattern, unit, int(timezone)
        self.fractional_digits, self.calendar = fractional_digits, bool(calendar)
        if step not in (None, "day", "week", "month", "quarter", "year"):
            raise ValueError("step must be day, week, month, quarter or year")
        if week_start not in (
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
        ):
            raise ValueError("week_start must name a weekday")
        if not isinstance(period_labels, bool):
            raise TypeError("period_labels must be bool")
        if step is None and (period_labels or origin is not None):
            raise ValueError("period labels and an origin require a calendar step")
        if origin is None and (prefix is not None or labels is not None):
            raise ValueError("relative and custom labels require an origin")
        if origin is not None:
            if pattern is not None or (prefix is not None and labels is not None):
                raise ValueError("choose a pattern, relative labels or custom labels")
            if not isinstance(origin, (int, np.integer)) or not -(2**63) <= origin < 2**63:
                raise ValueError("origin must be a signed 64-bit timestamp")
            origin = int(origin)
        if prefix is not None and not isinstance(prefix, str):
            raise TypeError("prefix must be a string")
        if isinstance(labels, (str, bytes)):
            raise TypeError("labels must be a sequence of strings")
        self.step, self.week_start = step, week_start
        self.period_labels, self.origin, self.prefix = period_labels, origin, prefix
        self.labels = None if labels is None else list(labels)
        if self.labels is not None and not all(isinstance(value, str) for value in self.labels):
            raise TypeError("labels must contain strings")

    def _format(self):
        result = {
            "Timestamp": dict(
                unit={
                    "s": "Seconds",
                    "ms": "Milliseconds",
                    "us": "Microseconds",
                    "ns": "Nanoseconds",
                }[self.unit],
                timezone="Utc"
                if self.timezone == 0
                else {"FixedOffsetMinutes": self.timezone},
                label="Auto" if self.pattern is None else {"Pattern": self.pattern},
                fractional="Auto"
                if self.fractional_digits is None
                else {"Fixed": self.fractional_digits},
                tick_policy="AutoCalendar" if self.calendar else "NumericSpacing",
            )
        }
        spec = result["Timestamp"]
        if self.step == "week":
            spec["step"] = {"Week": {"start": self.week_start.title()}}
        elif self.step is not None:
            spec["step"] = self.step.title()
        if self.period_labels:
            spec["period_labels"] = True
        if self.origin is not None:
            if self.labels is None:
                spec["label"] = {"Relative": {"origin": self.origin, "prefix": self.prefix or ""}}
            else:
                spec["label"] = {"Custom": {"origin": self.origin, "labels": self.labels}}
        return result
