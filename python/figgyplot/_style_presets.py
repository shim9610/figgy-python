"""Task profiles: documented source guidance and explicit product choices."""
import copy

SOURCES={
 'nature':['https://www.nature.com/nature/for-authors/final-submission',
           'https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/'],
 'ieee':['https://proceedingsoftheieee.ieee.org/resources/guidelines-for-figures-and-tables/'],
 'kfas':['https://www.e-kfas.org/intro/instructions.asp'],
 'screen':['https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips',
           'https://www.carbondesignsystem.com/building-blocks/data-visualization/color-palettes'],
 'operations':['https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/'],
 'contrast':['https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html',
             'https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html'],
}
# Font sizes are points. Profile widths are recommendations, never resize edits.
PROFILES={
 'publication.nature':dict(purpose='Small final-size scientific figures',font=6.5,title=7,print=True,tick='Inside',widths_mm=[89,183],source='nature'),
 'publication.ieee-proceedings':dict(purpose='Engineering figures for Proceedings of the IEEE',font=9,title=10,print=True,tick='Inside',widths_mm=[88.9,182],source='ieee',mono=True),
 'publication.kfas':dict(purpose='Four-sided scientific frame with inward ticks',font=9,title=10,print=True,tick='Inside',source='kfas'),
 'scientific.precision':dict(purpose='Dense quantitative signals with a full measurement frame',font=10,title=12,tick='Inside',grid='both',source='screen'),
 'print.monochrome':dict(purpose='Grayscale printing and photocopying',font=9,title=11,print=True,tick='Inside',mono=True,source='contrast'),
 'presentation.stage':dict(purpose='Projected charts with few large marks',font=17,title=22,dark=True,thick=2.6,source='screen'),
 'dashboard.executive':dict(purpose='Sparse performance overview with comparison context',font=12,title=16,thick=2,source='screen'),
 'dashboard.operations':dict(purpose='Operational trends with caller-supplied alert roles',font=11,title=14,dark=True,source='operations'),
 'dashboard.analysis':dict(purpose='Comparisons, uncertainty and focus versus context',font=10,title=13,grid='both',source='screen'),
 'dashboard.instrument':dict(purpose='Dense measurement traces, units and references',font=10,title=12,dark=True,tick='Inside',grid='both',source='screen'),
 'dashboard.wallboard':dict(purpose='Distant viewing with large labels and strokes',font=17,title=24,dark=True,thick=2.8,source='screen'),
 'dashboard.public':dict(purpose='Broad-audience charts with clear redundant encodings',font=13,title=17,thick=2,source='contrast'),
 'dashboard.mobile':dict(purpose='Small-screen single-chart reading',font=11,title=14,thick=1.8,source='screen'),
 'education.explainer':dict(purpose='Teaching with a clear frame, labels and emphasis',font=12,title=16,tick='Outside',grid='both',thick=1.8,source='screen'),
}
LIGHT=['#0067a5','#a74432','#6841b1','#007f65','#946200','#5d6470']
DARK=['#64c6ef','#ffbf69','#baa5ff','#65d6b4','#ff7c85','#c0cad7']
MARKERS=['CircleFilled','SquareFilled','TriangleFilled','DiamondFilled','Plus','Cross']
DASHES=['Solid','Dash','Dot','DashDot']


def describe(name):
    if name not in PROFILES:raise ValueError('unknown task profile: '+name)
    p=copy.deepcopy(PROFILES[name]);source=p.pop('source')
    guidance={
        'nature':['89/183 mm typical final widths; ordinary lettering 5–7 pt; editable vector/font handling required.'],
        'ieee':['Proceedings of the IEEE recommends approximately 9–10 pt lettering.'],
        'kfas':['Four-sided frames and inward ticks are specified; this profile\'s 9 pt size is a product choice.'],
    }.get(source,['Task taxonomy, typography, spacing and default colors are product choices informed by the cited guidance.'])
    p.update(name=name,checked='2026-10-26',sources=SOURCES[source]+([] if source=='contrast' else SOURCES['contrast']),
        verified_guidance=guidance,
        default_theme='dark' if p.get('dark') else 'light',
        tick_provenance='journal requirement' if name=='publication.kfas' else 'product design choice; not a journal requirement',
        category_capacity=12 if p.get('mono') else 24,
        limits=['Appearance only; no thresholds, units, scale domains or text inferred.',
                'PNG export does not meet editable vector/font submission requirements.',
                'Default host font must be checked or explicitly replaced; no bundled journal font guarantee.',
                'Color contrast audit is not whole-chart accessibility or CVD certification.',
                'Mobile navigation, reflow and wallboard viewing distance belong to the host.'])
    return p


