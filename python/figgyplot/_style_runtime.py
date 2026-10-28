"""Execution-local style defaults and construction-time inheritance.

Only newly constructed objects are styled. Existing accepted edits never need
replaying, and resolved defaults enter the original constructor transaction.
"""
import copy
from contextlib import contextmanager
from contextvars import ContextVar
import functools
import inspect
import threading
import warnings

from . import styles

INHERIT=object()
_current=ContextVar('figgyplot_style_defaults',default=None)
_call=ContextVar('figgyplot_style_construction',default=None)


class _Session:
    def __init__(self):
        self.indices={};self.lock=threading.RLock()

    def index(self,key):
        with self.lock:
            if key not in self.indices:self.indices[key]=len(self.indices)
            return self.indices[key]


def _token(value):
    if isinstance(value,str):value=styles.preset(value)
    if not isinstance(value,styles.StyleToken):raise TypeError('style must be a preset name or StyleToken')
    value.validate()
    # Default declarations never replay wording or coordinate domains.
    return styles.StyleToken(appearance=value.appearance)


def capture(value=INHERIT):
    current=_current.get()
    if value is None:return None,None
    base=copy.deepcopy(current[0]) if current else None
    session=current[1] if current else _Session()
    if value is INHERIT:return base,session if base is not None else None
    local=_token(value)
    if base is None:return local,session
    styles._merge(base.appearance,local.appearance);base.validate()
    return base,session


def use_style(value):
    """Set defaults for subsequent Figures in this execution context only."""
    if value is None:_current.set(None)
    else:_current.set((_token(value),_Session()))


@contextmanager
def style_context(value):
    """Temporarily replace execution defaults; nesting and exceptions restore them."""
    token=None if value is None else _token(value)
    handle=_current.set(None if token is None else (token,_Session()))
    try:yield copy.deepcopy(token)
    finally:_current.reset(handle)


def styled(method):
    """Record actually supplied arguments, including positional/default-equal values."""
    signature=inspect.signature(method)
    accepts_key=method.__name__ not in ('annotate','text','arrow','axhline','axvline','axhspan','axvspan')
    @functools.wraps(method)
    def wrapped(self,*args,**kwargs):
        if not accepts_key and 'style_key' in kwargs:raise TypeError('style_key applies to data series, not annotations')
        key=kwargs.pop('style_key',None)
        fig=self.figure
        if key is not None and (not isinstance(key,str) or not key):raise ValueError('style_key must be a nonempty string')
        active=_call.get()
        if active is not None and active['figure'] is fig:
            return method(self,*args,**kwargs)
        with fig._lock:
            if fig._style_defaults is None:
                if key is not None:raise ValueError('style_key requires Figure or execution style defaults')
                return method(self,*args,**kwargs)
            bound=signature.bind(self,*args,**kwargs)
            explicit=dict(bound.arguments);explicit.pop('self',None)
            for parameter in signature.parameters.values():
                if parameter.kind is inspect.Parameter.VAR_KEYWORD:
                    explicit.update(explicit.pop(parameter.name,{}))
            call=dict(figure=fig,name=method.__name__,explicit=explicit,key=key,index=None,used=False)
            handle=_call.set(call)
            try:
                result=method(self,*args,**kwargs)
                if call['used'] and call['key'] not in fig._style_defaults.appearance.get('roles',{}):
                    fig._style_next_index+=1
                return result
            finally:_call.reset(handle)
    # Expose the additional style correspondence keyword to help()/inspect().
    params=list(signature.parameters.values())
    extra=inspect.Parameter('style_key',kind=inspect.Parameter.KEYWORD_ONLY,default=None)
    where=next((i for i,p in enumerate(params) if p.kind is inspect.Parameter.VAR_KEYWORD),len(params))
    if accepts_key:params.insert(where,extra)
    wrapped.__signature__=signature.replace(parameters=params)
    return wrapped


def _construction(fig):
    call=_call.get()
    if call is None or call['figure'] is not fig:
        return dict(name='',explicit={},key=None,index=fig._style_next_index)
    if call['index'] is None:
        a=fig._style_defaults.appearance;palette=a.get('palette',[])
        call['index']=(0 if call['key'] in a.get('roles',{}) else fig._style_session.index(call['key'])) if call['key'] is not None else fig._style_next_index
        capacity=len(palette)*max(1,len(a.get('line_cycle',[])))
        if capacity and call['index']>=capacity and call['key'] not in a.get('roles',{}):
            warnings.warn('style category encodings exhausted; supply explicit styles or split/group categories',styles.StyleWarning,stacklevel=4)
    return call


def _mark_used(fig):
    call=_call.get()
    if call is not None and call['figure'] is fig:call['used']=True


