"""NumPy-first plots; Rust owns rendering, picking and accepted settings."""
from .figure import Figure, Axes, Artist, RadialArtist, figure, subplots, text_segments
from ._native import release_gpu

__version__ = "0.2.1"
__all__ = ["Figure", "Axes", "Artist", "RadialArtist", "figure", "subplots", "text_segments", "release_gpu"]