def build(name,theme=None,density='comfortable'):
    from .styles import StyleToken
    p=PROFILES[name]
    if density not in ('compact','comfortable'):raise ValueError('density must be compact or comfortable')
    if theme not in (None,'light','dark'):raise ValueError('theme must be light or dark')
    printed=p.get('print',False)
    if printed and theme=='dark':raise ValueError('print/publication profiles require a light surface')
    dark=p.get('dark',False) if theme is None else theme=='dark'
    if printed and density!='comfortable':raise ValueError('print typography is fixed; customize an extracted token explicitly')
    size=p['font']*(.9 if density=='compact' else 1)
    title=p['title']*(.9 if density=='compact' else 1)
    bg='#101924' if dark else '#ffffff';fg='#e6edf5' if dark else '#202733'
    grid='#344355' if dark else '#dbe2e9'
    muted='#aab8ca' if dark else '#5d6470'
    palette=(['#e6edf5','#b5c4d4','#889eb5'] if dark else ['#171717','#505050','#767676']) if p.get('mono') else (DARK if dark else LIGHT)
    if name in ('dashboard.operations','dashboard.instrument','dashboard.wallboard'):
        # Warm alert colors are reserved for caller-declared statuses here.
        palette=['#64c6ef','#baa5ff','#65d6b4','#c0cad7','#a4c4ff','#cfb8dd'] if dark else ['#0067a5','#6841b1','#007f65','#5d6470','#1b5c89','#6d456c']
    frame=printed or name in ('scientific.precision','dashboard.instrument','education.explainer')
    tick=p.get('tick','None');stroke=p.get('thick',1.4)
    if printed:stroke=.65
    axis=dict(tick=tick,line_visible=frame,line_color=fg,line_width=.5 if printed else .65,
              major_tick_length=2.5 if tick!='None' else 0,minor_tick_length=1.25 if tick!='None' else 0,
              minor_count=1 if tick!='None' else 0,label_style=dict(color=fg),
              title_option=dict(text=dict(color=fg)))
    panel=dict(chart_title=dict(visible=not printed,top_margin=0 if printed else title+9),
               legend=dict(bg_color=bg,border_color=bg,padding=3 if printed else 5),
               grid=dict(show_major_x=not printed and p.get('grid')=='both',show_major_y=not printed,
                         show_minor_x=False,show_minor_y=False,major_x_color=grid,major_y_color=grid,
                         major_x_width=.45,major_y_width=.45),
               **{key:copy.deepcopy(axis) for key in ('bottom_x','top_x','left_y','right_y')})
    for key in ('top_x','right_y'):
        panel[key]['label_style']['label_visible']=False
        panel[key]['out_margin']=4 if printed else max(10,size*1.5)
    panel['left_y']['out_margin']=size*4.3 if not printed else size*4.8
    panel['bottom_x']['out_margin']=size*3.4 if not printed else size*3.6
    panel['left_y']['title_option'].update(offset_x=0,offset_y=-size*.85)
    panel['bottom_x']['title_option']['offset_y']=size*.35
    if name=='dashboard.mobile':
        panel['legend']['padding']=3
        panel['top_x']['out_margin']=4;panel['right_y']['out_margin']=4
    def role(color,width=stroke,dash='Solid',shape='CircleFilled'):
        return dict(line=dict(line_color=color,line_width=width,line_style=dash),
                    scatter=dict(point_color=color,point_shape=shape),
                    err_style=dict(error_bar_color=color),bar=dict(fill_color=color),
                    style=dict(color=color),contour=dict(line=dict(line_color=color,line_width=width)))
    roles=dict(focus=role(palette[0],stroke*1.4),context=role(muted,stroke*.75),
               reference=role(muted,stroke,'Dash'),
               warning=role('#ffbf69' if dark else '#946200',stroke,'Dash','TriangleFilled'),
               critical=role('#ff7c85' if dark else '#b42332',stroke*1.2,'Dot','DiamondFilled'),
               positive=role('#65d6b4' if dark else '#007f65'))
    bounded={k:dict(text_color=fg,background=bg,grid=not printed) for k in ('categorical','boxplot','radar')}
    bounded['radial']=dict(label_color=fg,background=bg)
    bounded['categorical']['style']=dict(outline_color=fg,outline_width=.5)
    bounded['boxplot']['style']=dict(outline_color=fg,median_color=bg,mean_color=bg,whisker_color=fg,outlier_color=fg,
                                    median_width=.8,whisker_width=.6)
    bounded['radar']['style']=dict(spoke_color=grid,ring_color=grid,line_width_px=stroke,fill_opacity=.12)
    return StyleToken(dict(background=bg,typography=dict(font='',font_size=size,color=fg,
        title_scale=title/size,label_scale=1,legend_scale=.95),panel=panel,palette=palette,
        line_cycle=DASHES,marker_cycle=MARKERS,roles=roles,bounded=bounded,
        series_defaults=dict(line=dict(line_width=stroke),scatter=dict(point_size=2.5 if printed else 4),
            err_style=dict(error_bar_width=.6 if printed else 1,error_bar_cap_size=2,cap_width=.6 if printed else 1),
            bar=dict(border_width=.5,border_color=fg),contour=dict(line=dict(line_width=stroke)),
            style=dict(width_px=stroke)),
        annotations=dict(ReferenceLine=dict(style=dict(color=muted,width=stroke,style='Dash')),
            Arrow=dict(style=dict(line=dict(color=fg,width=stroke,style='Solid'),head_length=7,head_width=5)),
            Span=dict(fill=dict(r=0.3,g=0.5,b=0.7,a=.15)))))
