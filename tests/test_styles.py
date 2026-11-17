"""Style reuse preserves destination meaning; expectations use public chart values."""
import copy
import json

import numpy as np
import pytest
import figgyplot as fg


BACKENDS=['native','webgpu']

def populate(fig,kind,offset=0):
    ax=fig.axes[0]
    x=np.array([1.,2.,3.]);y=np.array([2.,4.,3.])+offset
    if kind=='line':ax.plot(x,y,marker='s',id='signal',label='Destination')
    elif kind=='mapped':ax.scatter(x,y,c=[1,4,9],id='signal')
    elif kind=='error':ax.errorbar(x,y,yerr=[.1,.2,.3],id='signal',label='Destination')
    elif kind=='hist':ax.hist([1,2,2,3,4],bins=3,id='signal')
    elif kind=='heat':ax.imshow(np.array([[1.,2.],[3.,4.]])+offset,id='signal')
    elif kind=='contour':ax.contour(np.arange(9).reshape(3,3)+offset,id='signal')
    elif kind=='vector':ax.quiver(x,y,[.1,.2,.3],[.3,.2,.1],scale=17,id='signal')
    elif kind=='fill':ax.fill_between(x,y,[.5,1,1.5],id='signal')
    elif kind=='steps':ax.step(x,y,where='post',id='signal')
    elif kind=='bar':ax.bar(['One','Two'],[2+offset,3+offset])
    elif kind=='box':ax.boxplot([[1,2,4],[2,3,5]])
    elif kind=='radar':ax.radar(['A','B','C'],[2+offset,4+offset,3+offset])
    elif kind=='pie':ax.pie([2+offset,3+offset],labels=['One','Two'])
    ax.set_title('Destination title')
    return ax


def meaning(state):
    """Fields with scientific meaning, not a reconstruction of style projection."""
    result={}
    for key in ['radial','categorical','boxplot','radar']:
        if key in state:
            chart=state[key]
            result[key]={k:copy.deepcopy(chart[k]) for k in ['categories','mode','direction','kind','value_range','ring_spacing'] if k in chart}
            result[key]['items']=[{k:copy.deepcopy(v) for k,v in s.items() if k in ('id','label','value','values','explode')}
                                  for s in chart.get('slices',chart.get('series',[]))]
            result[key]['title']=chart['title']
    panels=[state['config']]+[p['config'] for p in state['config'].get('subplots',[])]
    result['axes']=[{k:{p:c[k][p] for p in ['scale','min','max','major_spacing','inverted']} for k in ['bottom_x','top_x','left_y','right_y']} for c in panels]
    result['text']=[]
    for c in panels:
        titles={k:c[k]['title_option']['text']['segments'] for k in ['bottom_x','top_x','left_y','right_y']}
        titles['title']=c['chart_title']['text']['segments'];result['text'].append(titles)
    result['series']=[]
    for s in state['series']:
        tag,body=next(iter(s['render_type'].items()))
        entry=dict(kind=tag,label=s['label'],id=s['series_id'],x=s['x_column'],y=s['y_column'])
        for k in ['matrix','components','err_x','err_y']:
            if k in body:entry[k]=body[k]
        for part,keys in [('line',['fill','interpolation']),('scatter',['point_color_map','point_size_map']),('bar',['baseline','orientation']),('contour',['levels']),('style',['scale','color_map'])]:
            for k in keys:
                if k in body.get(part,{}):entry[part+'/'+k]=body[part][k]
        result['series'].append(entry)
    result['identity']=state['identity']
    return copy.deepcopy(result)


@pytest.mark.parametrize('backend',BACKENDS)
@pytest.mark.parametrize('kind',['line','bar','box','radar','pie'])
@pytest.mark.parametrize('preset',fg.styles.available())
def test_presets_preserve_data_text_domains_ids_and_do_not_reupload(backend,kind,preset):
    with fg.Figure(backend=backend) as fig:
        populate(fig,kind)
        before=meaning(fig.get_settings());uploads=fig.info.get('column_uploads')
        report=fig.apply_style(preset,strict=True)
        assert report.skipped==()
        assert meaning(fig.get_settings())==before
        assert fig.info.get('column_uploads')==uploads
        if backend=='native' and preset=='dark':
            image=fig.render_rgba()
            assert image[0,0,:3].max()<70


