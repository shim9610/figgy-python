"""Execution declarations inherit at construction, without replaying accepted edits."""
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context

import numpy as np
import pytest
import figgyplot as fg
from figgyplot.figure import _color
from figgyplot._style_presets import PROFILES


@pytest.fixture(autouse=True)
def clean_defaults():
    fg.use_style(None)
    yield
    fg.use_style(None)


def body(fig,index=-1):
    return next(iter(fig.get_settings()['series'][index]['render_type'].values()))


def close_color(actual,expected):
    assert list(actual)==list(expected)
    assert list(actual.values())==pytest.approx(list(expected.values()))


def contrast(c,b):
    def luminance(value):
        channels=[value[k] for k in ('r','g','b')]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels]
        return sum(w*v for w,v in zip((.2126,.7152,.0722),linear))
    a,d=luminance(c),luminance(b)
    return (max(a,d)+.05)/(min(a,d)+.05)


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('kind',['line','bar','box','pie','radar'])
def test_all_task_profiles_inherit_in_both_backends(profile,kind,backend):
    with fg.style_context(profile):
        fig=fg.Figure(backend=backend)
    try:
        # Constructors outside the declaring scope still use the captured defaults.
        ax=fig.axes[0]
        if kind=='line':ax.plot([1,2],[3,4],marker='o',label='Signal')
        elif kind=='bar':ax.bar(['a','b'],[2,3])
        elif kind=='box':ax.boxplot([1,2,3,5])
        elif kind=='pie':ax.pie([1,2],labels=['a','b'])
        else:ax.radar(['a','b','c'],[1,2,3])
        state=fig.get_settings();token=fg.styles.preset(profile)
        if kind=='line':close_color(body(fig)['line']['line_color'],token.appearance['palette'][0])
        else:
            family={'bar':'categorical','box':'boxplot','pie':'radial','radar':'radar'}[kind]
            close_color(state[family]['background'],token.appearance['background'])
            assert state[family]['font_size']==pytest.approx(PROFILES[profile]['font']*fig.dpi/72)
    finally:fig.close()


def test_scope_nesting_reset_exception_and_figure_optout():
    fg.use_style('dashboard.operations')
    with fg.Figure(backend='webgpu') as a:
        with pytest.raises(RuntimeError):
            with fg.style_context('dashboard.public'):
                with fg.Figure(backend='webgpu') as b:assert b.style_defaults.appearance['typography']['font_size']==13
                raise RuntimeError('restore')
        with fg.Figure(backend='webgpu') as c,fg.Figure(backend='webgpu',style=None) as d:
            assert c.style_defaults.appearance==a.style_defaults.appearance
            assert d.style_defaults is None
        # Local Figure overrides are composed over current execution defaults.
        with fg.Figure(backend='webgpu',style=fg.StyleToken(dict(typography=dict(font_size=12)))) as e:
            assert e.style_defaults.appearance['typography']['font_size']==12
            assert e.style_defaults.appearance['background']==a.style_defaults.appearance['background']
        fg.use_style(None)
        a.axes[0].plot([1,2],[3,4])
        close_color(body(a)['line']['line_color'],a.style_defaults.appearance['palette'][0])
    with fg.Figure(backend='webgpu') as f:assert f.style_defaults is None


def test_contexts_and_threads_do_not_share_declarations():
    fg.use_style('dashboard.operations')
    def observe():
        with fg.Figure(backend='webgpu') as f:return f.style_defaults
    assert Context().run(observe) is None
    with ThreadPoolExecutor(1) as executor:assert executor.submit(observe).result() is None
    async def scoped(name):
        with fg.style_context(name):
            await asyncio.sleep(0)
            return observe().appearance['typography']['font_size']
    async def run():return await asyncio.gather(scoped('dashboard.operations'),scoped('dashboard.public'))
    assert asyncio.run(run())==[11,13]
    assert observe().appearance['typography']['font_size']==11


