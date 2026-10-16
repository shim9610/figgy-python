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
