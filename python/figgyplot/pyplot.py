"""A small stateful interface familiar to matplotlib.pyplot users."""
from .figure import Figure, subplots as _subplots

_current = None


def figure(*args, **kwargs):
    global _current
    _current = Figure(*args, **kwargs)
    return _current


def gcf():
    return _current if _current is not None else figure()


def gca():
    return gcf().axes[0]


def subplots(*args, **kwargs):
    global _current
    _current, ax = _subplots(*args, **kwargs)
    return _current, ax


def plot(*args, **kwargs): return gca().plot(*args, **kwargs)
def scatter(*args, **kwargs): return gca().scatter(*args, **kwargs)
def imshow(*args, **kwargs): return gca().imshow(*args, **kwargs)
def pie(*args, **kwargs): return gca().pie(*args, **kwargs)
def donut(*args, **kwargs): return gca().donut(*args, **kwargs)
def draw_style(*args, **kwargs): return gcf().set_draw_style(*args, **kwargs)
def bar(*args, **kwargs): return gca().bar(*args, **kwargs)
def barh(*args, **kwargs): return gca().barh(*args, **kwargs)
def boxplot(*args, **kwargs): return gca().boxplot(*args, **kwargs)
def bxp(*args, **kwargs): return gca().bxp(*args, **kwargs)
def errorbar(*args, **kwargs): return gca().errorbar(*args, **kwargs)
def hist(*args, **kwargs): return gca().hist(*args, **kwargs)
def stairs(*args, **kwargs): return gca().stairs(*args, **kwargs)
def contour(*args, **kwargs): return gca().contour(*args, **kwargs)
def contourf(*args, **kwargs): return gca().contourf(*args, **kwargs)
def title(*args, **kwargs): return gca().set_title(*args, **kwargs)
def xlabel(*args, **kwargs): return gca().set_xlabel(*args, **kwargs)
def ylabel(*args, **kwargs): return gca().set_ylabel(*args, **kwargs)
def xlim(*args, **kwargs): return gca().set_xlim(*args, **kwargs)
def ylim(*args, **kwargs): return gca().set_ylim(*args, **kwargs)
def xscale(*args, **kwargs): return gca().set_xscale(*args, **kwargs)
def yscale(*args, **kwargs): return gca().set_yscale(*args, **kwargs)
def legend(*args, **kwargs): return gca().legend(*args, **kwargs)
def grid(*args, **kwargs): return gca().grid(*args, **kwargs)
def savefig(*args, **kwargs): return gcf().savefig(*args, **kwargs)
def show(*args, **kwargs): return gcf().show(*args, **kwargs)


def close(fig=None):
    global _current
    obj = gcf() if fig is None else fig
    obj.close()
    if obj is _current:
        _current = None


def quiver(*args, **kwargs): return gca().quiver(*args, **kwargs)
def radar(*args, **kwargs): return gca().radar(*args, **kwargs)
def step(*args, **kwargs): return gca().step(*args, **kwargs)
def fill_between(*args, **kwargs): return gca().fill_between(*args, **kwargs)
def text(*args, **kwargs): return gca().text(*args, **kwargs)
def axhline(*args, **kwargs): return gca().axhline(*args, **kwargs)
def axvline(*args, **kwargs): return gca().axvline(*args, **kwargs)
def axhspan(*args, **kwargs): return gca().axhspan(*args, **kwargs)
def axvspan(*args, **kwargs): return gca().axvspan(*args, **kwargs)
def arrow(*args, **kwargs): return gca().arrow(*args, **kwargs)
def twinx(*args, **kwargs): return gca().twinx(*args, **kwargs)

def stem(*args, **kwargs): return gca().stem(*args, **kwargs)

def streamlines(*args, **kwargs): return gca().streamlines(*args, **kwargs)

def streamplot(*args, **kwargs): return gca().streamplot(*args, **kwargs)

def range_bars(*args, **kwargs): return gca().range_bars(*args, **kwargs)

def broken_barh(*args, **kwargs): return gca().broken_barh(*args, **kwargs)

def waterfall(*args, **kwargs): return gca().waterfall(*args, **kwargs)

def candlestick(*args, **kwargs): return gca().candlestick(*args, **kwargs)

def violinplot(*args, **kwargs): return gca().violinplot(*args, **kwargs)

def raincloud(*args, **kwargs): return gca().raincloud(*args, **kwargs)

def rose(*args, **kwargs): return gca().rose(*args, **kwargs)

def hexbin(*args, **kwargs): return gca().hexbin(*args, **kwargs)

def ternary(*args, **kwargs): return gca().ternary(*args, **kwargs)

def parallel_coordinates(*args, **kwargs): return gca().parallel_coordinates(*args, **kwargs)

def tripcolor(*args, **kwargs): return gca().tripcolor(*args, **kwargs)

def plot_surface(*args, **kwargs): return gca().plot_surface(*args, **kwargs)

def plot_trisurf(*args, **kwargs): return gca().plot_trisurf(*args, **kwargs)

def plot3D(*args, **kwargs): return gca().plot3D(*args, **kwargs)

def scatter3D(*args, **kwargs): return gca().scatter3D(*args, **kwargs)

def quiver3D(*args, **kwargs): return gca().quiver3D(*args, **kwargs)

def energy_levels(*args, **kwargs): return gca().energy_levels(*args, **kwargs)

def feynman(*args, **kwargs): return gca().feynman(*args, **kwargs)

def sunburst(*args, **kwargs): return gca().sunburst(*args, **kwargs)

def tight_layout(**kwargs): return gcf().tight_layout(**kwargs)
def theme(name="gallery"): return gcf().set_theme(name)

def twiny(*args, **kwargs): return gca().twiny(*args, **kwargs)

def tricontour(*args, **kwargs): return gca().tricontour(*args, **kwargs)
def tricontourf(*args, **kwargs): return gca().tricontourf(*args, **kwargs)
