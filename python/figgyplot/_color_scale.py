"""Shared color-domain mutation for constructors, artists and scale handles."""

import json
import math

import numpy as np


def colorbar(config, values, cmap, vmin, vmax):
    finite = np.asarray(values)[np.isfinite(values)]
    if not finite.size:
        raise ValueError("mapped values need at least one finite value")
    low = float(finite.min()) if vmin is None else float(vmin)
    high = float(finite.max()) if vmax is None else float(vmax)
    if low == high:
        high = low + max(1.0, abs(low) * 0.01)
    _set_colorbar(config, cmap, low, high)


_COLOR_UNSET = object()


def fit_colorbar_title(config):
    """Fit an unpositioned label with renderer metrics; preserve manual offsets."""
    bar = config.get("colorbar")
    if not bar or not bar["visible"]:
        return
    title = bar["axis"]["title_option"]
    if not title["visible"] or title["offset_x"] or title["offset_y"]:
        return
    from ._native import fitted_colorbar_title_margin

    bar["axis"]["out_margin"] = fitted_colorbar_title_margin(json.dumps(config))


def update_color_scale(
    config, *, cmap=_COLOR_UNSET, vmin=None, vmax=None, reset_spacing=False
):
    """Apply one complete scale change and fit its label once.

    The caller owns a detached SSOT snapshot. Constructors reset spacing for
    their new data domain; edits retain the user's accepted spacing.
    """
    from .figure import _colormap
    from ._native import default_colorbar_json

    bar = config.get("colorbar")
    if bar is None:
        bar = json.loads(default_colorbar_json())
    axis = bar["axis"]
    low = axis["min"] if vmin is None else float(vmin)
    high = axis["max"] if vmax is None else float(vmax)
    if not math.isfinite(low) or not math.isfinite(high) or low >= high:
        raise ValueError("mapped value domain must be finite and increasing")
    if cmap is not _COLOR_UNSET:
        bar["colormap"] = _colormap(cmap)
    axis.update(min=low, max=high)
    if reset_spacing:
        axis["major_spacing"] = (high - low) / 5
    config["colorbar"] = bar
    # Palette changes do not change tick or title geometry.
    if vmin is not None or vmax is not None:
        fit_colorbar_title(config)


def _set_colorbar(config, cmap, low, high):
    """Initialize a domain while retaining accepted colorbar appearance."""
    update_color_scale(config, cmap=cmap, vmin=low, vmax=high, reset_spacing=True)
