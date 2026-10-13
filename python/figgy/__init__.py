"""NumPy-first plots; Rust owns rendering, picking and accepted settings."""
from .figure import Figure, Axes, Artist, figure, subplots, text_segments
from ._native import release_gpu

__version__ = "0.2.0"
__all__ = ["Figure", "Axes", "Artist", "figure", "subplots", "text_segments", "release_gpu"]