@pytest.mark.parametrize('backend',BACKENDS)
@pytest.mark.parametrize('kind',['line','mapped','error','hist','heat','contour','vector','fill','steps','bar','box','radar','pie'])
def test_extraction_and_json_reuse_never_import_data_or_wording(backend,kind,tmp_path):
    with fg.Figure(backend=backend) as source,fg.Figure(backend=backend) as target:
        populate(source,kind);populate(target,kind,offset=5)
        source.axes[0].set_title('SOURCE ONLY')
        source.apply_style('paper')
        token=source.extract_style()
        assert token.scales is None and token.text is None
        assert 'SOURCE ONLY' not in token.to_json()
        assert 'x_column' not in token.to_json() and 'err_y' not in token.to_json()
        token.save(tmp_path/'style.json');token=fg.StyleToken.load(tmp_path/'style.json')
        before=meaning(target.get_settings())
        target.apply_style(token,strict=True)
        assert meaning(target.get_settings())==before
        if backend=='native':target.render_rgba()


@pytest.mark.parametrize('backend',BACKENDS)
def test_scale_and_text_payloads_require_explicit_application(backend):
    with fg.Figure(backend=backend) as source,fg.Figure(backend=backend) as target:
        sa=populate(source,'line');ta=populate(target,'line',5)
        sa.set_title('Source');sa.set_xlabel('Source X');sa.set_ylabel('Source Y')
        sa.set_xlim(1,100);sa.set_xscale('log');ta.set_xlabel('Target X')
        token=source.extract_style(scales=True,text=True)
        before=meaning(target.get_settings());target.apply_style(token)
        assert meaning(target.get_settings())==before
        target.apply_style(token,text={'axis_titles'})
        s=target.get_settings();assert s['config']['bottom_x']['title_option']['text']['segments']==source.get_settings()['config']['bottom_x']['title_option']['text']['segments']
        assert s['config']['chart_title']['text']['segments']==before['text'][0]['title']
        target.apply_scales(token.scales,limits=False)
        assert ta.get_xscale()=='log'
        assert target.get_settings()['config']['bottom_x']['max']==before['axes'][0]['bottom_x']['max']
        target.apply_style(token,scales=True,text=True)
        assert ta.get_xscale()=='log'
        assert target.get_settings()['config']['bottom_x']['max']==100
        assert target.get_settings()['series'][0]['label']==source.get_settings()['series'][0]['label']


@pytest.mark.parametrize('backend',BACKENDS)
def test_log_failure_unknown_fields_and_stale_application_are_atomic(backend):
    with fg.Figure(backend=backend) as fig:
        ax=fig.axes[0];ax.plot([-1,0,1],[1,2,3])
        token=fig.extract_style(scales=True);token.scales['panels'][0]['axes']['bottom_x']['scale']='Logarithmic'
        before=fig.get_settings();revision=fig.revision
        with pytest.raises(ValueError,match='positive'):fig.apply_scales(token.scales,limits=False)
        bad=fg.styles.preset('paper');bad.appearance['panel']['bottom_x']['min']=10
        with pytest.raises(ValueError,match='unknown style'):fig.apply_style(bad)
        with pytest.raises(ValueError,match='stale'):fig.apply_style('dark',expected_revision=revision-1)
        assert fig.get_settings()==before and fig.revision==revision


def test_visual_scale_and_cross_dpi_reuse_are_absolute_not_multiplicative():
    with fg.Figure(dpi=100) as source,fg.Figure(dpi=200) as target:
        populate(source,'line');populate(target,'line')
        source.apply_style('presentation');t=source.extract_style();before=meaning(target.get_settings())
        target.apply_style(t,size_scale=1.5)
        s=source.get_settings();v=target.get_settings()
        assert v['config']['chart_title']['text']['font_size']==pytest.approx(s['config']['chart_title']['text']['font_size']*3)
        assert v['series'][0]['render_type']['ScatterLine']['line']['line_width']==pytest.approx(s['series'][0]['render_type']['ScatterLine']['line']['line_width']*3)
        assert meaning(v)==before
        revision=target.revision;target.apply_style(t,size_scale=1.5)
        assert target.revision==revision


