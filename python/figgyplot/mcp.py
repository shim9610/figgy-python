"""Local MCP tools for figure construction, editing and renderer-backed export.

Run ``python -m figgyplot.mcp`` after installing ``figgyplot[mcp]``.
Source arrays are supplied as tool data; no arbitrary Python is evaluated.
"""

from __future__ import annotations
import inspect
import json
import uuid
from pathlib import Path
from typing import Optional

from .figure import Figure

CHART_METHODS = (
    "plot",
    "scatter",
    "errorbar",
    "hist",
    "stairs",
    "step",
    "fill_between",
    "bar",
    "barh",
    "boxplot",
    "bxp",
    "radar",
    "rose",
    "stem",
    "imshow",
    "contour",
    "contourf",
    "hexbin",
    "quiver",
    "streamlines",
    "streamplot",
    "range_bars",
    "broken_barh",
    "waterfall",
    "candlestick",
    "violinplot",
    "raincloud",
    "ternary",
    "parallel_coordinates",
    "tripcolor",
    "tricontour",
    "tricontourf",
    "plot_surface",
    "plot_trisurf",
    "plot3D",
    "scatter3D",
    "quiver3D",
    "pie",
    "donut",
    "sunburst",
    "energy_levels",
    "feynman",
)
_figures = {}


def _figure(id):
    try:
        return _figures[id]
    except KeyError:
        raise ValueError(f"unknown figure: {id}") from None


def capabilities():
    """Discover available chart signatures, themes, formats and input types."""
    from .figure import Axes

    return dict(
        charts={
            name: str(inspect.signature(getattr(Axes, name)))
            for name in CHART_METHODS
            if hasattr(Axes, name)
        },
        themes=list(Figure.theme_names()),
        formats=["png", "svg", "pdf"],
        dtypes=["float32", "float64"],
        gpu_value_bytes=8,
        dtype_note="float32 input and notebook transfer are preserved; the renderer stores two f32 lanes per scalar",
    )


def figure_create(
    figsize: Optional[list[float]] = None,
    dpi: float = 120,
    grid: Optional[list[list[str]]] = None,
    theme: Optional[str] = None,
):
    """Create a native figure; optional grid contains stable subplot IDs."""
    fig = Figure(figsize=figsize or (8, 5), dpi=dpi, grid=grid, backend="native")
    try:
        if theme is not None:
            fig.set_theme(theme)
    except Exception:
        fig.close()
        raise
    id = uuid.uuid4().hex
    _figures[id] = fig
    return dict(id=id, settings=fig.get_settings())


def _input(value):
    if isinstance(value, dict):
        if set(value) == {"dtype", "values"}:
            import numpy as np

            if value["dtype"] not in (
                "float32",
                "float64",
                "int16",
                "int32",
                "uint8",
                "uint16",
                "uint32",
            ):
                raise ValueError("unsupported numeric dtype")
            return np.asarray(value["values"], dtype=value["dtype"])
        return {key: _input(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_input(item) for item in value]
    return value


def chart_add(
    id: str,
    kind: str,
    args: Optional[list] = None,
    options: Optional[dict] = None,
    panel: Optional[str] = None,
):
    """Add a chart using Python arguments. Typed arrays use {"dtype":"float32","values":[...]} instead of a list."""
    if kind not in CHART_METHODS:
        raise ValueError("unsupported chart kind; inspect capabilities()")
    fig = _figure(id)
    ax = fig.subplots[panel].axes if panel is not None else fig.axes[0]
    method = getattr(ax, kind)
    args = [] if args is None else args
    options = {} if options is None else options
    inspect.signature(method).bind(*args, **options)
    method(*_input(args), **_input(options))
    return dict(id=id, settings=fig.get_settings())


def figure_get(id: str):
    """Read the accepted document, including layout, styles and source IDs."""
    return _figure(id).get_settings()


def figure_patch(id: str, config: Optional[dict] = None, series: Optional[dict] = None):
    """Patch renderer configuration or existing series appearance atomically."""
    fig = _figure(id)
    fig.configure(config=config, series=series)
    return fig.get_settings()


def figure_theme(id: str, name: str):
    """Apply a renderer theme to every chart kind in the document."""
    fig = _figure(id)
    fig.set_theme(name)
    return fig.get_settings()


def figure_layout(id: str, grid: Optional[list[list[str]]] = None):
    """Change panel placement if supplied, then fit text and decoration bands."""
    fig = _figure(id)
    if grid is not None:
        fig.set_layout(grid)
    fig.tight_layout()
    return fig.get_settings()


def figure_export(id: str, path: str, format: Optional[str] = None, scale: float = 1.0):
    """Export the complete document to a local PNG, SVG or PDF file."""
    fig = _figure(id)
    destination = Path(path).expanduser().resolve()
    fig.savefig(destination, format=format, scale=scale)
    return dict(
        path=str(destination),
        bytes=destination.stat().st_size,
        format=(format or destination.suffix.lstrip(".")).lower(),
    )


def figure_close(id: str):
    fig = _figure(id)
    fig.close()
    del _figures[id]
    return dict(id=id, closed=True)


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install figgyplot[mcp] to run the MCP server") from exc
    server = FastMCP("figgyplot")
    for tool in (
        capabilities,
        figure_create,
        chart_add,
        figure_get,
        figure_patch,
        figure_theme,
        figure_layout,
        figure_export,
        figure_close,
    ):
        server.tool()(tool)
    return server


def main():
    try:
        create_server().run(transport="stdio")
    finally:
        for fig in list(_figures.values()):
            fig.close()
        _figures.clear()


if __name__ == "__main__":
    main()