def containers(fig,state,panel_ids=(),overlays=(),initial=False):
    if fig._style_defaults is None:return state
    for pid,oid in overlays:
        from ._document import overlay_config
        patch=styles._units(fig._style_defaults.appearance.get('panel',{}).get('right_y',{}),fig.dpi/72)
        # Top/right labels suppressed in a base frame must become readable on
        # an explicitly requested secondary measurement axis.
        patch.get('label_style',{}).pop('label_visible',None)
        styles._merge(overlay_config(state,pid,oid)['y_axis'],patch)
        overlay_config(state,pid,oid)['y_axis']['label_style']['label_visible']=True
    # Grid geometry is resolved once from explicit/accepted/inherited options
    # in set_layout(). Styling new panels must not place only part of the grid
    # using a second set of layout defaults.
    token=fig._style_defaults
    if 'layout' in token.appearance:
        appearance=copy.deepcopy(token.appearance);appearance.pop('layout')
        token=styles.StyleToken(appearance)
    candidate=styles._resolve(fig,state,token)
    if initial:
        state['config']=candidate['config']
        if 'background' in candidate:state['background']=candidate['background']
        return state
    for pid in panel_ids:
        from ._document import panel_config
        original=panel_config(state,pid);original.clear();original.update(copy.deepcopy(panel_config(candidate,pid)))
    for pid,oid in overlays:
        from ._document import overlay_config
        original=overlay_config(state,pid,oid);original.clear();original.update(copy.deepcopy(overlay_config(candidate,pid,oid)))
    return state


def layout_options(fig,state,grid,row_weights,column_weights,gap):
    defaults=fig._style_defaults.appearance.get('layout',{}) if fig._style_defaults is not None else {}
    previous=state['identity'].get('layout') or {}
    result={}
    for key,value,count in [('row_weights',row_weights,len(grid)),
                            ('column_weights',column_weights,len(grid[0]))]:
        if value is None:
            value=next((v for v in (previous.get(key),defaults.get(key)) if v is not None and len(v)==count),[1]*count)
        result[key]=list(value)
    if gap is None:
        if 'gap' in previous:gap=previous['gap']
        elif 'gap' in defaults:gap=defaults['gap']*fig.dpi/72
        else:gap=12
    result['gap']=float(gap)
    return result


def _restore_explicit(target,original,supplied):
    """Protect supplied leaves without restoring unrelated constructor defaults."""
    for key,value in supplied.items():
        if key not in original:continue
        if isinstance(value,dict) and isinstance(original[key],dict) and isinstance(target.get(key),dict):
            _restore_explicit(target[key],original[key],value)
        else:target[key]=copy.deepcopy(original[key])


def _copy_path(target,original,path):
    a,b=target,original
    for key in path[:-1]:
        if not isinstance(a,dict) or not isinstance(b,dict) or key not in a or key not in b:return
        a,b=a[key],b[key]
    if isinstance(a,dict) and isinstance(b,dict) and path[-1] in b:a[path[-1]]=copy.deepcopy(b[path[-1]])


def _restore_series(body,original,call):
    e=call['explicit'];name=call['name']
    fields={
        'color':[('line','line_color'),('scatter','point_color'),('bar','fill_color'),('style','color'),('err_style','error_bar_color'),('line','fill_color'),('contour','line','line_color')],
        'linewidth':[('line','line_width'),('bar','border_width'),('style','width_px'),('contour','line','line_width')],
        'linestyle':[('line','line_style')], 'marker':[('scatter','point_shape')],
        'markersize':[('scatter','point_size')], 's':[('scatter','point_size')],
        'ecolor':[('err_style','error_bar_color')],
        'elinewidth':[('err_style','error_bar_width'),('err_style','cap_width')],
        'capsize':[('err_style','error_bar_cap_size')],
        'edgecolor':[('bar','border_color')], 'fill_color':[('line','fill_color')],
        'gap':[('bar','gap_px')], 'width':[('bar','width_ratio'),('style','width_px')],
        'pivot':[('style','pivot')], 'head_length':[('style','head_length_px')],
        'head_width':[('style','head_width_px')],
    }
    fmt=e.get('fmt',e.get('y') if isinstance(e.get('y'),str) else '') or ''
    protected={k for k,v in e.items() if v is not None}
    if any(c in fmt for c in 'bgrkw'):protected.add('color')
    if any(c in fmt for c in 'os^vD+x*'):protected.add('marker')
    if any(c in fmt for c in '-:'):protected.add('linestyle')
    for key in protected:
        for path in fields.get(key,[]):_copy_path(body,original,path)
    if name=='fill_between':
        # Both lines are fill geometry, not requested visible strokes.
        _copy_path(body,original,('line','line_width'))
        if 'alpha' in protected and 'fill_color' in body.get('line',{}):
            body['line']['fill_color']['a']=original['line']['fill_color']['a']
    if name=='contourf' and 'linewidth' not in e:
        _copy_path(body,original,('contour','line','line_width'))


