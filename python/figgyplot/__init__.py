"""NumPy-first plots; Rust owns rendering, picking and accepted settings."""
from .figure import Figure, Axes, Artist, RadialArtist, RenderWarning, figure, subplots, text_segments
from ._native import __version__, release_gpu
from ._document import Subplot
from ._features import Annotation
from . import styles
from .styles import StyleToken, StyleReport, StyleWarning
from ._style_runtime import use_style, style_context

__all__ = ["Subplot", "Annotation", "Figure", "Axes", "Artist", "RadialArtist", "RenderWarning", "figure", "subplots", "text_segments", "release_gpu", "styles", "StyleToken", "StyleReport", "StyleWarning"]
__all__ += ['use_style', 'style_context']

from ._artist_appearance import MarkerStyle, ErrorBarStyle, BinStyle, ColumnReference, GridReference
__all__ += ["MarkerStyle", "ErrorBarStyle", "BinStyle", "ColumnReference", "GridReference"]
from ._field_api import ContourLabel
__all__ += ["ContourLabel"]
from ._richtext import TextRun
__all__ += ["TextRun"]
