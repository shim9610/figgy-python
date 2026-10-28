"""Renderer 0.18 constructors; all accepted visual state lives in SSOT."""
import copy
import json
import math
import uuid
import numpy as np
from . import _document
from . import _style_runtime


from ._color_scale import colorbar


from ._annotation_api import AnnotationEditing


class Annotation(AnnotationEditing):
    def __init__(self, figure, id):
        self.figure, self.id = figure, id

    def _find(self, state):
        from ._charts import family
        owner = state[family(state)] if family(state) else state['config']
        layer = owner.get('annotations', {'visible': True, 'items': []})
        for item in layer['items']:
            if item['id'] == self.id:
                return owner, layer, item
        raise ValueError(f'annotation {self.id!r} no longer exists')

    def set(self, *, visible=None, **geometry):
        from .figure import _merge
        state = self.figure.get_settings()
        _, _, item = self._find(state)
        if visible is not None:
            item['visible'] = bool(visible)
        if geometry:
            _merge(next(iter(item['kind'].values())), geometry)
        self.figure.apply_settings(state)
        return self

    def remove(self):
        with self.figure.batch_update():
            state = self.figure.get_settings()
            owner, layer, item = self._find(state)
            layer['items'].remove(item)
            arrow=getattr(self,'arrow_patch',None)
            if arrow:
                _,arrow_layer,arrow_item=arrow._find(state);arrow_layer['items'].remove(arrow_item)
            owner.get('decorations', {}).update(selected=None)
            self.figure.apply_settings(state)

    def select(self):
        from ._charts import family
        state = self.figure.get_settings()
        owner, layer, item = self._find(state)
        owner['active_layer'] = 'Annotations'
        if family(state):
            owner['decorations']['selected'] = {'Annotation': layer['items'].index(item)}
        self.figure.apply_settings(state)
        return self

    def get_visible(self):return self._find(self.figure.get_settings())[2]['visible']
    def set_visible(self,value):
        with self.figure.batch_update():
            self.set(visible=value)
            arrow=getattr(self,'arrow_patch',None)
            if arrow:arrow.set(visible=value)
    def get_gid(self):return self.id
    def get_text(self):
        from .figure import _text
        body=next(iter(self._find(self.figure.get_settings())[2]['kind'].values()))
        rich=body.get('label',body.get('text'))
        return _text(rich) if rich else ''
    def _set_text_property(self,key,value):
        state=self.figure.get_settings();body=next(iter(self._find(state)[2]['kind'].values()))
        rich=body.get('label',body.get('text'))
        if rich is None:raise AttributeError('this annotation has no text')
        rich[key]=value;self.figure.apply_settings(state)
    def set_text(self,value):
        from .figure import _segments
        self._set_text_property('segments',_segments(value, dpi=self.figure.dpi))
    def set_fontsize(self,value):
        from ._validation import number as _number
        self._set_text_property('font_size',_number(value,'fontsize',positive=True)*self.figure.dpi/72)
    def get_fontsize(self):
        return self._rich_text()['font_size']*72/self.figure.dpi
    def set_fontfamily(self,value):self._set_text_property('font',self.figure._check_font(value))
    def set_color(self,value):
        from .figure import _color
        self._set_text_property('color',_color(value))
    def get_position(self):
        body=next(iter(self._find(self.figure.get_settings())[2]['kind'].values()))
        if 'anchor' not in body:raise AttributeError('this annotation has no text position')
        kind,point=next(iter(body['anchor'].items()))
        return point['x'],1-point['y'] if kind=='Ratio' and getattr(self,'_axes_fraction',False) else point['y']
    def set_position(self,xy):
        from ._validation import number as _number
        x,y=map(lambda v:_number(v,'position'),xy)
        with self.figure.batch_update():
            state=self.figure.get_settings();body=next(iter(self._find(state)[2]['kind'].values()))
            kind=next(iter(body['anchor']))
            anchor={kind:dict(x=x,y=1-y if kind=='Ratio' and getattr(self,'_axes_fraction',False) else y)}
            body['anchor']=anchor
            arrow=getattr(self,'arrow_patch',None)
            if arrow:next(iter(arrow._find(state)[2]['kind'].values()))['from']=copy.deepcopy(anchor)
            self.figure.apply_settings(state)