@pytest.mark.parametrize('name,kwargs,paths',[
 ('plot',dict(color='black',linewidth=1.5,linestyle='-',marker='o',markersize=4),
  [('line','line_color'),('line','line_width'),('line','line_style'),('scatter','point_shape'),('scatter','point_size')]),
 ('scatter',dict(color='black',s=16,marker='o'),[('scatter','point_color'),('scatter','point_size'),('scatter','point_shape')]),
 ('errorbar',dict(color='black',ecolor='black',linewidth=1.5,elinewidth=1,capsize=3,marker='o',markersize=4),
  [('line','line_color'),('line','line_width'),('scatter','point_size'),('err_style','error_bar_width'),('err_style','error_bar_cap_size')]),
 ('stairs',dict(color='black',edgecolor='black',linewidth=.5,gap=1,width=1),
  [('bar','fill_color'),('bar','border_color'),('bar','border_width'),('bar','gap_px'),('bar','width_ratio')]),
 ('contour',dict(color='black',linewidth=1),[('contour','line','line_color'),('contour','line','line_width')]),
 ('quiver',dict(color='black',width=1,head_length=6,head_width=4),
  [('style','color'),('style','width_px'),('style','head_length_px'),('style','head_width_px')]),
])
def test_explicit_values_equal_to_old_defaults_win(name,kwargs,paths):
    def draw(fig):
        ax=fig.axes[0]
        args={'plot':([1,2],[3,4]),'scatter':([1,2],[3,4]),'errorbar':([1,2],[3,4]),
              'stairs':([1,2],[0,1,2]),'contour':(np.arange(9).reshape(3,3),),
              'quiver':([1,2],[3,4],[.2,.3],[.3,.2])}[name]
        extra=dict(yerr=.1) if name=='errorbar' else {}
        getattr(ax,name)(*args,**kwargs,**extra)
    with fg.Figure(backend='webgpu') as original,fg.Figure(backend='webgpu',style='dashboard.wallboard') as themed:
        draw(original);draw(themed)
        for path in paths:
            a,b=body(original),body(themed)
            for part in path:a,b=a[part],b[part]
            assert a==b,(name,path,a,b)


@pytest.mark.parametrize('name',['step','hist','contourf','fill_between'])
def test_nested_constructors_do_not_treat_forwarded_defaults_as_explicit(name):
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        ax=fig.axes[0]
        if name=='step':ax.step([1,2],[3,4],where='post')
        elif name=='hist':ax.hist([1,1,2,3],bins=3)
        elif name=='contourf':ax.contourf(np.arange(9).reshape(3,3))
        else:ax.fill_between([1,2],[3,4],[2,3])
        b=body(fig)
        if name=='step':
            close_color(b['line']['line_color'],_color('#64c6ef'))
            assert b['line']['interpolation']=='StepPost'
        elif name=='hist':close_color(b['bar']['fill_color'],_color('#64c6ef'))
        elif name=='contourf':assert b['contour']['line']['line_width']==0
        else:
            assert all(next(iter(s['render_type'].values()))['line']['line_width']==0 for s in fig.get_settings()['series'])
            close_color(dict(b['line']['fill_color'],a=1),_color('#64c6ef'))
            assert b['line']['fill_color']['a']==pytest.approx(.3)


def test_existing_edits_are_not_replayed_by_new_series_annotations_or_layout():
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        ax=fig.axes[0];ax.plot([1,2],[3,4],id='kept')
        ax.text(.5,.5,'Keep this',coords='ratio',id='text')
        fig.configure(series={'kept':{'render_type':{'Line':{'line':{'line_width':23}}}}})
        state=fig.get_settings();state['config']['chart_title']['text']['font_size']=31
        state['config']['annotations']['items'][0]['kind']['Text']['text']['font_size']=29
        fig.apply_settings(state);before=fig.get_settings()
        ax.scatter([1,2],[3,4]);ax.text(.2,.3,'New text',coords='ratio')
        fig.set_layout([['main','new']]);overlay=ax.twinx(id='right')
        after=fig.get_settings()
        assert after['series'][0]==before['series'][0]
        assert after['config']['chart_title']==before['config']['chart_title']
        assert after['config']['annotations']['items'][0]==before['config']['annotations']['items'][0]
        assert after['config']['subplots'][0]['config']['chart_title']['text']['font_size']==pytest.approx(14*fig.dpi/72)
        assert overlay._overlay(after)['y_axis']['label_style']['font_size']==pytest.approx(11*fig.dpi/72)


@pytest.mark.parametrize('name',['text','arrow','axhline','axvspan'])
def test_annotation_defaults_and_explicit_style_preserve_geometry(name):
    def add(fig,explicit):
        kw=dict(color='black') if explicit else {}
        ax=fig.axes[0]
        if name=='text':ax.text(.3,.4,'Do not replace',coords='ratio',**kw)
        elif name=='arrow':ax.arrow(.1,.2,.3,.4,coords='ratio',**kw)
        elif name=='axhline':ax.axhline(2,**kw)
        else:ax.axvspan(1,3,**kw)
        return next(iter(fig.get_settings()['config']['annotations']['items'][-1]['kind'].values()))
    with fg.Figure(backend='webgpu') as original,fg.Figure(backend='webgpu',style='dashboard.operations') as themed:
        before=add(original,True);after=add(themed,True)
        # Geometry and explicit black are identical despite dark profile.
        for key in ('anchor','from','to','axis','value'):
            if key in before:assert after[key]==before[key]
        color=lambda b: b['text']['color'] if name=='text' else b['style']['line']['color'] if name=='arrow' else b['style']['color'] if name=='axhline' else b['fill']
        close_color(color(before),color(after))
        default=add(themed,False)
        assert color(default)!=color(before)