@pytest.mark.parametrize('backend',BACKENDS)
def test_grid_overlay_and_colorbar_axis_titles_and_ranges(backend):
    with fg.Figure(backend=backend,grid=[['left','right']]) as source,fg.Figure(backend=backend,grid=[['a','b']]) as target:
        for fig in [source,target]:
            ids=list(fig.subplots);fig.subplots[ids[0]].axes.scatter([1,2],[3,4],c=[10,20],id='mapped')
            ax=fig.subplots[ids[1]].axes;ax.plot([1,2],[2,3]);twin=ax.twinx(id='secondary');twin.plot([1,2],[100,200]);twin.set_ylabel('Pressure')
        st=source.get_settings();st['config']['colorbar']['axis']['title_option']['text']['segments']=fg.text_segments('Energy')
        st['config']['colorbar']['axis']['min']=1;st['config']['colorbar']['axis']['max']=25
        st['config']['overlays']=[]
        source.apply_settings(st);token=source.extract_style(scales=True,text=True)
        original=target.get_settings();target.apply_style(token)
        assert target.get_settings()['config']['colorbar']['axis']['max']==20
        target.apply_style(token,scales=True,text={'axis_titles'})
        result=target.get_settings();assert result['config']['colorbar']['axis']['max']==25
        assert result['config']['colorbar']['axis']['title_option']['text']['segments']==st['config']['colorbar']['axis']['title_option']['text']['segments']
        assert result['identity']['figure']==original['identity']['figure']
        assert [p['id'] for p in result['identity']['panels']]==['a','b']


def test_token_validation_preset_independence_and_single_undo():
    a=fg.styles.preset('paper');b=fg.styles.preset('paper');a.appearance['palette'][0]['a']=.1
    assert b.appearance['palette'][0]['a']==1
    with pytest.raises(ValueError,match='version'):fg.StyleToken.from_dict(dict(version=2,appearance={}))
    with pytest.raises(ValueError):fg.StyleToken(dict(panel=dict(chart_title=dict(text=dict(segments=[])))))
    with fg.Figure() as fig:
        populate(fig,'line');fig.mark_edit_baseline();before=fig.get_settings()
        fig.apply_style('dark');fig.undo()
        assert fig.get_settings()==before


def test_notebook_extraction_waits_for_barrier():
    import asyncio
    with fg.Figure(backend='webgpu') as fig:
        populate(fig,'line');calls=[]
        async def sync(**kwargs):
            calls.append(kwargs);fig.axes[0].set_title('Accepted after barrier')
        fig.sync=sync
        token=asyncio.run(fig.extract_style_async(text=True))
        assert calls==[dict(timeout=30)]
        assert ''.join(s['text'] for s in token.text['panels'][0]['titles'])=='Accepted after barrier'


@pytest.mark.parametrize('backend',BACKENDS)
def test_layout_topology_mapping_preserves_physical_plot_margins(backend):
    with fg.Figure(backend=backend,grid=[['left','right']]) as source,fg.Figure(backend=backend,grid=[['a'],['b']],figsize=(12,8)) as target:
        for fig in [source,target]:
            for p in fig.subplots.values():p.axes.plot([1,2],[3,4])
        source.edit_property('panel/left','Plot area/bounds',[60.,50.,300,300]);state=source.get_settings()
        t=source.extract_style();before=target.shared_axes
        target.apply_style(t,layout=True,panel_map={0:'b',1:'a'})
        result=target.get_settings();layout=result['identity']['layout']
        assert layout['placement']=={'slot_0':'b','slot_1':'a'}
        assert result['config']['chart_area']['x']>result['config']['subplots'][0]['config']['chart_area']['x']
        assert result['config']['subplots'][0]['config']['left_y']['out_margin']==pytest.approx(state['config']['left_y']['out_margin'])
        assert layout['gap']==pytest.approx(12)
        assert target.shared_axes==before


