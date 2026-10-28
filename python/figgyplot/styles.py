"""Portable, versioned appearance tokens; data and chart meaning remain owned by the Figure.

Lengths are points, not renderer pixels. ``scales`` and ``text`` are opt-in on
both extraction and application. See docs/STYLE_TOKENS.md for matching rules.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import warnings

from . import _document

def family(settings):
    # Keep the token compiler independent of the constructor/decorator module.
    return next((k for k in ('radial','categorical','boxplot','radar') if settings.get(k) is not None),None)


class StyleWarning(UserWarning):
    """Some requested appearance has no compatible target."""


@dataclass
class StyleReport:
    applied: tuple = ()
    skipped: tuple = ()


RGBA = dict.fromkeys(('r', 'g', 'b', 'a'), True)
RICH = dict(color=RGBA, font_size=True, font=True, align=True)
TITLE = dict(text=RICH, visible=True, offset_x=True, offset_y=True, top_margin=True)
LABEL = dict(visible=True, color=RGBA, font_size=True, label_visible=True,
             label_font=True, label_offset_x=True, label_offset_y=True,
             format=True, significant_digits=True)
AXIS = dict(label_style=LABEL, title_option=TITLE, tick=True, out_margin=True,
            line_offset=True, line_visible=True, line_color=RGBA, line_width=True,
            line_style=True, major_tick_length=True, minor_tick_length=True, minor_count=True)
GRID = {**{k:True for k in ('show_major_x','show_major_y','show_minor_x','show_minor_y')},
        **{p+'_'+k: RGBA if k=='color' else True
           for p in ('major_x','major_y','minor_x','minor_y') for k in ('color','width','style')}}
LEGEND = dict(visible=True, content=RICH, corner=True, offset_x=True, offset_y=True,
              padding=True, bg_color=RGBA, border_color=RGBA)
COLORBAR = dict(visible=True, side=True, thickness_px=True, gap_px=True,
                length_frac=True, align=True, offset_x=True, offset_y=True,
                colormap='json', nan_color=RGBA, border_color=RGBA, border_width=True, axis=AXIS)
LINE = dict(line_color=RGBA, line_width=True, line_style=True, fill_color=RGBA)
SCATTER = dict(point_color=RGBA, point_shape=True, point_size=True)
ERROR = dict(error_bar_color=RGBA, error_bar_width=True, error_bar_cap_size=True, cap_width=True)
BAR = dict(fill_color=RGBA, border_color=RGBA, border_width=True, gap_px=True, width_ratio=True)
VECTOR = dict(color=RGBA, width_px=True, pivot=True, head_length_px=True, head_width_px=True)
RENDER = dict(line=LINE, scatter=SCATTER, err_style=ERROR, bar=BAR,
              style=VECTOR, contour=dict(line=LINE),
              fill=dict(mode=True, shading=True, opacity=True))
OUTLINE = dict(rim=True, separators=True, emphasis=True, width=True, color=RGBA)
BOUNDED_STYLE = {
    'radial': dict(material=True, tilt_degrees=True, depth=True, bevel=True,
        gap_degrees=True, roughness=True, texture_strength=True, texture_scale=True,
        light='json', shadow=True, inner_corner=True, outer_corner=True, outline=OUTLINE,
        hover_lift=True, hover_brightness=True, gloss=True, texture_angle_degrees=True),
    'categorical': dict(material=True, corner_radius=True, outline=True, outline_width=True,
        outline_color=RGBA, texture_strength=True, texture_scale=True, gloss=True, emphasis_brightness=True),
    'boxplot': dict(material=True, corner_radius=True, outline=True, outline_width=True,
        outline_color=RGBA, median_width=True, median_color=RGBA, whisker_width=True,
        whisker_color=RGBA, caps=True, cap_ratio=True, notch_depth=True,
        mean_size=True, mean_color=RGBA, outlier_size=True, outlier_color=RGBA,
        outlier_shape=True, outlier_filled=True, texture_strength=True, texture_scale=True,
        gloss=True, emphasis_brightness=True),
    'radar': dict(grid_shape=True, spoke_color=RGBA, ring_color=RGBA, line_width_px=True,
        fill_opacity=True, marker=True, marker_size_px=True, emphasis_brightness=True),
}
BOUNDED = dict(font_family=True, font_size=True, text_color=RGBA, label_color=RGBA,
    background=RGBA, chart_title=TITLE, grid=True, legend=True, label_decimals=True,
    group_width=True, bar_gap=True, box_gap=True)
ANNOTATION = dict(Text=dict(text=RICH,box_style=dict(fill=RGBA,border_color=RGBA,border_width=True,padding=True)), Arrow=dict(text=RICH,
    style=dict(line=dict(color=RGBA,width=True,style=True),head_length=True,head_width=True)),
    ReferenceLine=dict(style=dict(color=RGBA,width=True,style=True),label=RICH), Span=dict(fill=RGBA))
PANEL = dict(chart_title=TITLE, grid=GRID, legend=LEGEND, colorbar=COLORBAR,
             draw_style=dict.fromkeys(('mode','amplitude_px','wavelength_px','seed',
                 'star_density','ribbon_width_px','ribbon_intensity','star_scale',
                 'star_brightness','spread_px','structure_scale','faint_bias','glow',
                 'nebula','dust','planet_rim','star_opacity','line_opacity'),True),
             polar=dict(inner_radius_fraction=True,radial_label_angle_degrees=True),
             **dict.fromkeys(('bottom_x','top_x','left_y','right_y'), AXIS))
SCALE_KEYS = ('scale','min','max','major_spacing','inverted')
LENGTHS = set(('font_size','title_size','label_size','legend_size','line_width','point_size','error_bar_width','error_bar_cap_size',
    'cap_width','border_width','gap_px','thickness_px','padding','offset_x','offset_y',
    'label_offset_x','label_offset_y','out_margin','line_offset','major_tick_length',
    'minor_tick_length','top_margin','width_px','head_length_px','head_width_px',
    'head_length','head_width','width','corner_radius','outline_width','median_width',
    'whisker_width','mean_size','outlier_size','line_width_px','marker_size_px','bar_gap','box_gap'))
LENGTHS.update(('gap','amplitude_px','wavelength_px','ribbon_width_px','spread_px'))
TYPO = dict(font=True, font_size=True, title_size=True, label_size=True,
            legend_size=True, title_scale=True, label_scale=True, legend_scale=True, color=RGBA)
SCALE_AXIS = dict.fromkeys((*SCALE_KEYS, 'tick_mode'), True)
TEXT_GROUPS = {'titles','axis_titles','legend_labels'}


def _project(value, schema):
    if not isinstance(value, dict):
        return {}
    return {k:copy.deepcopy(v) if rule is True or rule=='json' else _project(v,rule)
            for k,v in value.items() if (rule:=schema.get(k)) is not None and v is not None}


def _check(value, schema, path):
    if not isinstance(value,dict):
        raise ValueError(path+' must be a mapping')
    for key,v in value.items():
        if key not in schema:
            raise ValueError('unknown style field: '+path+'/'+key)
        rule=schema[key]
        if rule is True:
            if not isinstance(v,(str,bool,int,float)):
                raise ValueError(path+'/'+key+' must be a scalar')
        elif rule!='json':
            _check(v,rule,path+'/'+key)


def _normalize_colors(node):
    from .figure import _color
    if isinstance(node,dict):
        for key,value in node.items():
            if key=='palette':node[key]=[copy.deepcopy(c) if isinstance(c,dict) else _color(c) for c in value]
            elif (key in ('color','background','fill') or key.endswith('_color')) and isinstance(value,(str,list,tuple)):
                node[key]=_color(value)
            else:_normalize_colors(value)
    elif isinstance(node,list):
        for value in node:_normalize_colors(value)


def _units(value, multiplier):
    if isinstance(value,dict):
        return {k:(v*multiplier if k in LENGTHS and isinstance(v,(int,float)) and not isinstance(v,bool)
                   else _units(v,multiplier)) for k,v in value.items()}
    if isinstance(value,list):return [_units(v,multiplier) for v in value]
    return copy.deepcopy(value)


def _merge(target, patch):
    for k,v in patch.items():
        if isinstance(v,dict) and isinstance(target.get(k),dict):_merge(target[k],v)
        else:target[k]=copy.deepcopy(v)


def _panels(state):
    return [state['config']]+[v['config'] for v in state['config'].get('subplots',[])]


def _panel_patch(cfg, raw, kind, skipped):
    from .figure import _colormap
    patch=copy.deepcopy(raw)
    for key,message in [('colorbar','colorbar: target panel has no color scale'),
                        ('polar','polar appearance: target is Cartesian')]:
        if key in patch and not cfg.get(key):
            patch.pop(key);skipped.append(message)
    if kind and 'draw_style' in patch:
        patch.pop('draw_style');skipped.append('draw style: bounded charts use materials')
    if 'draw_style' in patch:cfg.pop('draw_style',None)
    if isinstance(patch.get('colorbar',{}).get('colormap'),str):
        patch['colorbar']['colormap']=_colormap(patch['colorbar']['colormap'])
    _merge(cfg,patch)


def _rich_text(node):
    return copy.deepcopy(node.get('segments',[]))


def _panel_text(cfg):
    return dict(titles=_rich_text(cfg['chart_title']['text']),
        axis_titles={key:_rich_text(cfg[key]['title_option']['text'])
                     for key in ('bottom_x','top_x','left_y','right_y')},
        colorbar_title=_rich_text(cfg['colorbar']['axis']['title_option']['text']) if cfg.get('colorbar') else None,
        overlays=[_rich_text(o['y_axis']['title_option']['text']) for o in cfg.get('overlays',[])])


@dataclass
class StyleToken:
    """One reusable token. Optional scale/text payloads are never implicitly applied."""
    appearance: dict = field(default_factory=dict)
    scales: dict = None
    text: dict = None
    version: int = 1

    def __post_init__(self):
        self.appearance=copy.deepcopy(self.appearance)
        self.scales=copy.deepcopy(self.scales)
        self.text=copy.deepcopy(self.text)
        self.validate()

    def validate(self):
        if type(self.version) is not int or self.version!=1:raise ValueError('unsupported style token version')
        a=self.appearance
        allowed={'typography','background','palette','colormap','panel','panels','series','series_defaults',
                 'roles','line_cycle','marker_cycle',
                 'bounded','bounded_items','annotations','layout'}
        if not isinstance(a,dict) or set(a)-allowed:raise ValueError('unknown appearance fields')
        _normalize_colors(a)
        for name,schema in [('typography',TYPO),('background',RGBA),('panel',PANEL),('series_defaults',RENDER)]:
            if name in a:_check(a[name],schema,name)
        for c in a.get('palette',[]):_check(c,RGBA,'palette')
        if not isinstance(a.get('roles',{}),dict):raise ValueError('roles must be a mapping')
        for name,style in a.get('roles',{}).items():
            if not isinstance(name,str) or not name:raise ValueError('style roles need nonempty names')
            _check(style,RENDER,'roles/'+name)
        for name in ('line_cycle','marker_cycle'):
            if name in a and (not isinstance(a[name],list) or not a[name] or any(not isinstance(v,str) for v in a[name])):
                raise ValueError(name+' must be a nonempty list of names')
        valid_lines={'Solid','Dash','Dot','DashDot','DashDotDot','ShortDash','ShortDot','ShortDashDot',
            'LongDash','LongDashDot','LongDashDotDot'}
        valid_markers={'Circle','CircleFilled','Square','SquareFilled','Triangle','TriangleFilled',
            'TriangleDown','TriangleDownFilled','Diamond','DiamondFilled','Plus','Cross','Star','StarFilled'}
        valid_markers.update({'TriangleLeft','TriangleRight','TriangleLeftFilled','TriangleRightFilled',
            'PlusFilled','CrossFilled','Pentagon','Hexagon','Octagon','PentagonFilled','HexagonFilled','OctagonFilled'})
        for name,choices in [('line_cycle',valid_lines),('marker_cycle',valid_markers)]:
            if any(v not in choices for v in a.get(name,[])):raise ValueError('unsupported '+name+' entry')
        for panel in a.get('panels',[]):
            _check(panel,dict(config=PANEL,overlays='json'),'panels')
            for overlay in panel.get('overlays',[]):_check(overlay,dict(y_axis=AXIS),'overlays')
        for spec in a.get('series',[]):
            _check(spec,dict(kind=True,style=RENDER),'series')
        for kind,style in a.get('bounded',{}).items():
            if kind not in BOUNDED_STYLE:raise ValueError('unknown bounded style family')
            _check(style,dict(BOUNDED,style=BOUNDED_STYLE[kind]),'bounded/'+kind)
        for kind,items in a.get('bounded_items',{}).items():
            if kind not in BOUNDED_STYLE:raise ValueError('unknown bounded item family')
            for item in items:_check(item,dict(color=RGBA,style=BOUNDED_STYLE[kind]),'bounded_items')
        for kind,styles in a.get('annotations',{}).items():
            if kind not in ANNOTATION:raise ValueError('unknown annotation kind')
            for style in styles if isinstance(styles,list) else [styles]:
                _check(style,ANNOTATION[kind],'annotations/'+kind)
        if 'layout' in a:
            layout=a['layout'];_check(layout,dict(gap=True,row_weights='json',column_weights='json',grid='json'),'layout')
            if set(layout)!={'gap','row_weights','column_weights','grid'}:raise ValueError('layout needs gap, weights and grid')
            grid=layout['grid']
            if not isinstance(grid,list) or not grid or not isinstance(grid[0],list) or not grid[0] or any(not isinstance(r,list) or len(r)!=len(grid[0]) for r in grid):
                raise ValueError('layout grid must be rectangular')
            if any(v is not None and (type(v) is not int or v<0) for r in grid for v in r):raise ValueError('layout grid uses integer panel slots')
            for key,count in [('row_weights',len(grid)),('column_weights',len(grid[0]))]:
                if not isinstance(layout[key],list) or len(layout[key])!=count or any(type(v) not in (int,float) or v<=0 for v in layout[key]):raise ValueError('invalid layout weights')
            if not isinstance(layout['gap'],(int,float)) or layout['gap']<0:raise ValueError('layout gap must be nonnegative')
        for payload in (self.scales,self.text):
            if payload is not None and not isinstance(payload,dict):raise ValueError('optional style payload must be a mapping')
        if self.scales is not None:
            if set(self.scales)-{'panels','family','value_range','ring_spacing'}:raise ValueError('unknown scale fields')
            for p in self.scales.get('panels',[]):
                _check(p,dict(axes={k:SCALE_AXIS for k in ('bottom_x','top_x','left_y','right_y')},
                              colorbar=SCALE_AXIS,overlays='json'),'scales')
                for o in p.get('overlays',[]):_check(o,SCALE_AXIS,'scales/overlays')
        if self.text is not None:
            if set(self.text)-{'panels','series','family','bounded'}:raise ValueError('unknown text fields')
            for p in self.text.get('panels',[]):
                _check(p,dict(titles='json',axis_titles={key:'json' for key in ('bottom_x','top_x','left_y','right_y')},
                              colorbar_title='json',overlays='json'),'text/panels')
            if 'bounded' in self.text:
                _check(self.text['bounded'],dict(title=True,title_segments='json',category_title=True,value_title=True,legend_labels='json'),'text/bounded')
        # Also reject NaN/inf, non-JSON objects and accidentally supplied arrays.
        json.dumps(self.to_dict(),allow_nan=False)
        return self

    def to_dict(self):
        return copy.deepcopy(dict(version=self.version,appearance=self.appearance,scales=self.scales,text=self.text))

    def to_json(self, *, indent=2):
        self.validate()
        return json.dumps(self.to_dict(),ensure_ascii=False,allow_nan=False,indent=indent)

    @classmethod
    def from_dict(cls,value):
        if not isinstance(value,dict) or set(value)-{'version','appearance','scales','text'}:
            raise ValueError('invalid style token document')
        if 'version' not in value:raise ValueError('style token requires a version')
        return cls(**value)

    @classmethod
    def from_json(cls,value):return cls.from_dict(json.loads(value))

    def save(self,path):Path(path).write_text(self.to_json()+'\n',encoding='utf-8')

    @classmethod
    def load(cls,path):return cls.from_json(Path(path).read_text(encoding='utf-8'))

    @classmethod
    def from_figure(cls,figure,**kwargs):return extract(figure,**kwargs)


def extract(figure, *, scales=False, text=False):
    """Extract accepted SSOT. In notebooks await Figure.sync() before extraction."""
    if type(scales) is not bool or type(text) is not bool:
        raise ValueError('scales and text extraction flags must be boolean')
    with figure._lock:
        state=figure.get_settings()
        unit=72/figure.dpi
        kind=family(state)
        panels=_panels(state)
        appearance=dict(panels=[])
        for cfg in panels:
            p=dict(config=_units(_project(cfg,PANEL),unit),overlays=[
                dict(y_axis=_units(_project(o['y_axis'],AXIS),unit)) for o in cfg.get('overlays',[])])
            if not kind:p['config'].setdefault('draw_style',dict(mode='precise'))
            appearance['panels'].append(p)
        appearance['background']=copy.deepcopy(state.get('background',dict(r=1.,g=1.,b=1.,a=1.)))
        appearance['series']=[dict(kind=next(iter(s['render_type'])),
            style=_units(_project(next(iter(s['render_type'].values())),RENDER),unit)) for s in state['series']]
        if kind:
            chart=state[kind]
            appearance['bounded']={kind:_units(_project(chart,dict(BOUNDED,style=BOUNDED_STYLE[kind])),unit)}
            appearance['bounded_items']={kind:[_units(_project(v,dict(color=RGBA,style=BOUNDED_STYLE[kind])),unit)
                for v in chart.get('slices',chart.get('series',[]))]}
            appearance['background']=copy.deepcopy(chart['background'])
        owner=state[kind] if kind else state['config']
        for item in owner.get('annotations',{}).get('items',[]):
            tag,body=next(iter(item['kind'].items()))
            appearance.setdefault('annotations',{}).setdefault(tag,[]).append(_units(_project(body,ANNOTATION[tag]),unit))
        layout=state['identity'].get('layout')
        if layout:
            slots=layout['placement'];ids=[v['id'] for v in state['identity']['panels']]
            appearance['layout']=dict(gap=layout['gap']*unit,row_weights=copy.deepcopy(layout['row_weights']),
                column_weights=copy.deepcopy(layout['column_weights']),
                grid=[[None if slot is None or slot not in slots else ids.index(slots[slot]) for slot in row] for row in layout['grid']])
        scale_payload=None
        if scales:
            scale_payload=dict(panels=[])
            for i,cfg in enumerate(panels):
                pid=state['identity']['panels'][i]['id']
                def axis_scale(axis,owner,key):
                    return dict(_project(axis,dict.fromkeys(SCALE_KEYS,True)),
                        tick_mode=state['identity'].get('tick_modes',{}).get(owner,{}).get(key,'Auto'))
                p=dict(axes={key:axis_scale(cfg[key],pid,key) for key in ('bottom_x','top_x','left_y','right_y')},
                    overlays=[axis_scale(o['y_axis'],state['identity']['panels'][i]['overlays'][j],'y_axis') for j,o in enumerate(cfg.get('overlays',[]))])
                if cfg.get('colorbar'):p['colorbar']=_project(cfg['colorbar']['axis'],dict.fromkeys(SCALE_KEYS,True))
                scale_payload['panels'].append(p)
            if kind:
                scale_payload['family']=kind
                for key in ('value_range','ring_spacing'):
                    if key in state[kind]:scale_payload[key]=copy.deepcopy(state[kind][key])
        text_payload=None
        if text:
            text_payload=dict(panels=[_panel_text(c) for c in panels],series=[copy.deepcopy(s.get('label')) for s in state['series']])
            if kind:
                chart=state[kind];text_payload['family']=kind
                text_payload['bounded']={k:copy.deepcopy(chart[k]) for k in ('title','category_title','value_title') if k in chart}
                if chart.get('chart_title'):
                    from .figure import _text
                    text_payload['bounded']['title'] = _text(chart['chart_title']['text'])
                    text_payload['bounded']['title_segments'] = copy.deepcopy(chart['chart_title']['text']['segments'])
                text_payload['bounded']['legend_labels']=[s['label'] for s in chart.get('slices',chart.get('series',[]))]
        return StyleToken(appearance,scale_payload,text_payload)


def _font_size(typo, role):
    if role in typo:return typo[role]
    if 'font_size' in typo:return typo['font_size']*typo.get(role.replace('_size','_scale'),1)
    return None


def _typography(cfg, typo):
    def rich(node,size):
        for src,dst in [('font','font'),('color','color')]:
            if src in typo:node[dst]=copy.deepcopy(typo[src])
        value=_font_size(typo,size)
        if value is not None:node['font_size']=value
    rich(cfg['chart_title']['text'],'title_size');rich(cfg['legend']['content'],'legend_size')
    for key in ('bottom_x','top_x','left_y','right_y'):
        axis=cfg[key];rich(axis['title_option']['text'],'label_size')
        label=axis['label_style']
        for src,dst in [('font','label_font'),('color','color')]:
            if src in typo:label[dst]=copy.deepcopy(typo[src])
        value=_font_size(typo,'label_size')
        if value is not None:label['font_size']=value
    if cfg.get('colorbar'):
        # Same axis typography without requiring another chart model.
        temp=dict(cfg,bottom_x=cfg['colorbar']['axis'])
        for key in ('top_x','left_y','right_y'):temp[key]=cfg['colorbar']['axis']
        temp.pop('colorbar',None);_typography(temp,typo)
    for overlay in cfg.get('overlays',[]):
        temp=dict(cfg,bottom_x=overlay['y_axis']);temp.pop('overlays',None);temp.pop('colorbar',None)
        for key in ('top_x','left_y','right_y'):temp[key]=overlay['y_axis']
        _typography(temp,typo)


def _axis_apply(axis,patch,limits):
    allowed=SCALE_KEYS if limits else ('scale','inverted')
    for key in allowed:
        if key in patch:axis[key]=copy.deepcopy(patch[key])
    if axis['scale']=='Logarithmic' and axis['min']<=0:
        raise ValueError('log style requires positive axis limits; set positive limits explicitly')


def _render_patch(body, patch):
    """Appearance defaults can style existing components, never introduce kinds."""
    for key,value in patch.items():
        if key in body and isinstance(body[key],dict):_merge(body[key],value)


def _encode_series(body, appearance, index, role=None):
    palette=appearance.get('palette',[])
    if palette:
        color=palette[index%len(palette)]
        for name,keys in [('line',['line_color']),('scatter',['point_color']),('bar',['fill_color']),('err_style',['error_bar_color']),('style',['color'])]:
            if not isinstance(body.get(name),dict):continue
            if name=='scatter' and body[name].get('point_color_map'):continue
            if name=='style' and body[name].get('color_map'):continue
            for key in keys:
                if key in body[name]:body[name][key]=copy.deepcopy(color)
        if isinstance(body.get('contour',{}).get('line'),dict):
            body['contour']['line']['line_color']=copy.deepcopy(color)
    block=index//max(1,len(palette))
    if appearance.get('line_cycle') and 'line' in body:
        body['line']['line_style']=appearance['line_cycle'][block%len(appearance['line_cycle'])]
    if appearance.get('line_cycle') and 'contour' in body:
        body['contour']['line']['line_style']=appearance['line_cycle'][block%len(appearance['line_cycle'])]
    if appearance.get('marker_cycle') and 'scatter' in body:
        body['scatter']['point_shape']=appearance['marker_cycle'][(index%max(1,len(palette))+block)%len(appearance['marker_cycle'])]
    if role in appearance.get('roles',{}):_render_patch(body,appearance['roles'][role])


class _Candidate:
    """Resolve appearance before a constructor uploads/commits new objects."""
    def __init__(self,figure,state,finalize=None):
        self.state=copy.deepcopy(state);self.dpi=figure.dpi;self._lock=figure._lock
        self._check_font=figure._check_font;self.finalize=finalize

    def get_settings(self):return copy.deepcopy(self.state)
    def apply_settings(self,state,**kwargs):self.state=copy.deepcopy(state)


def _resolve(figure,state,token,finalize=None):
    candidate=_Candidate(figure,state,finalize)
    with warnings.catch_warnings():
        # Defaults may describe fields or families not constructed yet.
        warnings.simplefilter('ignore',StyleWarning)
        apply(candidate,token)
    return candidate.state


def apply(figure, token, *, scales=False, text=False, size_scale=1.0,
          panel_map=None, series_map=None, layout=False, strict=False,
          expected_revision=None, limits=True, role_map=None):
    """Resolve a token completely before one atomic accepted-settings edit."""
    from .figure import _colormap
    if isinstance(token,str):token=preset(token)
    if not isinstance(token,StyleToken):raise TypeError('style must be a StyleToken or preset name')
    token.validate()
    if any(type(flag) is not bool for flag in (scales,layout,strict,limits)):
        raise ValueError('scales, layout, strict and limits flags must be boolean')
    size_scale=float(size_scale)
    if not math.isfinite(size_scale) or size_scale<=0:raise ValueError('size_scale must be positive and finite')
    groups=TEXT_GROUPS if text is True else set() if text is False else set(text)
    if not groups<=TEXT_GROUPS:raise ValueError('unknown text selection')
    if scales and token.scales is None:raise ValueError('token contains no scales')
    if groups and token.text is None:raise ValueError('token contains no text')
    with figure._lock:
        state=figure.get_settings();kind=family(state)
        a=_units(token.appearance,figure.dpi/72*size_scale)
        skipped=[];applied=[]
        targets=_panels(state);ids=[p['id'] for p in state['identity']['panels']]
        source=a.get('panels',[])
        if panel_map is None:
            pairs=[(0,j) for j in range(len(targets))] if len(source)==1 else [(i,i) for i in range(min(len(source),len(targets)))]
            if len(source)>1 and len(source)!=len(targets):skipped.append('panel count differs; unmatched panel styles (use panel_map)')
        else:
            pairs=[]
            for key,value in panel_map.items():
                if type(key) is not int or key<0 or key>=len(source) or value not in ids:raise ValueError('invalid panel_map')
                pairs.append((key,ids.index(value)))
        if 'background' in a:
            if kind:state[kind]['background']=copy.deepcopy(a['background'])
            else:state['background']=copy.deepcopy(a['background'])
        for cfg in targets:
            if 'panel' in a:_panel_patch(cfg,a['panel'],kind,skipped)
            if 'colormap' in a:
                if cfg.get('colorbar'):
                    cfg['colorbar']['colormap']=_colormap(a['colormap']) if isinstance(a['colormap'],str) else copy.deepcopy(a['colormap'])
                else:skipped.append('colormap: target panel has no color scale')
        for src,dst in pairs:
            spec=source[src];cfg=targets[dst]
            _panel_patch(cfg,spec.get('config',{}),kind,skipped)
            for j,overlay in enumerate(spec.get('overlays',[])):
                if j<len(cfg.get('overlays',[])):_merge(cfg['overlays'][j],overlay)
                else:skipped.append('overlay style: no corresponding overlay')
        if a.get('layout'):
            spec=a['layout'];existing=state['identity'].get('layout')
            if layout:
                if kind:raise ValueError('bounded charts cannot use a subplot layout')
                grid=spec['grid'];seen={v for row in grid for v in row if v is not None}
                order={src:ids[dst] for src,dst in pairs}
                if seen!=set(order) or set(order.values())!=set(ids):raise ValueError('layout topology needs matching panel count')
                figure_grid=[[None if v is None else 'slot_'+str(v) for v in row] for row in grid]
                area=state['config']['chart_area'];size=existing['size'] if existing else [area['width'],area['height']]
                existing=dict(grid=figure_grid,placement={'slot_'+str(i):pid for i,pid in order.items()},size=size)
                state['identity']['layout']=existing
            if existing:
                existing['gap']=spec['gap']
                for key,axis in [('row_weights',0),('column_weights',1)]:
                    count=len(existing['grid']) if axis==0 else len(existing['grid'][0])
                    if len(spec[key])==count:existing[key]=copy.deepcopy(spec[key])
                    elif layout:raise ValueError('incompatible grid weights')
                    else:skipped.append(key+': grid dimensions differ')
                _document.place_grid(state)
        styles=a.get('series',[]);counters={};palette=a.get('palette',[])
        mapping={} if series_map is None else series_map
        if role_map is not None:
            for sid,role in role_map.items():
                if sid not in [s['series_id'] for s in state['series']] or role not in a.get('roles',{}):
                    raise ValueError('role_map must address existing series and declared style roles')
        for index,sid in mapping.items():
            if type(index) is not int or not 0<=index<len(styles) or sid not in [s['series_id'] for s in state['series']]:raise ValueError('invalid series_map')
        for i,s in enumerate(state['series']):
            tag,body=next(iter(s['render_type'].items()))
            _render_patch(body,a.get('series_defaults',{}))
            candidates=[v for v in styles if v['kind']==tag]
            selected=next((styles[k] for k,v in mapping.items() if v==s['series_id']),None)
            if selected is not None and selected['kind']!=tag:raise ValueError('series_map cannot change chart kind')
            if selected is None and series_map is None and candidates:
                n=counters.get(tag,0);selected=candidates[n%len(candidates)];counters[tag]=n+1
            if selected is not None:_merge(body,selected['style'])
            elif styles and series_map is None:skipped.append('no '+tag+' series style')
            _encode_series(body,a,i,(role_map or {}).get(s['series_id']))
            capacity=len(palette)*max(1,len(a.get('line_cycle',[])))
            categorical=any(k in body for k in ('line','bar','contour')) or ('scatter' in body and not body['scatter'].get('point_color_map')) or ('style' in body and not body['style'].get('color_map'))
            if capacity and i>=capacity and categorical and s['series_id'] not in (role_map or {}):
                skipped.append('category encodings exhausted; supply explicit styles or split/group categories')
        if kind:
            chart=state[kind]
            if kind in a.get('bounded',{}):
                patch = a['bounded'][kind]
                if patch.get('chart_title'):
                    # An appearance token omits wording. Seed from the target
                    # before merging its partial rich-title styles.
                    from ._chart_text import title_options
                    title_options(chart)
                _merge(chart,patch)
            elif a.get('bounded'):skipped.append('bounded style: source chart family differs')
            items=chart.get('slices',chart.get('series',[]));itemstyles=a.get('bounded_items',{}).get(kind,[])
            if palette and len(items)>len(palette):skipped.append('bounded palette exhausted; supply explicit colors or group series/slices')
            for i,item in enumerate(items):
                if itemstyles:_merge(item,itemstyles[i%len(itemstyles)])
                if palette:item['color']=copy.deepcopy(palette[i%len(palette)])
        elif len(a.get('bounded',{}))==1:skipped.append('bounded style: target is Cartesian')
        owner=state[kind] if kind else state['config']
        annotation_counts={}
        for item in owner.get('annotations',{}).get('items',[]):
            tag,body=next(iter(item['kind'].items()))
            styles=a.get('annotations',{}).get(tag,[])
            if styles:
                if not isinstance(styles,list):styles=[styles]
                index=annotation_counts.get(tag,0);annotation_counts[tag]=index+1
                patch=copy.deepcopy(styles[index%len(styles)])
                for key in ('text','label'):
                    if key in patch and body.get(key) is None:patch.pop(key)
                _merge(body,patch)
        if scales:
            payload=token.scales
            for src,dst in pairs:
                if src>=len(payload.get('panels',[])):continue
                cfg=targets[dst];p=payload['panels'][src]
                for key,patch in p['axes'].items():
                    _axis_apply(cfg[key],patch,limits)
                    if limits and 'tick_mode' in patch:
                        state['identity'].setdefault('tick_modes',{}).setdefault(ids[dst],{})[key]=patch['tick_mode']
                if 'colorbar' in p:
                    if cfg.get('colorbar'):_axis_apply(cfg['colorbar']['axis'],p['colorbar'],limits)
                    else:skipped.append('color scale: no target colorbar')
                for j,patch in enumerate(p.get('overlays',[])):
                    if j<len(cfg.get('overlays',[])):
                        _axis_apply(cfg['overlays'][j]['y_axis'],patch,limits)
                        if limits and 'tick_mode' in patch:
                            oid=state['identity']['panels'][dst]['overlays'][j]
                            state['identity'].setdefault('tick_modes',{}).setdefault(oid,{})['y_axis']=patch['tick_mode']
                    else:skipped.append('overlay scale: no target overlay')
            if payload.get('family'):
                if kind==payload['family']:
                    if limits:
                        for key in ('value_range','ring_spacing'):
                            if key in payload:state[kind][key]=copy.deepcopy(payload[key])
                else:raise ValueError('value scales require the same bounded family')
            for definition in state['identity']['groups'].values():
                keys=('bottom_x','top_x') if definition['axis']=='x' else ('left_y','right_y')
                members=[targets[ids.index(pid)] for pid in definition['members']]
                for key in keys:
                    values=[tuple(c[key][prop] for prop in SCALE_KEYS) for c in members]
                    if values and any(v!=values[0] for v in values):
                        raise ValueError('captured scales conflict with a shared-axis group')
        if groups:
            payload=token.text
            for src,dst in pairs:
                if src>=len(payload.get('panels',[])):continue
                p=payload['panels'][src];cfg=targets[dst]
                if 'titles' in groups:cfg['chart_title']['text']['segments']=copy.deepcopy(p['titles'])
                if 'axis_titles' in groups:
                    for key,segments in p['axis_titles'].items():cfg[key]['title_option']['text']['segments']=copy.deepcopy(segments)
                    if p.get('colorbar_title') is not None and cfg.get('colorbar'):cfg['colorbar']['axis']['title_option']['text']['segments']=copy.deepcopy(p['colorbar_title'])
                    for j,segments in enumerate(p.get('overlays',[])):
                        if j<len(cfg.get('overlays',[])):cfg['overlays'][j]['y_axis']['title_option']['text']['segments']=copy.deepcopy(segments)
            if 'legend_labels' in groups:
                labels=payload.get('series',[])
                if series_map is None:
                    if len(labels)!=len(state['series']):raise ValueError('legend text requires matching series count')
                    for i,s in enumerate(state['series']):s['label']=copy.deepcopy(labels[i])
                else:
                    for index,sid in series_map.items():
                        if index>=len(labels):raise ValueError('missing source legend label')
                        next(s for s in state['series'] if s['series_id']==sid)['label']=copy.deepcopy(labels[index])
            if payload.get('family'):
                if kind!=payload['family']:raise ValueError('bounded text requires the same family')
                p=payload['bounded'];chart=state[kind]
                if 'titles' in groups and 'title' in p:
                    from ._chart_text import set_title_text
                    set_title_text(chart, p['title'], segments=p.get('title_segments'))
                if 'axis_titles' in groups:
                    for key in ('category_title','value_title'):
                        if key in p:chart[key]=p[key]
                if 'legend_labels' in groups:
                    items=chart.get('slices',chart.get('series',[]));labels=p['legend_labels']
                    if len(items)!=len(labels):raise ValueError('legend text requires matching item count')
                    for item,label in zip(items,labels):item['label']=label
        # Explicit common typography overrides captured object styles. Extracted
        # tokens do not invent a global override from one arbitrary title.
        typo=a.get('typography',{})
        for cfg in targets:_typography(cfg,typo)
        if kind:
            chart=state[kind]
            for src,dst in [('font','font_family'),('font_size','font_size'),('color','text_color' if 'text_color' in chart else 'label_color')]:
                if src in typo:chart[dst]=copy.deepcopy(typo[src])
            if chart.get('chart_title'):
                rich=chart['chart_title']['text']
                for key in ('font','color'):
                    if key in typo:rich[key]=copy.deepcopy(typo[key])
                value=_font_size(typo,'title_size')
                if value is not None:rich['font_size']=value
        for item in owner.get('annotations',{}).get('items',[]):
            body=next(iter(item['kind'].values()))
            for key in ('text','label'):
                if isinstance(body.get(key),dict):
                    for field in ('font','font_size','color'):
                        if field in typo:body[key][field]=copy.deepcopy(typo[field])
        if isinstance(figure,_Candidate) and figure.finalize is not None:figure.finalize(state)
        if kind:
            maximum=64 if kind=='radial' else 32
            if not 8<=state[kind]['font_size']<=maximum:
                raise ValueError('%s renderer font_size must be 8..%s logical pixels at this DPI; lower font_size or size_scale' % (kind,maximum))
        # Check fonts before committing any part of the candidate.
        def check_fonts(node):
            if isinstance(node,dict):
                for key,value in node.items():
                    if key in ('font','font_family','label_font') and value not in ('sans-serif','serif','monospace'):
                        figure._check_font(value)
                    else:check_fonts(value)
            elif isinstance(node,list):
                for value in node:check_fonts(value)
        check_fonts(a)
        skipped=tuple(dict.fromkeys(skipped))
        if strict and skipped:raise ValueError('incompatible style: '+'; '.join(skipped))
        if skipped:warnings.warn('; '.join(skipped),StyleWarning,stacklevel=3)
        figure.apply_settings(state,expected_revision=expected_revision)
        applied.append('appearance')
        if scales:applied.append('scales')
        if groups:applied.append('text')
        return StyleReport(tuple(applied),skipped)


def available():
    from ._style_presets import PROFILES
    return ('paper','report','presentation','dark','monochrome','colorblind')+tuple(PROFILES)


def describe(name):
    """Source guidance, intended task, recommendations and known limitations."""
    from ._style_presets import PROFILES, describe as task_description
    if name in PROFILES:return task_description(name)
    if name not in available():raise ValueError('unknown preset: '+name)
    return dict(name=name,purpose='Legacy generic appearance starting point',
                limits=['Not a journal, accessibility or dashboard-task certification.'],sources=[])


def preset(name, *, theme=None, density='comfortable'):
    """Fresh, independent appearance-only preset. No title, label or axis domain."""
    from .figure import _color
    from ._style_presets import PROFILES,build
    if name in PROFILES:return build(name,theme,density)
    if name not in available():raise ValueError('unknown preset; choose '+', '.join(available()))
    if theme is not None or density!='comfortable':raise ValueError('theme and density options require a task profile')
    dark=name=='dark';fg=_color('#e5e7eb' if dark else '#20242b')
    bg=_color('#171b24' if dark else '#ffffff');grid=_color('#394254' if dark else '#d9dde3')
    palette=['#0072b2','#e69f00','#009e73','#cc79a7','#d55e00','#56b4e9','#f0e442']
    if name=='monochrome':palette=['#161616','#666666','#a0a0a0']
    if dark:palette=['#56b4e9','#f0b45a','#5ad1a6','#df95cb','#ff9072']
    size=16 if name=='presentation' else 11
    axis=dict(line_color=fg,line_width=.8,tick='Outside',major_tick_length=4,minor_tick_length=2,
        label_style=dict(color=fg,font_size=size,label_font=''),
        title_option=dict(text=dict(color=fg,font_size=size+1,font='')))
    panel=dict(chart_title=dict(text=dict(color=fg,font_size=size+3,font=''),top_margin=size+9),
        grid=dict(show_major_x=name in ('report','dark'),show_major_y=name!='paper',
            major_x_color=grid,major_y_color=grid,major_x_width=.6,major_y_width=.6),
        legend=dict(content=dict(color=fg,font_size=size-1,font=''),bg_color=dict(bg,a=.9),border_color=grid,padding=6),
        **{key:copy.deepcopy(axis) for key in ('bottom_x','top_x','left_y','right_y')})
    bounded={k:dict(text_color=fg,grid=name!='paper') for k in ('categorical','boxplot','radar')}
    bounded['radial']=dict(label_color=fg)
    for k in ('categorical','boxplot'):
        bounded[k]['style']=dict(outline_color=fg)
    bounded['boxplot']['style'].update(median_color=fg,whisker_color=fg,outlier_color=fg)
    bounded['radar']['style']=dict(spoke_color=grid,ring_color=grid)
    return StyleToken(dict(typography=dict(font='',font_size=size,title_scale=(size+3)/size,label_scale=1,
        legend_scale=(size-1)/size,color=fg),background=bg,palette=[_color(c) for c in palette],panel=panel,
        series_defaults=dict(line=dict(line_width=1.2),scatter=dict(point_size=3),
            err_style=dict(error_bar_width=1,error_bar_cap_size=3,cap_width=1),
            bar=dict(border_width=.6),contour=dict(line=dict(line_width=1))),bounded=bounded))