def test_stable_cross_figure_category_keys_and_explicit_semantic_roles():
    with fg.style_context('dashboard.operations'):
        with fg.Figure(backend='webgpu') as first,fg.Figure(backend='webgpu') as second:
            a,b=first.axes[0],second.axes[0]
            a.plot([0,1],[1,2],style_key='service-a');a.plot([0,1],[2,3],style_key='service-b')
            b.plot([0,1],[2,3],style_key='service-b');b.plot([0,1],[1,2],style_key='service-a')
            assert body(first,0)['line']==body(second,1)['line']
            assert body(first,1)['line']==body(second,0)['line']
            b.plot([0,1],[4,4],style_key='warning')
            assert body(second)['line']['line_style']=='Dash'
            b.scatter([0,1],[4,4],style_key='warning')
            assert body(second)['scatter']['point_shape']=='TriangleFilled'
            b.plot([0,1],[5,5],color='black',style_key='critical')
            close_color(body(second)['line']['line_color'],_color('black'))
    with fg.Figure(backend='webgpu') as f:
        with pytest.raises(ValueError,match='requires'):f.axes[0].plot([1,2],style_key='service-a')


def test_palette_exhaustion_adds_dashes_then_reports_capacity():
    token=fg.StyleToken(dict(palette=['#0067a5'],line_cycle=['Solid','Dash']))
    with fg.Figure(backend='webgpu',style=token) as fig:
        fig.axes[0].plot([1,2]);fig.axes[0].plot([1,2])
        assert body(fig,0)['line']['line_style']=='Solid';assert body(fig,1)['line']['line_style']=='Dash'
        with pytest.warns(fg.StyleWarning,match='exhausted'):fig.axes[0].plot([1,2])


def test_set_style_and_one_shot_have_distinct_future_behavior():
    with fg.Figure(backend='webgpu') as fig:
        fig.apply_style('dashboard.operations');assert fig.style_defaults is None
        fig.axes[0].plot([1,2]);fig.set_style('dashboard.operations')
        fig.axes[0].plot([2,3]);close_color(body(fig)['line']['line_color'],_color('#baa5ff'))
        fig.set_style(None);assert fig.style_defaults is None
        before=fig.get_settings()['series']
        fig.axes[0].plot([3,4]);assert fig.get_settings()['series'][:2]==before


def test_declarations_do_not_replay_scale_or_text_and_are_copied():
    with fg.Figure(backend='webgpu') as source:
        source.axes[0].set_title('SOURCE');source.axes[0].set_xlim(100,200)
        token=source.extract_style(scales=True,text=True)
    fg.use_style(token);token.appearance['panel']={'legend':{'padding':99}}
    with fg.Figure(backend='webgpu') as fig:
        assert fig.style_defaults.scales is None and fig.style_defaults.text is None
        assert fig.get_settings()['config']['bottom_x']['min']!=100
        assert 'SOURCE' not in str(fig.get_settings()['config']['chart_title'])
        copied=fig.style_defaults;copied.appearance['panel']={'legend':{'padding':123}}
        assert fig.style_defaults.appearance!=copied.appearance


def test_rejected_style_has_no_partial_columns_or_accepted_document():
    token=fg.styles.preset('dashboard.operations')
    with fg.Figure(backend='webgpu',style=token) as fig:
        before=fig.get_settings();columns=copy.deepcopy(fig._native.columns)
        fig._style_defaults.appearance['series_defaults']['line']['line_width']=-1
        with pytest.raises(ValueError):fig.axes[0].plot([1,2],[3,4])
        assert fig.get_settings()==before
        assert fig._native.columns==columns


def test_annotation_creation_does_not_consume_category_colors():
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        fig.axes[0].text(.2,.2,'Note',coords='ratio');fig.axes[0].axhline(1)
        fig.axes[0].plot([1,2]);close_color(body(fig)['line']['line_color'],_color('#64c6ef'))


def test_secondary_axis_inherits_axis_appearance_and_is_readable():
    with fg.Figure(backend='webgpu',style='dashboard.instrument') as fig:
        ax=fig.axes[0];ax.configure(left_y={'tick':'Outside'})
        secondary=ax.twinx()
        axis=secondary._overlay(fig.get_settings())['y_axis']
        assert axis['tick']=='Inside'
        assert axis['label_style']['label_visible']
        assert ax._config(fig.get_settings())['left_y']['tick']=='Outside'