@pytest.mark.parametrize('backend',BACKENDS)
def test_shared_scale_conflict_and_incompatible_style_fail_before_commit(backend):
    with fg.Figure(backend=backend,grid=[['l','r']]) as source,fg.Figure(backend=backend,grid=[['a','b']]) as target:
        for fig in [source,target]:
            for i,p in enumerate(fig.subplots.values()):p.axes.plot([1+10*i,2+10*i],[1,2])
        target.share_axes('x',['a','b']);before=target.get_settings()
        with pytest.raises(ValueError,match='shared-axis'):target.apply_style(source.extract_style(scales=True),scales=True)
        assert target.get_settings()==before
        token=fg.StyleToken(dict(colormap='Magma'))
        with pytest.raises(ValueError,match='incompatible'):target.apply_style(token,strict=True)
        assert target.get_settings()==before


@pytest.mark.parametrize('backend',BACKENDS)
def test_series_mapping_does_not_use_source_ids_or_reconnect_columns(backend):
    with fg.Figure(backend=backend) as source,fg.Figure(backend=backend) as target:
        source.axes[0].plot([1,2],[3,4],color='red',id='src-red',label='Red')
        source.axes[0].plot([1,2],[4,3],color='blue',id='src-blue',label='Blue')
        target.axes[0].plot([10,20],[30,40],id='a',label='A')
        target.axes[0].plot([10,20],[40,30],id='b',label='B')
        token=source.extract_style(text=True);target.apply_style(token,series_map={0:'b',1:'a'},text={'legend_labels'})
        series=target.get_settings()['series']
        assert [s['series_id'] for s in series]==['a','b']
        assert [s['x_column'] for s in series]==['a/x','b/x']
        assert series[1]['render_type']['Line']['line']['line_color']['r']==1
        assert ''.join(c['text'] for c in series[1]['label']['segments'])=='Red'


@pytest.mark.parametrize('backend',BACKENDS)
def test_annotations_keep_distinct_styles_and_destination_geometry_and_text(backend):
    with fg.Figure(backend=backend) as source,fg.Figure(backend=backend) as target:
        for fig in [source,target]:fig.axes[0].plot([1,2],[3,4])
        source.axes[0].text(.1,.2,'source one',coords='ratio',color='red',fontsize=8)
        source.axes[0].text(.4,.5,'source two',coords='ratio',color='blue',fontsize=16)
        target.axes[0].text(.2,.3,'keep one',coords='ratio',id='one')
        target.axes[0].text(.6,.7,'keep two',coords='ratio',id='two')
        before=copy.deepcopy(target.get_settings()['config']['annotations']['items'])
        target.apply_style(source.extract_style())
        items=target.get_settings()['config']['annotations']['items']
        assert [v['id'] for v in items]==['one','two']
        for a,b in zip(items,before):
            assert a['kind']['Text']['anchor']==b['kind']['Text']['anchor']
            assert a['kind']['Text']['text']['segments']==b['kind']['Text']['text']['segments']
        assert items[1]['kind']['Text']['text']['font_size']==pytest.approx(2*items[0]['kind']['Text']['text']['font_size'])


def test_native_and_notebook_accept_the_same_style_document():
    states=[]
    for backend in BACKENDS:
        with fg.Figure(backend=backend,id='same') as fig:
            populate(fig,'line');fig.apply_style('dark');states.append(fig.get_settings())
    assert states[0]==states[1]


@pytest.mark.parametrize('mode',['sketch','milkyway','constellation'])
def test_extracted_draw_styles_replace_mode_without_importing_plot_kind(mode):
    with fg.Figure() as source,fg.Figure() as target:

        if mode=='milkyway':
            source.axes[0].plot([1,2],[3,4]);target.axes[0].plot([10,20],[30,40])
        else:populate(source,'line');populate(target,'line')
        source.set_draw_style(mode);target.set_draw_style('sketch')
        target.apply_style(source.extract_style())
        assert target.get_settings()['config']['draw_style']==source.get_settings()['config']['draw_style']
        target.render_rgba()