class FeatureMethods:
    @_style_runtime.styled
    def step(self, x, y=None, *, where='pre', **kwargs):
        modes = dict(pre='StepPre', post='StepPost', mid='StepMid')
        if where not in modes:
            raise ValueError('where must be pre, post or mid')
        return self.plot(x, y, interpolation=modes[where], **kwargs)

    @_style_runtime.styled
    def fill_between(self, x, y1, y2=0, *, color=None, alpha=0.3, label=None, id=None,
                     interpolation='Linear'):
        """Fill to a baseline or another index-aligned line sharing the X column."""
        from .figure import _array, _color, _COLORS
        x, upper = _array(x), _array(y1)
        if x.size != upper.size:
            raise ValueError('x and y1 must have equal lengths')
        if not math.isfinite(float(alpha)) or not 0 <= alpha <= 1:
            raise ValueError('alpha must be in 0..1')
        rgba = _color(color or _COLORS[self.figure._next_series % len(_COLORS)])
        fill_color = dict(rgba, a=rgba['a']*alpha)
        sid = id or f'series_{self.figure._next_series}'
        line = dict(line_color=rgba, line_width=0., line_style='Solid', interpolation=interpolation,
                    fill_color=fill_color)
        if np.isscalar(y2):
            line['fill'] = {'ToBaseline': float(y2)}
            return self._add(x, upper, {'Line': {'line': line}}, label, sid)
        lower = _array(y2)
        if lower.size != x.size:
            raise ValueError('y2 must match x')
        # Introduce both lines in one native transaction. Their data column is
        # shared by reference, with no resampling or persistent CPU array copy.
        return self._add_fill_pair(x, lower, upper, line, label, sid)

    @_style_runtime.styled
    def quiver(self, x, y, u, v, *, values=None, cmap='viridis', vmin=None, vmax=None,
               scale=1., units='pixels', pivot='tail', color='black', width=1.,
               head_length=6., head_width=4., min_length=0., label=None, id=None):
        from .figure import _array, _color
        x, y, u, v = _array(x), _array(y), np.asarray(u), np.asarray(v)
        if u.shape != v.shape or u.ndim not in (1, 2):
            raise ValueError('u and v must have identical point-vector or grid shapes')
        if units not in ('pixels', 'data') or pivot not in ('tail', 'middle', 'tip'):
            raise ValueError('unsupported vector units or pivot')
        if not math.isfinite(float(scale)) or scale == 0:
            raise ValueError('vector scale must be finite and nonzero')
        if any(not math.isfinite(float(n)) or n < 0 for n in (width, head_length, head_width, min_length)):
            raise ValueError('vector sizes must be nonnegative and finite')
        sid = id or f'series_{self.figure._next_series}'
        columns = []
        def matrix(name, values):
            names = [f'{sid}/{name}/{i}' for i in range(values.shape[0])]
            columns.extend((n, _array(row)) for n, row in zip(names, values))
            return dict(columns=names, orientation='ColumnsAreY', grid_layout='Centers')
        if u.ndim == 1:
            if not x.size == y.size == u.size:
                raise ValueError('point vectors require equal x/y/u/v lengths')
            components = {'Points': dict(u=f'{sid}/u', v=f'{sid}/v')}
            columns.extend([(f'{sid}/u', _array(u)), (f'{sid}/v', _array(v))])
        else:
            if u.shape != (y.size, x.size):
                raise ValueError('grid vectors require u/v shape (len(y), len(x))')
            components = {'Grid': dict(u=matrix('u', u), v=matrix('v', v))}
        px = self.figure.dpi/72
        style = dict(color=_color(color), width_px=float(width)*px,
            scale={'Data': dict(factor=float(scale))} if units == 'data' else {'Pixels': dict(px_per_unit=float(scale))},
            pivot=pivot.title(), head_length_px=float(head_length)*px,
            head_width_px=float(head_width)*px, min_length_px=float(min_length)*px)
        cfg = copy.deepcopy(self._config(self.figure.get_settings()))
        if values is not None:
            values = np.asarray(values)
            if values.shape != u.shape:
                raise ValueError('vector color values must match component shape')
            if u.ndim == 1:
                columns.append((f'{sid}/color', _array(values)))
                style['color_map'] = {'Column': f'{sid}/color'}
            else:
                style['color_map'] = {'Grid': matrix('color', values)}
            colorbar(cfg, values, cmap, vmin, vmax)
        return self._add(x, y, {'Vector': dict(components=components, style=style)}, label, sid,
                         extra_columns=columns, config=cfg)

    @_style_runtime.styled
    def radar(self, categories, values, *, labels=None, colors=None, **properties):
        from .figure import _color, _COLORS
        categories = list(categories)
        values = np.asarray(values, dtype=float)
        if values.ndim == 1:
            values = values[None, :]
        if values.ndim != 2 or values.shape[1] != len(categories) or not np.isfinite(values).all():
            raise ValueError('radar values must be a finite series-by-category matrix')
        labels = list(labels) if labels is not None else [f'Series {i+1}' for i in range(len(values))]
        colors = list(colors) if colors is not None else [_COLORS[i % len(_COLORS)] for i in range(len(values))]
        if len(labels) != len(values) or len(colors) != len(values):
            raise ValueError('radar labels/colors must match series count')
        cats = [dict(id=f'category_{i}', label=str(name)) for i, name in enumerate(categories)]
        series = [dict(id=f'series_{i}', label=str(label), values=row.tolist(), color=_color(color), style=None)
                  for i, (row, label, color) in enumerate(zip(values, labels, colors))]
        return self._bounded('radar', cats, series, **properties)

    @_style_runtime.styled
    def _add_annotation(self, kind, *, id=None, **properties):
        """Add a document annotation using upstream geometry and logical pixels.

        Ratio anchors use the parent plot rectangle. Subplot-local annotation
        spaces are not supported by renderer 0.18 and are rejected explicitly.
        """
        from ._charts import family
        state = self.figure.get_settings()
        if self.overlay_id or _document.panel_index(state, self.subplot_id) != 0:
            raise ValueError('renderer 0.18 annotations belong to the parent panel only')
        owner = state[family(state)] if family(state) else state['config']
        if kind not in ('ReferenceLine', 'Span', 'Text', 'Arrow'):
            raise ValueError('unsupported annotation kind')
        if 'from_' in properties:
            properties['from'] = properties.pop('from_')
        if family(state) in ('radial', 'radar') and (kind in ('ReferenceLine', 'Span') or any(
            'Data' in properties.get(key, {}) for key in ('anchor', 'from', 'to'))):
            raise ValueError('pie/donut and radar annotations require ratio anchors')
        if owner.get('polar') is not None and (kind in ('ReferenceLine', 'Span') or any(
            'Data' in properties.get(key, {}) for key in ('anchor', 'from', 'to'))):
            raise ValueError('polar annotations require ratio anchors')
        layer = owner.setdefault('annotations', dict(visible=True, items=[]))
        annotation_id = _document.identifier(id or 'annotation/'+str(uuid.uuid4()))
        if any(item['id'] == annotation_id for item in layer['items']):
            raise ValueError('duplicate annotation ID')
        layer['items'].append(dict(id=annotation_id, visible=True, kind={kind: properties}))
        layer['items'][-1]=_style_runtime.annotation(self.figure,state,layer['items'][-1])
        self.figure.apply_settings(state)
        return Annotation(self.figure, annotation_id)

    @_style_runtime.styled
    def annotate(self, text, xy=None, xytext=None, xycoords='data', textcoords=None,
                 arrowprops=None, *, id=None, **kwargs):
        """Annotate a point with optional text and a straight arrow.

        Coordinates support data and axes fraction; offset points require a
        renderer transform and are rejected. Curved arrows are unsupported.
        """
        # The explicit renderer constructor remains available for old callers.
        if xy is None and text in ('ReferenceLine','Span','Text','Arrow'):
            return self._add_annotation(text,id=id,**kwargs)
        if xy is None:raise TypeError('annotate() requires xy')
        textcoords=xycoords if textcoords is None else textcoords
        destination=self._annotation_anchor(xy,xycoords)
        position=xy if xytext is None else xytext
        origin=self._annotation_anchor(position,textcoords)
        props=dict(arrowprops or {})
        allowed={'arrowstyle','color','linewidth','lw','linestyle','ls','head_length','head_width'}
        if set(props)-allowed:raise NotImplementedError('unsupported arrow properties: '+', '.join(sorted(set(props)-allowed)))
        if props.get('arrowstyle','->')!='->':raise NotImplementedError('renderer supports straight -> arrows only')
        from .figure import _color,_LINES
        with self.figure.batch_update():
            note=self.text(*position,text,transform=textcoords,id=id,**kwargs)
            if arrowprops is not None:
                unit=self.figure.dpi/72
                note.arrow_patch=self._add_annotation('Arrow',id=note.id+'/arrow',from_=origin,to=destination,text=None,
                    style=dict(line=dict(color=_color(props.get('color','black')),
                        width=float(props.get('linewidth',props.get('lw',1)))*unit,
                        style=_LINES.get(props.get('linestyle',props.get('ls','-')),props.get('linestyle','-'))),
                        head_length=float(props.get('head_length',8))*unit,head_width=float(props.get('head_width',6))*unit))
        return note

    def _annotation_anchor(self,xy,coords):
        from ._matplotlib import Transform
        from ._validation import number as _number
        x,y=(_number(v,'annotation coordinate') for v in xy)
        if isinstance(coords,Transform):
            if coords.axes is not self:raise ValueError('transform belongs to another Axes')
            coords=coords.kind
        if coords=='data':return {'Data':dict(x=x,y=y)}
        if coords=='axes fraction':return {'Ratio':dict(x=x,y=1-y)}
        raise NotImplementedError('annotation coordinates support data and axes fraction')

    @_style_runtime.styled
    def axhline(self, y=0, *, color='black', linewidth=1., id=None):
        return self._reference_line('Y', y, color, linewidth, id)

    @_style_runtime.styled
    def axvline(self, x=0, *, color='black', linewidth=1., id=None):
        return self._reference_line('X', x, color, linewidth, id)

    def _reference_line(self, axis, value, color, width, id):
        from .figure import _color
        return self._add_annotation('ReferenceLine', id=id, axis=axis, value=float(value), label=None,
            style=dict(color=_color(color), width=float(width)*self.figure.dpi/72, style='Solid'))

    @_style_runtime.styled
    def text(self, x, y, text, *, transform=None, coords='data', fontsize=11, color='black',
             fontfamily=None, fontweight='normal', fontstyle='normal', id=None):
        from .figure import _color, _segments
        if coords not in ('data', 'ratio'):
            raise ValueError('coords must be data or ratio')
        from ._matplotlib import Transform
        from ._validation import number as _number
        if fontweight not in ('normal','bold',400,700) or fontstyle not in ('normal','italic'):
            raise NotImplementedError('supported text styles are normal/bold and normal/italic')
        rich = copy.deepcopy(self.figure._default_config['legend']['content'])
        rich.update(segments=_segments(text, dpi=self.figure.dpi), font_size=_number(fontsize,'fontsize',positive=True)*self.figure.dpi/72, color=_color(color))
        if fontfamily is not None:rich['font']=self.figure._check_font(fontfamily)
        for segment in rich['segments']:
            if fontweight in ('bold',700):segment['bold']=True
            if fontstyle=='italic':segment['italic']=True
        anchor=self._annotation_anchor((x,y),transform or 'data') if transform is not None or coords=='data' else {'Ratio':dict(x=_number(x,'x'),y=_number(y,'y'))}
        note=self._add_annotation('Text', id=id, anchor=anchor,text=rich, box_style=None)
        note._axes_fraction=transform=='axes fraction' or isinstance(transform,Transform) and transform.kind=='axes fraction'
        return note

    @_style_runtime.styled
    def axhspan(self, ymin, ymax, *, color='gray', alpha=0.25, id=None):
        return self._span('Y', ymin, ymax, color, alpha, id)

    @_style_runtime.styled
    def axvspan(self, xmin, xmax, *, color='gray', alpha=0.25, id=None):
        return self._span('X', xmin, xmax, color, alpha, id)

    def _span(self, axis, low, high, color, alpha, id):
        from .figure import _color
        if not math.isfinite(float(alpha)) or not 0 <= alpha <= 1:
            raise ValueError('alpha must be in 0..1')
        rgba = _color(color)
        rgba['a'] *= float(alpha)
        return self._add_annotation('Span', id=id, axis=axis, from_=float(low), to=float(high), fill=rgba)

    @_style_runtime.styled
    def arrow(self, x, y, dx, dy, *, coords='data', color='black', linewidth=1.,
              head_length=8., head_width=6., id=None):
        from .figure import _color
        if coords not in ('data', 'ratio'):
            raise ValueError('coords must be data or ratio')
        unit = self.figure.dpi/72
        return self._add_annotation('Arrow', id=id, from_={coords.title(): dict(x=float(x), y=float(y))},
            to={coords.title(): dict(x=float(x+dx), y=float(y+dy))}, text=None,
            style=dict(line=dict(color=_color(color), width=float(linewidth)*unit, style='Solid'),
                       head_length=float(head_length)*unit, head_width=float(head_width)*unit))
