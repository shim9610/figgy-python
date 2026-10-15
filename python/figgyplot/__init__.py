"""NumPy-first plots; Rust owns rendering, picking and accepted settings."""
from .figure import Figure, Axes, Artist, RadialArtist, RenderWarning, figure, subplots, text_segments
from ._native import __version__, release_gpu

__all__ = ["Figure", "Axes", "Artist", "RadialArtist", "RenderWarning", "figure", "subplots", "text_segments", "release_gpu"]