def series(fig,document,spec,panel_id):
    if fig._style_defaults is None:return spec,document
    from ._document import panel_config
    call=_construction(fig);original=copy.deepcopy(spec)
    source=copy.deepcopy(document);source['series'].append(copy.deepcopy(spec))
    sid=spec['series_id'];a=styles._units(fig._style_defaults.appearance,fig.dpi/72)
    def finalize(candidate):
        styled_spec=next(s for s in candidate['series'] if s['series_id']==sid)
        body=next(iter(styled_spec['render_type'].values()));before=next(iter(original['render_type'].values()))
        styles._encode_series(body,a,call['index'],call['key'])
        if a.get('palette') and 'fill_color' in body.get('line',{}):
            color=copy.deepcopy(body['line']['line_color'])
            color['a']*=before['line']['fill_color']['a'];body['line']['fill_color']=color
        _restore_series(body,before,call)
    candidate=styles._resolve(fig,source,fig._style_defaults,finalize)
    result=next(s for s in candidate['series'] if s['series_id']==sid)
    cfg=panel_config(document,panel_id);old=panel_config(fig.get_settings(),panel_id)
    if cfg.get('colorbar'):
        if not old.get('colorbar'):
            bar=panel_config(candidate,panel_id)['colorbar']
            if call['explicit'].get('cmap') is not None:bar['colormap']=copy.deepcopy(cfg['colorbar']['colormap'])
            cfg['colorbar']=copy.deepcopy(bar)
        elif call['explicit'].get('cmap') is None:
            cfg['colorbar']['colormap']=copy.deepcopy(old['colorbar']['colormap'])
    return copy.deepcopy(result),document


def bounded(fig,state,kind):
    if fig._style_defaults is None:return state
    call=_construction(fig);original=copy.deepcopy(state[kind]);e=call['explicit']
    def finalize(candidate):
        chart=candidate[kind]
        if call['key'] is not None:
            items=chart.get('series',chart.get('slices',[]))
            if len(items)!=1:raise ValueError('style_key identifies one series; multi-series bounded charts require explicit colors')
            a=fig._style_defaults.appearance
            if a.get('palette'):items[0]['color']=copy.deepcopy(a['palette'][call['index']%len(a['palette'])])
            role=a.get('roles',{}).get(call['key'],{})
            for part,key in [('line','line_color'),('scatter','point_color'),('bar','fill_color')]:
                if key in role.get(part,{}):items[0]['color']=copy.deepcopy(role[part][key]);break
        # Public advanced chart properties and per-family style dictionaries
        # are explicit overrides, including values equal to old defaults.
        _restore_explicit(chart,original,{k:v for k,v in e.items() if k not in ('series','slices','categories')})
        if e.get('color') is not None or e.get('colors') is not None:
            for item,before in zip(chart.get('series',chart.get('slices',[])),original.get('series',original.get('slices',[]))):item['color']=copy.deepcopy(before['color'])
        if call['name'] in ('pie','donut'):
            for key in ('material','tilt','depth'):
                field={'material':'material','tilt':'tilt_degrees','depth':'depth'}[key]
                if key in e:chart['style'][field]=copy.deepcopy(original['style'][field])
            _restore_explicit(chart['style'],original['style'],e)
    candidate=styles._resolve(fig,state,fig._style_defaults,finalize)
    state[kind]=candidate[kind]
    palette=fig._style_defaults.appearance.get('palette',[])
    items=state[kind].get('series',state[kind].get('slices',[]))
    if palette and len(items)>len(palette) and e.get('colors') is None and e.get('color') is None:
        warnings.warn('bounded palette exhausted; supply explicit colors or group series/slices',styles.StyleWarning,stacklevel=4)
    _mark_used(fig)
    return state


def annotation(fig,state,item):
    if fig._style_defaults is None:return item
    from ._charts import family
    kind=family(state);call=_construction(fig);original=copy.deepcopy(item)
    def finalize(candidate):
        owner=candidate[kind] if kind else candidate['config']
        body=next(v for v in owner['annotations']['items'] if v['id']==item['id'])['kind']
        tag=next(iter(body));body=body[tag];before=original['kind'][tag];e=call['explicit']
        if call['name']=='annotate':
            for key in e:
                if key in before:body[key]=copy.deepcopy(before[key])
        else:
            if 'fontsize' in e and isinstance(body.get('text'),dict):body['text']['font_size']=before['text']['font_size']
            if e.get('color') is not None:
                for path in [('text','color'),('style','color'),('style','line','color'),('fill',)]:_copy_path(body,before,path)
            if 'linewidth' in e:
                for path in [('style','width'),('style','line','width')]:_copy_path(body,before,path)
            for key in ('head_length','head_width'):
                if key in e:_copy_path(body,before,('style',key))
            if 'alpha' in e:_copy_path(body,before,('fill','a'))
    candidate=styles._resolve(fig,state,fig._style_defaults,finalize)
    owner=candidate[kind] if kind else candidate['config']
    return copy.deepcopy(next(v for v in owner['annotations']['items'] if v['id']==item['id']))