def test_role_map_existing_series_and_solid_contour_contrast():
    with fg.Figure(backend='webgpu') as fig:
        fig.axes[0].plot([1,2],[3,4],id='latency')
        fig.apply_style('dashboard.operations',role_map={'latency':'critical'})
        close_color(body(fig)['line']['line_color'],_color('#ff7c85'))
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        fig.axes[0].contour(np.arange(9).reshape(3,3))
        close_color(body(fig)['contour']['line']['line_color'],_color('#64c6ef'))


def test_single_bounded_series_key_and_ambiguous_multi_series_guard():
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        fig.axes[0].bar(['a','b'],[1,2],style_key='critical')
        close_color(fig.get_settings()['categorical']['series'][0]['color'],_color('#ff7c85'))
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        before=fig.get_settings()
        with pytest.raises(ValueError,match='one series'):
            fig.axes[0].bar(['a','b'],[[1,2],[3,4]],style_key='critical')
        assert fig.get_settings()==before


def test_default_equal_font_and_bounded_style_overrides():
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        fig.axes[0].text(.2,.2,'Explicit',coords='ratio',fontsize=11,color='black')
        rich=fig.get_settings()['config']['annotations']['items'][0]['kind']['Text']['text']
        assert rich['font_size']==pytest.approx(11*fig.dpi/72)
        close_color(rich['color'],_color('black'))
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        fig.axes[0].bar(['a','b'],[1,2],font_size=18,style=dict(corner_radius=0),color='black')
        chart=fig.get_settings()['categorical']
        assert chart['font_size']==18 and chart['style']['corner_radius']==0
        close_color(chart['series'][0]['color'],_color('black'))


@pytest.mark.parametrize('theme',['light','dark'])
@pytest.mark.parametrize('density',['compact','comfortable'])
def test_task_variants_contrast_and_print_guards(theme,density):
    for name,p in PROFILES.items():
        if p.get('print'):
            if theme=='dark' or density=='compact':
                with pytest.raises(ValueError):fg.styles.preset(name,theme=theme,density=density)
                continue
        token=fg.styles.preset(name,theme=theme,density=density);a=token.appearance
        assert all(contrast(c,a['background'])>=4.5 for c in a['palette'])
        assert all(contrast(v['line']['line_color'],a['background'])>=4.5 for v in a['roles'].values())
        with fg.Figure(backend='webgpu',style=token) as fig:
            fig.axes[0].plot([1,2],[3,4]);assert fig.get_settings()['series']


def test_marker_encodings_do_not_repeat_within_declared_capacity():
    for name in PROFILES:
        a=fg.styles.preset(name).appearance;seen=set()
        with fg.Figure(backend='webgpu',style=name) as fig:
            for i in range(fg.styles.describe(name)['category_capacity']):
                fig.axes[0].scatter([1,2],[3,4]);s=body(fig)['scatter']
                encoding=tuple(s['point_color'].values())+(s['point_shape'],)
                assert encoding not in seen,(name,i)
                seen.add(encoding)


def test_physical_font_limit_is_reported_without_shrinking():
    with fg.Figure(backend='webgpu',dpi=300,style='print.monochrome') as fig:
        before=fig.get_settings()
        with pytest.raises(ValueError,match='8..32'):fig.axes[0].boxplot([1,2,3,4])
        assert fig.get_settings()==before
        # A caller can choose valid renderer pixels explicitly for this family.
        fig.axes[0].boxplot([1,2,3,4],font_size=32)
        assert fig.get_settings()['boxplot']['font_size']==32


def test_one_shot_and_bounded_palette_exhaustion_are_reported():
    token=fg.StyleToken(dict(palette=['#0067a5'],line_cycle=['Solid','Dash']))
    with fg.Figure(backend='webgpu') as fig:
        for i in range(3):fig.axes[0].plot([1,2],[i,i+1])
        before=fig.get_settings()
        with pytest.raises(ValueError,match='encodings exhausted'):fig.apply_style(token,strict=True)
        assert fig.get_settings()==before
        with pytest.warns(fg.StyleWarning,match='encodings exhausted'):report=fig.apply_style(token)
        assert any('encodings exhausted' in s for s in report.skipped)
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        with pytest.warns(fg.StyleWarning,match='bounded palette exhausted'):
            fig.axes[0].pie([1]*7)


def test_concurrent_additions_keep_unique_local_category_assignments():
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        def add(i):fig.axes[0].plot([0,1],[i,i+1],id='s'+str(i))
        with ThreadPoolExecutor(6) as pool:list(pool.map(add,range(6)))
        actual=[tuple(next(iter(s['render_type'].values()))['line']['line_color'].values()) for s in fig.get_settings()['series']]
        assert len(set(actual))==6
        assert fig.info['columns']==12