def test_default_white_precise_extraction_replaces_dark_sketch_appearance():
    with fg.Figure() as source,fg.Figure() as target:
        populate(source,'line');populate(target,'line')
        target.apply_style('dark');target.set_draw_style('sketch')
        target.apply_style(source.extract_style())
        state=target.get_settings()
        assert state.get('background',dict(r=1,g=1,b=1,a=1))==dict(r=1,g=1,b=1,a=1)
        assert state['config'].get('draw_style',dict(mode='precise'))['mode']=='precise'


@pytest.mark.parametrize('kind',['line','bar','pie'])
def test_common_typography_override_is_effective_after_extraction(kind):
    with fg.Figure(dpi=144) as fig:
        populate(fig,kind);t=fig.extract_style()
        t.appearance['typography']=dict(font_size=15,title_size=23,color='#551188')
        fig.apply_style(t)
        s=fig.get_settings()
        assert s['config']['chart_title']['text']['font_size']==46
        if kind!='line':
            chart=s['categorical' if kind=='bar' else 'radial']
            assert chart['font_size']==30
            assert chart['chart_title']['text']['font_size']==46
        else:assert s['config']['left_y']['label_style']['font_size']==30


@pytest.mark.parametrize('backend',BACKENDS)
def test_colormap_recolors_mapped_data_and_keeps_normalization_and_columns(backend):
    with fg.Figure(backend=backend) as fig:
        populate(fig,'mapped');before=fig.get_settings()
        if backend=='native':image=fig.render_rgba()
        token=fg.StyleToken(dict(colormap='magma'))
        fig.apply_style(token,strict=True);after=fig.get_settings()
        assert after['config']['colorbar']['colormap']=='Magma'
        assert after['config']['colorbar']['axis']==before['config']['colorbar']['axis']
        assert after['series']==before['series']
        if backend=='native':
            rendered=fig.render_rgba()
            x,y,w,h=map(round,json.loads(fig._native.bounds_json('data_area'))['rect'])
            # The plot interior must recolor as well as the bar outside it.
            assert not np.array_equal(image[y:y+h,x:x+w],rendered[y:y+h,x:x+w])


def test_invalid_renderer_style_combination_is_atomic():
    with fg.Figure() as source,fg.Figure() as target:
        source.axes[0].plot([1,2],[3,4]);source.set_draw_style('milkyway')
        populate(target,'line');before=target.get_settings()
        # Marker lines cannot use this renderer material. Do not remove markers
        # or convert the chart type merely to make a style compatible.
        with pytest.warns(fg.StyleWarning,match='no ScatterLine'):
            with pytest.raises(ValueError,match='line-only'):target.apply_style(source.extract_style())
        assert target.get_settings()==before


def test_renderer_font_limit_is_reported_without_partial_application():
    with fg.Figure(dpi=144) as fig:
        populate(fig,'bar');before=fig.get_settings()
        token=fg.StyleToken(dict(typography=dict(font_size=17)))
        with pytest.raises(ValueError,match='8..32 logical pixels'):fig.apply_style(token)
        assert fig.get_settings()==before


def test_captured_implicit_auto_ticks_stay_auto_when_imported():
    with fg.Figure() as source,fg.Figure() as target:
        populate(source,'line');populate(target,'line')
        token=source.extract_style(scales=True)
        assert token.scales['panels'][0]['axes']['bottom_x']['tick_mode']=='Auto'
        target.apply_scales(token.scales)
        assert target.get_settings()['identity']['tick_modes']['main']['bottom_x']=='Auto'
        source.configure(config={'bottom_x':{'major_spacing':.25}})
        target.apply_scales(source.extract_style(scales=True).scales)
        assert target.get_settings()['identity']['tick_modes']['main']['bottom_x']=='Fixed'


def test_preset_base_font_adjusts_all_roles_with_relative_hierarchy():
    with fg.Figure(dpi=144) as fig:
        populate(fig,'line');token=fg.styles.preset('paper')
        token.appearance['typography']['font_size']=15
        fig.apply_style(token)
        cfg=fig.get_settings()['config']
        assert cfg['left_y']['label_style']['font_size']==30
        assert cfg['chart_title']['text']['font_size']==pytest.approx(30*14/11)
        assert cfg['legend']['content']['font_size']==pytest.approx(30*10/11)
