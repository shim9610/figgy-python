"""Chart constructors: host-side statistics and upstream declarative models."""
import copy
import json
import math
import numpy as np


def family(settings):
    return next((k for k in ('radial', 'categorical', 'boxplot', 'radar') if settings.get(k) is not None), None)


class BoundedArtist:
    """A bounded chart's SSOT; patches preserve fields that are not supplied."""
    def __init__(self, figure, kind):
        self.figure, self.kind = figure, kind

    def set(self, **properties):
        self.figure.configure_bounded(self.kind, **properties)
        return self

    def set_style(self, **properties):
        return self.set(style=properties)

    def set_values(self, values, *, series=0):
        with self.figure._lock:
            state = self.figure.get_settings()
            chart = state[self.kind]
            if isinstance(series, str):
                series = next(i for i, s in enumerate(chart['series']) if s['id'] == series)
            values = list(values)
            if len(values) != len(chart['categories']):
                raise ValueError('values must match the existing categories')
            chart['series'][series]['values'] = values
            chart['selected'] = chart['hovered'] = None
            self.figure.apply_settings(state)
        return self


class ChartMethods:
    def _bounded(self, kind, categories, series, **properties):
        from .figure import _color, _text, _merge
        from ._native import default_bounded_json
        fig = self.figure
        if len(fig.subplots) != 1 or self.overlay_id or self._config(fig.get_settings()).get('polar'):
            raise ValueError('bounded charts require a separate single-panel Figure')
        chart = json.loads(default_bounded_json(kind))
        chart.update(categories=categories, series=series,
                     title=_text(fig.get_settings()['config']['chart_title']['text']),
                     font_size=11 * fig.dpi / 72)
        _merge(chart, properties)
        with fig._lock:
            fig._require_open()
            fig._native.set_bounded(kind, json.dumps(chart, allow_nan=False))
        fig._changed()
        return BoundedArtist(fig, kind)

    def bar(self, x, height, *, label=None, colors=None, color=None,
            mode='grouped', orientation='vertical', **properties):
        """Bounded categorical bars (up to 64 categories / 16 series / 512 bars).

        ``height`` is one value per category or a series-by-category matrix.
        ``None`` means missing; zero is a real value. Modes are grouped, stacked,
        percent_stacked. Renderer materials and decoration layout are SSOT fields.
        """
        from .figure import _color, _COLORS
        labels = list(x)
        values = np.asarray(height, dtype=object)
        if values.ndim == 1:
            values = values[None, :]
        if values.ndim != 2 or values.shape[1] != len(labels):
            raise ValueError('height must have one value per category, optionally for multiple series')
        if orientation not in ('vertical', 'horizontal') or mode not in ('grouped', 'stacked', 'percent_stacked'):
            raise ValueError('unsupported bar orientation or mode')
        n = values.shape[0]
        names = [str(label)] if isinstance(label, str) else list(label) if label is not None else [f'Series {i+1}' for i in range(n)]
        palette = list(colors) if colors is not None else [_COLORS[i % len(_COLORS)] if color is None else color for i in range(n)]
        if len(names) != n or len(palette) != n:
            raise ValueError('labels and colors must match the number of series')
        categories = [dict(id=f'category_{i}', label=str(v)) for i, v in enumerate(labels)]
        series = [dict(id=f'series_{i}', label=names[i], values=[None if v is None else float(v) for v in row],
                       color=_color(palette[i]), style=None) for i, row in enumerate(values)]
        return self._bounded('categorical', categories, series,
                             mode={'grouped': 'Grouped', 'stacked': 'Stacked', 'percent_stacked': 'PercentStacked'}[mode],
                             direction=orientation.title(), **properties)

    def barh(self, y, width, **kwargs):
        """Horizontal categorical bars; other arguments follow ``bar``."""
        return self.bar(y, width, orientation='horizontal', **kwargs)

    def bxp(self, stats, *, labels=None, color=None, orientation='vertical', **properties):
        """Plot precomputed boxes without recomputing statistics.

        Each dictionary supplies q1, median (or med), q3, whisker_low (whislo),
        whisker_high (whishi); optional mean, sample_count, median_ci, outliers
        (fliers). Renderer bounds: 128 outliers per box / 4096 per chart.
        """
        from .figure import _color, _COLORS
        stats = list(stats)
        if orientation not in ('vertical', 'horizontal'):
            raise ValueError('orientation must be vertical or horizontal')
        names = list(labels) if labels is not None else [s.get('label', f'Box {i+1}') for i, s in enumerate(stats)]
        if len(names) != len(stats):
            raise ValueError('labels must match the number of boxes')
        values = []
        for source in stats:
            s = dict(source)
            s.pop('label', None)
            for alias, key in [('med', 'median'), ('whislo', 'whisker_low'), ('whishi', 'whisker_high'), ('fliers', 'outliers')]:
                if alias in s:
                    if key in s:
                        raise ValueError(f'both {alias} and {key} were supplied')
                    s[key] = s.pop(alias)
            for key in ('q1', 'median', 'q3', 'whisker_low', 'whisker_high'):
                s[key] = float(s[key])
            for key in ('mean', 'sample_count', 'median_ci'):
                s.setdefault(key, None)
            s['outliers'] = [float(v) for v in s.get('outliers', [])]
            values.append(s)
        categories = [dict(id=f'category_{i}', label=str(v)) for i, v in enumerate(names)]
        series = [dict(id='series_0', label='Distribution', values=values, color=_color(_COLORS[0] if color is None else color), style=None)]
        return self._bounded('boxplot', categories, series, direction=orientation.title(), **properties)

    def boxplot(self, x, *, labels=None, whis=1.5, orientation='vertical', **properties):
        """Compute NumPy linear quartiles and actual IQR whiskers, then call bxp.

        A 1-D input is one box; a sequence of arrays is one box per array.
        No outlier is dropped to fit the renderer's bounded limits.
        """
        if not math.isfinite(float(whis)) or whis < 0:
            raise ValueError('whis must be finite and nonnegative')
        rows = list(x)
        if not rows:
            raise ValueError('boxplot needs samples')
        if np.isscalar(rows[0]):
            rows = [rows]
        stats = []
        for row in rows:
            a = np.asarray(row, dtype=float)
            if a.ndim != 1 or not a.size or not np.isfinite(a).all():
                raise ValueError('each box needs a nonempty finite one-dimensional sample')
            q1, median, q3 = np.percentile(a, [25, 50, 75])
            iqr = q3 - q1
            lower, upper = a[a >= q1-whis*iqr], a[a <= q3+whis*iqr]
            low, high = min(q1, lower.min()), max(q3, upper.max())
            stats.append(dict(q1=float(q1), median=float(median), q3=float(q3), whisker_low=float(low),
                              whisker_high=float(high), mean=float(a.mean()), sample_count=int(a.size),
                              outliers=a[(a < low) | (a > high)].tolist()))
        return self.bxp(stats, labels=labels, orientation=orientation, **properties)

    def errorbar(self, x, y, *, xerr=None, yerr=None, color=None, ecolor=None,
                 linewidth=1.5, elinewidth=1.0, capsize=3, marker='o', markersize=4,
                 linestyle='-', label=None, id=None):
        """Symmetric or asymmetric errors: scalar, (N,), or (2,N) magnitudes.

        ``linestyle=None`` draws points and errors without connecting lines.
        Widths, marker diameter and cap sizes use Python points.
        """
        from .figure import _array, _color, _COLORS, _MARKERS, _LINES
        x, y = _array(x), _array(y)
        if x.size != y.size or not x.size:
            raise ValueError('x and y must have the same nonzero length')
        if xerr is None and yerr is None:
            raise ValueError('supply xerr and/or yerr')
        if any(not math.isfinite(float(v)) or v < 0 for v in (linewidth, elinewidth, capsize, markersize)):
            raise ValueError('sizes must be finite and nonnegative')
        sid = id if id is not None else f'series_{self.figure._next_series}'
        columns, errors = [], {}
        for axis, data in [('x', xerr), ('y', yerr)]:
            if data is None:
                continue
            a = np.asarray(data)
            if a.ndim == 0:
                a = np.full(x.size, a, dtype=float)
            if a.shape not in [(x.size,), (2, x.size)] or not np.isfinite(a).all() or (a < 0).any():
                raise ValueError('errors must be finite nonnegative scalar, (N,), or (2,N)')
            if a.ndim == 1:
                name = f'{sid}/err_{axis}'
                columns.append((name, _array(a)))
                errors[f'err_{axis}'] = {'Symmetric': {'column': name}}
            else:
                names = [f'{sid}/err_{axis}/{i}' for i in range(2)]
                columns.extend((n, _array(row)) for n, row in zip(names, a))
                errors[f'err_{axis}'] = {'Asymmetric': dict(lower=names[0], upper=names[1])}
        color = _color(color if color is not None else _COLORS[self.figure._next_series % len(_COLORS)])
        px = self.figure.dpi / 72
        style = dict(scatter=dict(point_color=color, point_shape=_MARKERS.get(marker, marker), point_size=float(markersize)*px/2),
                     err_style=dict(error_bar_color=_color(ecolor) if ecolor is not None else color,
                                    error_bar_width=float(elinewidth)*px, error_bar_cap_size=float(capsize)*px, cap_width=float(elinewidth)*px), **errors)
        prefix = 'ScatterErrorbar'
        if linestyle not in (None, '', 'none'):
            style['line'] = dict(line_style=_LINES.get(linestyle, linestyle), line_color=color, line_width=float(linewidth)*px)
            prefix = 'LineScatterErrorbar'
        suffix = 'XY' if len(errors) == 2 else 'X' if xerr is not None else 'Y'
        return self._add(x, y, {prefix+suffix: style}, label, id, extra_columns=columns)

    def stairs(self, values, edges, *, orientation='vertical', color=None, edgecolor='black',
               linewidth=0.5, baseline=0, gap=1, width=1, label=None, id=None):
        """Render pre-binned histogram bars; one more edge than values."""
        from .figure import _array, _color, _COLORS
        counts, edges = _array(values), _array(edges)
        if edges.size != counts.size+1 or not counts.size or not np.isfinite(edges).all() or not np.isfinite(counts).all() or not (np.diff(edges)>0).all():
            raise ValueError('histogram requires finite values and strictly increasing N+1 edges')
        if orientation not in ('vertical', 'horizontal'):
            raise ValueError('orientation must be vertical or horizontal')
        if not all(math.isfinite(float(v)) for v in (linewidth, baseline, gap, width)) or linewidth < 0 or gap < 0 or not 0 < width <= 1:
            raise ValueError('invalid histogram style')
        style = {'Histogram': {'bar': dict(fill_color=_color(color if color is not None else _COLORS[self.figure._next_series % len(_COLORS)]),
                 border_color=_color(edgecolor), border_width=float(linewidth)*self.figure.dpi/72,
                 baseline=float(baseline), gap_px=float(gap), width_ratio=float(width), orientation=orientation.title())}}
        return self._add(edges if orientation=='vertical' else counts, counts if orientation=='vertical' else edges, style, label, id)

    def hist(self, x, bins=10, *, range=None, weights=None, density=False, **kwargs):
        """Bin one finite sample vector with NumPy; return counts, edges, artist."""
        from .figure import _array
        x = _array(x)
        if not x.size or not np.isfinite(x).all():
            raise ValueError('hist needs nonempty finite samples')
        weights = None if weights is None else _array(weights)
        if weights is not None and (weights.size != x.size or not np.isfinite(weights).all()):
            raise ValueError('weights must be finite and match samples')
        counts, edges = np.histogram(x, bins=bins, range=range, weights=weights, density=density)
        return counts, edges, self.stairs(counts, edges, **kwargs)

    def contour(self, *args, levels=7, color='black', linewidth=1, cmap='viridis',
                vmin=None, vmax=None, filled=False, id=None):
        """Contour(Z) or contour(X,Y,Z), with increasing 1-D sample coordinates.

        Explicit levels are SSOT values. An integer requests evenly spaced
        interior levels. ``filled=True`` adds upstream banded field rendering.
        """
        from .figure import _array, _color, _colormap
        from ._native import default_colorbar_json
        if len(args) == 1:
            z = np.asarray(args[0])
            if z.ndim != 2:
                raise ValueError('Z must be a matrix')
            x, y = np.arange(z.shape[1], dtype=float), np.arange(z.shape[0], dtype=float)
        elif len(args) == 3:
            x, y, z = _array(args[0]), _array(args[1]), np.asarray(args[2])
        else:
            raise TypeError('use contour(Z) or contour(X,Y,Z)')
        if z.ndim != 2 or min(z.shape) < 2 or z.shape != (y.size, x.size) or z.dtype.kind not in 'fiu':
            raise ValueError('Z must have shape (len(Y), len(X)), at least 2x2')
        if not np.isfinite(x).all() or not np.isfinite(y).all() or not (np.diff(x)>0).all() or not (np.diff(y)>0).all():
            raise ValueError('X and Y must be finite and strictly increasing')
        finite = z[np.isfinite(z)]
        if not finite.size:
            raise ValueError('Z has no finite values')
        low = float(finite.min()) if vmin is None else float(vmin)
        high = float(finite.max()) if vmax is None else float(vmax)
        if low == high:
            high = low+1
        if not math.isfinite(low) or not math.isfinite(high) or low >= high:
            raise ValueError('vmin and vmax must be finite and increasing')
        if isinstance(levels, (int, np.integer)) and not isinstance(levels, bool):
            if not 1 <= levels <= 1024:
                raise ValueError('levels must be 1..1024')
            levels = np.linspace(low, high, int(levels)+2)[1:-1]
        levels = _array(levels)
        if not 1 <= levels.size <= 1024 or not np.isfinite(levels).all() or not (np.diff(levels)>0).all():
            raise ValueError('levels must be finite, increasing and at most 1024')
        if not math.isfinite(float(linewidth)) or linewidth < 0:
            raise ValueError('linewidth must be finite and nonnegative')
        sid = id if id is not None else f'series_{self.figure._next_series}'
        columns = [(f'{sid}/z/{i}', _array(row)) for i, row in enumerate(z)]
        style = dict(matrix=dict(columns=[n for n, _ in columns], orientation='ColumnsAreY', grid_layout='Centers'),
                     contour=dict(levels=levels.tolist(), line=dict(line_style='Solid', line_color=_color(color), line_width=float(linewidth)*self.figure.dpi/72)))
        if filled:
            style['fill'] = dict(mode='Bands', shading='Interpolated', opacity=1.0)
        bar = json.loads(default_colorbar_json())
        bar['colormap'] = _colormap(cmap)
        bar['axis'].update(min=low, max=high, major_spacing=(high-low)/5)
        with self.figure._lock:
            config = self._config(self.figure.get_settings())
            config['colorbar'] = bar
            return self._add(x, y, {'HeatmapContour' if filled else 'Contour': style}, id=id,
                             extra_columns=columns, config=config, bounds=(float(x[0]), float(x[-1]), float(y[0]), float(y[-1])))

    def contourf(self, *args, **kwargs):
        """Banded field plus optional contours; default line width is zero."""
        kwargs.setdefault('linewidth', 0)
        return self.contour(*args, filled=True, **kwargs)
