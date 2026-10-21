"""The same stable-object commands drive Python and both property inspectors."""
import copy
import pytest
import figgyplot as fg


def object_for(fig,target):
    return next(v for v in fig.editor_properties() if v['target']==target)


def edit(fig,target,property_id,value):
    owner=object_for(fig,target)
    return fig.edit_property(owner['id'],property_id,value,expected_revision=fig.revision)


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('kind',['line','vector','histogram','contour'])
def test_contextual_styles_have_real_commands_and_replay(backend,kind):
    with fg.Figure(backend=backend,id='property') as fig:
        ax=fig.axes[0]
        if kind=='line':
            ax.plot([0,1,2],[1,3,2],id='signal');prop='Line/interpolation';value='StepMid';path=['Line','line','interpolation']
        elif kind=='vector':
            ax.quiver([0,1],[1,2],[2,1],[1,3],id='signal');prop='Vectors/head_width_px';value=14;path=['Vector','style','head_width_px']
        elif kind=='histogram':
            ax.hist([0,1,1,2],id='signal');prop='Bars/baseline';value=-1;path=['Histogram','bar','baseline']
        else:
            ax.contour([[0,1],[2,3]],levels=[.5,1.5,2.5],id='signal');prop='Contours/levels';value=[.75,1.25,2.25];path=['Contour','contour','levels']
        before=fig.get_settings();count=fig.edit_history['undo_count']
        owner=object_for(fig,'signal')
        assert len({v['id'] for v in owner['fields']})==len(owner['fields'])
        assert any(v['id']==prop for v in owner['fields'])
        edit(fig,'signal',prop,value)
        result=fig.get_settings()['series'][0]['render_type']
        for key in path:result=result[key]
        assert result==value
        after=fig.get_settings()
        assert fig.edit_history['undo_count']==count+1
        fig.undo();assert fig.get_settings()==before
        fig.redo();assert fig.get_settings()==after
        exec(fig.to_code(),{'fig':fig})
        assert fig.get_settings()==after


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_enable_contour_labels_then_edit_their_typography(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].contour([[0,1],[2,3]],levels=[.5,1.5,2.5],id='field')
        before=fig.get_settings()
        edit(fig,'field','Contours/show_labels',True)
        edit(fig,'field','Contour labels/font_size',18)
        state=fig.get_settings()['series'][0]['render_type']['Contour']['contour']
        assert state['labels']['visible'] and state['labels']['font_size']==18
        edit(fig,'field','Contours/show_labels',False)
        assert 'labels' not in fig.get_settings()['series'][0]['render_type']['Contour']['contour']
        fig.undo();assert fig.get_settings()['series'][0]['render_type']['Contour']['contour']['labels']['font_size']==18
        fig.undo();fig.undo();assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_area_fill_is_explicit_and_can_be_removed_without_touching_arrays(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1,2],[1,3,2],id='signal')
        before=fig.get_settings()
        edit(fig,'signal','Area fill/enabled',True)
        edit(fig,'signal','Line/fill/ToBaseline',-2)
        assert fig.get_settings()['series'][0]['render_type']['Line']['line']['fill']=={'ToBaseline':-2}
        edit(fig,'signal','Area fill/enabled',False)
        assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_grid_weights_and_gap_reflow_named_panels_atomically(backend):
    with fg.Figure(backend=backend,id='layout',grid=[['left','right']]) as fig:
        before=fig.get_settings()
        edit(fig,'figure','Figure grid/column_weights',[1,2])
        state=fig.get_settings();left=state['config']['chart_area'];right=state['config']['subplots'][0]['config']['chart_area']
        assert right['width']==2*left['width']
        assert left['width']+right['width']+state['identity']['layout']['gap']==960
        owner=object_for(fig,'figure');revision=fig.revision;history=fig.edit_history
        with pytest.raises(ValueError,match='100 logical|gaps'):
            fig.edit_property(owner['id'],'Figure grid/gap',900,expected_revision=revision)
        assert fig.get_settings()==state and fig.revision==revision and fig.edit_history==history
        fig.undo();assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_wrong_owner_bad_choice_stale_revision_preserve_the_complete_document(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1],[1,2],id='signal')
        before=fig.get_settings();revision=fig.revision;history=fig.edit_history
        owner=object_for(fig,'signal')
        for oid,pid,value in [('missing','Line/line_width',4),(owner['id'],'Line/line_style','bogus'),(owner['id'],'Line/x_column','other')]:
            with pytest.raises(ValueError):fig.edit_property(oid,pid,value,expected_revision=revision)
        with pytest.raises(ValueError,match='stale'):fig.edit_property(owner['id'],'Line/line_width',7,expected_revision=revision-1)
        assert fig.get_settings()==before and fig.revision==revision and fig.edit_history==history


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_catalog_explains_fixed_colors_and_sparse_overrides(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].scatter([0,1],[1,2],id='fixed')
        fig.axes[0].scatter([0,1],[2,3],c=[1,2],id='mapped')
        assert any('fixed RGB' in v for v in object_for(fig,'fixed')['notices'])
        assert any('Colors use mapped/color' in v for v in object_for(fig,'mapped')['notices'])
        before=copy.deepcopy(fig.get_settings())
        fig.editor_properties()
        assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_value_mapping_uses_resident_extents_and_preserves_explicit_overrides(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].scatter([0,1,2],[10,30,20],id='signal')
        before=fig.get_settings()
        edit(fig,'signal','Color mapping/source','signal/y')
        state=fig.get_settings()
        assert state['series'][0]['render_type']['Scatter']['scatter']['point_color_map']=={'column':'signal/y'}
        assert [state['config']['colorbar']['axis'][k] for k in ('min','max')]==[10,30]
        edit(fig,'signal','Size mapping/source','signal/y')
        size=fig.get_settings()['series'][0]['render_type']['Scatter']['scatter']['point_size_map']
        assert [size[k] for k in ('domain_min','domain_max')]==[10,30]
        fig.configure(series={'signal':{'render_type':{'Scatter':{'scatter':{'point_style_overrides':[{'index':1,'point_color':{'r':1.,'g':0.,'b':0.,'a':1.}}]}}}}})
        current=fig.get_settings();edit(fig,'signal','Color scale/colormap','Magma')
        assert fig.get_settings()['series'][0]==current['series'][0]
        assert '1 explicit' in ' '.join(object_for(fig,'signal')['notices'])
        fig.undo();fig.undo();fig.undo();fig.undo()
        assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_named_grid_slot_swap_retains_ids_and_is_undoable(backend):
    with fg.Figure(backend=backend,id='slots',grid=[['left','right']]) as fig:
        before=fig.get_settings()
        edit(fig,'figure','Figure grid/slot/left','right')
        state=fig.get_settings()
        assert state['identity']['layout']['placement']=={'left':'right','right':'left'}
        assert state['identity']['panels']==before['identity']['panels']
        assert state['config']['chart_area']['x']==486
        fig.undo();assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_vector_scale_mode_exposes_the_new_units(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].quiver([0,1],[1,2],[2,1],[1,3],id='signal')
        edit(fig,'signal','Vectors/scale_mode','Data')
        edit(fig,'signal','Vectors/scale/Data/factor',2)
        assert fig.get_settings()['series'][0]['render_type']['Vector']['style']['scale']=={'Data':{'factor':2}}
        edit(fig,'signal','Vectors/scale_mode','Pixels')
        assert fig.get_settings()['series'][0]['render_type']['Vector']['style']['scale']=={'Pixels':{'px_per_unit':1}}


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('kind',['cartesian','categorical','boxplot'])
def test_annotation_coordinates_convert_using_the_actual_axis_contract(backend,kind):
    with fg.Figure(backend=backend) as fig:
        ax=fig.axes[0]
        if kind=='cartesian':
            ax.plot([0,10],[0,20],id='signal');ax.set_xlim(0,10);ax.set_ylim(0,20);x,y=2,5;ratio=(.2,.75);owner='config'
        elif kind=='categorical':
            ax.bar(['A','B'],[5,10]);x,y=0,5;ratio=(.25,2/3);owner=kind
        else:
            ax.boxplot([[1,2,3],[2,4,6]]);fig.configure_bounded('boxplot',value_range=[0,10]);x,y=0,5;ratio=(.25,.5);owner=kind
        ax.text(x,y,'Probe',coords='data',id='probe')
        before=fig.get_settings();target='annotation:probe' if kind=='cartesian' else 'annotation_0'
        edit(fig,target,'Coordinates/anchor','Ratio')
        anchor=fig.get_settings()[owner]['annotations']['items'][0]['kind']['Text']['anchor']
        assert [anchor['Ratio'][key] for key in ('x','y')]==pytest.approx(ratio,abs=1e-7)
        edit(fig,target,'Coordinates/anchor','Data')
        anchor=fig.get_settings()[owner]['annotations']['items'][0]['kind']['Text']['anchor']
        assert [anchor['Data'][key] for key in ('x','y')]==pytest.approx([x,y],abs=1e-6)
        fig.undo();fig.undo();assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_annotation_order_tracks_stable_ids_and_restores_bounded_selection(backend):
    with fg.Figure(backend=backend) as fig:
        ax=fig.axes[0];ax.boxplot([[1,2,3],[2,4,6]])
        ax.text(.2,.3,'First',coords='ratio',id='first');ax.text(.4,.5,'Second',coords='ratio',id='second')
        state=fig.get_settings();state['boxplot']['active_layer']='Annotations';state['boxplot']['decorations']['selected']={'Annotation':0};fig.apply_settings(state)
        before=fig.get_settings();stable=object_for(fig,'annotation_0')['id']
        fig.edit_property(stable,'Annotation/order',2,expected_revision=fig.revision)
        after=fig.get_settings()
        assert [v['id'] for v in after['boxplot']['annotations']['items']]==['second','first']
        assert after['boxplot']['decorations']['selected']=={'Annotation':1}
        assert fig.editor_properties(stable)['target']=='annotation_1'
        fig.undo();assert fig.get_settings()==before
        fig.redo();assert fig.get_settings()==after


def test_compact_inspector_transport_resolves_to_the_complete_property_catalog():
    import json
    from figgyplot._native import editor_catalog_json
    with fg.Figure(backend='webgpu') as fig:
        fig.axes[0].scatter([0,1],[1,2],c=[2,3],id='first')
        fig.axes[0].scatter([0,1],[3,4],id='second')
        full=fig.editor_properties();compact=json.loads(editor_catalog_json(json.dumps(fig.get_settings()),compact=True))
        resolved=copy.deepcopy(compact['objects'])
        refs=0
        for owner in resolved:
            for field in owner['fields']:
                if field.pop('choices_ref',None)=='columns':field['choices']+=compact['columns'];refs+=1
        assert refs==6 and len(set(compact['columns']))==len(compact['columns'])
        assert resolved==full

@pytest.mark.parametrize('backend',['native','webgpu'])
def test_optional_shapes_palettes_and_label_placements_have_controls(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].scatter([0,1],[1,2],id='points')
        owner=object_for(fig,'points')
        for group in ('Marker palette','Marker point overrides'):
            action=next(v for v in fig.editor_properties(owner['id'])['fields'] if v['id']==group+'/add')
            fig.edit_property(owner['id'],action['id'],True,expected_revision=fig.revision)
        edit(fig,'points','Marker palette/entry/1/override/point_size',True)
        edit(fig,'points','Marker palette/entry/1/point_size',9)
        edit(fig,'points','Marker palette/source','points/x')
        state=fig.get_settings()['series'][0]['render_type']['Scatter']['scatter']
        assert state['point_style_table'][0]['point_size']==9
        assert state['point_style_index_column']=='points/x'
        assert state['point_style_overrides'][0]['index']==0
        action=next(v for v in fig.editor_properties(owner['id'])['fields'] if v['id']=='Marker point overrides/remove/0')
        fig.edit_property(owner['id'],action['id'],True,expected_revision=fig.revision)
        assert not fig.get_settings()['series'][0]['render_type']['Scatter']['scatter'].get('point_style_overrides')
        fig.undo();assert fig.get_settings()['series'][0]['render_type']['Scatter']['scatter']['point_style_overrides'][0]['index']==0
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].pie([3,2,1]);edit(fig,'data_area','Pie / donut/mode','Donut')
        assert fig.get_settings()['radial']['kind']=={'Donut':{'inner_radius':.5}}
        edit(fig,'data_area','Pie / donut/Donut/inner_radius',.6)
        assert fig.get_settings()['radial']['kind']['Donut']['inner_radius']==pytest.approx(.6)
        edit(fig,'data_area','Pie / donut/mode','Pie');assert fig.get_settings()['radial']['kind']=='Pie'
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].contour([[0,1],[2,3]],levels=[.5,1.5,2.5],id='field')
        edit(fig,'field','Contours/level_colors',True)
        assert len(fig.get_settings()['series'][0]['render_type']['Contour']['contour']['per_level_color'])==3
        edit(fig,'field','Contours/show_labels',True);edit(fig,'field','Contour labels/background',True)
        owner=object_for(fig,'field');action=next(v for v in owner['fields'] if v['id']=='Label positions/add')
        fig.edit_property(owner['id'],action['id'],True,expected_revision=fig.revision)
        edit(fig,'field','Label positions/entry/1/x',.25)
        labels=fig.get_settings()['series'][0]['render_type']['Contour']['contour']['labels']
        assert labels['bg_color']['a']==1 and labels['anchors'][0]['x']==.25


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_shared_axis_command_adopts_target_range_and_detaches_without_restyling(backend):
    with fg.Figure(backend=backend,id='links',grid=[['left','middle','right']]) as fig:
        for name in ('left','middle','right'):fig.subplots[name].axes.plot([1,2],[2,3],id=name+'/data')
        fig.subplots['right'].axes.set_xlim(-5,15)
        before=fig.get_settings()
        left=next(v for v in fig.editor_properties() if v['id']=='panel/left')
        fig.edit_property(left['id'],'Shared axes/x','right',expected_revision=fig.revision)
        after=fig.get_settings()
        assert after['config']['subplots'][1]['link_x']=='Parent'
        assert [after['config']['bottom_x'][k] for k in ('min','max')]==[-5,15]
        assert after['config']['bottom_x']['label_style']==before['config']['bottom_x']['label_style']
        fig.subplots['right'].axes.set_xlim(-10,20)
        assert fig.get_settings()['config']['bottom_x']['min']==-10
        fig.edit_property(left['id'],'Shared axes/x','',expected_revision=fig.revision)
        detached=fig.get_settings();assert detached['config']['subplots'][1].get('link_x') is None
        assert not detached['identity']['groups']
        fig.undo();assert fig.get_settings()['config']['subplots'][1]['link_x']=='Parent'


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_vector_color_source_uses_the_same_panel_scale_command(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].quiver([0,1],[1,2],[2,1],[1,3],id='arrows')
        edit(fig,'arrows','Color mapping/source','arrows/u')
        state=fig.get_settings();assert state['series'][0]['render_type']['Vector']['style']['color_map']=={'Column':'arrows/u'}
        assert [state['config']['colorbar']['axis'][k] for k in ('min','max')]==[1,2]
        edit(fig,'arrows','Color scale/colormap','Turbo')
        assert fig.get_settings()['config']['colorbar']['colormap']=='Turbo'

@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('family',['radial','categorical','boxplot','radar'])
def test_independent_bounded_styles_can_be_enabled_and_return_to_inheritance(backend,family):
    with fg.Figure(backend=backend) as fig:
        ax=fig.axes[0]
        if family=='radial':ax.pie([3,2,1])
        elif family=='categorical':ax.bar(['A','B'],[3,5])
        elif family=='boxplot':ax.boxplot([[1,2,3],[2,4,6]])
        else:ax.radar(['A','B','C'],[[2,3,4]])
        owner=next(v for v in fig.editor_properties() if v['id'].startswith('bounded/series/'))
        before=fig.get_settings()
        fig.edit_property(owner['id'],'Series style/custom',True,expected_revision=fig.revision)
        item=fig.get_settings()[family]['slices' if family=='radial' else 'series'][0]
        assert isinstance(item['style'],dict)
        if family in ('categorical','boxplot'):
            state=fig.get_settings();state[family]['selected']={'series_id':state[family]['series'][0]['id'],'category_id':state[family]['categories'][1]['id']};fig.apply_settings(state)
            fig.edit_property(owner['id'],'Selected item/custom',True,expected_revision=fig.revision)
            item=fig.get_settings()[family]['overrides'][0]
            assert item['target']['category_id']==state[family]['categories'][1]['id']
            fig.edit_property(owner['id'],'Selected item/style/texture_strength',.6,expected_revision=fig.revision)
            assert fig.get_settings()[family]['overrides'][0]['style']['texture_strength']==pytest.approx(.6)
            fig.edit_property(owner['id'],'Selected item/custom',False,expected_revision=fig.revision)
            assert fig.get_settings()[family]['overrides']==[]
        fig.edit_property(owner['id'],'Series style/custom',False,expected_revision=fig.revision)
        assert fig.get_settings()[family]['slices' if family=='radial' else 'series'][0].get('style') is None


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_polar_optional_controls_and_grid_vector_colors(backend):
    with fg.Figure(backend=backend) as fig:
        ax=fig.axes[0];ax.plot([0,90,180],[1,2,1],id='polar');ax.set_polar()
        edit(fig,'data_area','Polar coordinates/interpolation_mode','Arc')
        edit(fig,'data_area','Polar coordinates/interpolation/Arc/pieces',8)
        edit(fig,'data_area','Polar coordinates/limit_sector',True)
        edit(fig,'data_area','Polar coordinates/sector',[0,180])
        assert fig.get_settings()['config']['polar']['interpolation']=={'Arc':{'pieces':8}}
        assert fig.get_settings()['config']['polar']['sector']==[0,180]
        edit(fig,'data_area','Polar coordinates/limit_sector',False)
        assert fig.get_settings()['config']['polar'].get('sector') is None
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].quiver([0,1],[1,2],[[1,2],[3,4]],[[2,1],[4,3]],id='grid')
        edit(fig,'grid','Color mapping/grid_source','Horizontal component')
        state=fig.get_settings();vector=state['series'][0]['render_type']['Vector']
        assert vector['style']['color_map']['Grid']==vector['components']['Grid']['u']
        assert [state['config']['colorbar']['axis'][k] for k in ('min','max')]==[1,4]
        edit(fig,'grid','Color mapping/grid_source','Fixed')
        assert fig.get_settings()['series'][0]['render_type']['Vector']['style'].get('color_map') is None

@pytest.mark.parametrize('backend',['native','webgpu'])
def test_timestamp_format_modes_are_typed_commands_and_preserve_numeric_domains(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1,2],[1,3,2],id='signal')
        owner=object_for(fig,'tick_labels_bottom');before=fig.get_settings()
        field=next(v for v in owner['fields'] if v['path'].endswith('/format'))
        prefix=field['id']+'/Timestamp/'
        fig.edit_property(owner['id'],field['id'],'Timestamp',expected_revision=fig.revision)
        for prop,value in [('timezone/mode','FixedOffsetMinutes'),('timezone/FixedOffsetMinutes',540),('label/mode','Pattern'),('label/Pattern','%Y-%m-%d %H:%M'),('fractional/mode','Fixed'),('fractional/Fixed',2),('tick_policy','NumericSpacing')]:
            fig.edit_property(owner['id'],prefix+prop,value,expected_revision=fig.revision)
        axis=fig.get_settings()['config']['bottom_x'];stamp=axis['label_style']['format']['Timestamp']
        assert stamp['timezone']=={'FixedOffsetMinutes':540}
        assert stamp['label']=={'Pattern':'%Y-%m-%d %H:%M'} and stamp['fractional']=={'Fixed':2}
        for key in ('min','max','major_spacing','scale'):assert axis[key]==before['config']['bottom_x'][key]
        for _ in range(8):fig.undo()
        assert fig.get_settings()==before

@pytest.mark.parametrize('backend',['native','webgpu'])
def test_semantic_tick_spacing_resolves_its_owner_independently_of_active_panel(backend):
    with fg.Figure(backend=backend,grid=[['left','right']]) as fig:
        fig.subplots['left'].axes.plot([0,10],[0,10],id='left/data')
        fig.subplots['right'].axes.plot([0,10],[0,10],id='right/data')
        fig.share_axes('x',['left','right'])
        before=fig.get_settings();owner=next(v for v in fig.editor_properties() if v['id']=='panel/right/axis_bottom')
        prop=next(v['id'] for v in owner['fields'] if v['path'].endswith('/major_spacing'))
        fig.edit_property(owner['id'],prop,2,expected_revision=fig.revision)
        state=fig.get_settings()
        assert state['identity']['tick_modes']['left']['bottom_x']=='Fixed'
        assert state['identity']['tick_modes']['right']['bottom_x']=='Fixed'
        assert state['config']['bottom_x']['major_spacing']==state['config']['subplots'][0]['config']['bottom_x']['major_spacing']==2
        assert state['config'].get('active_layer')==before['config'].get('active_layer')
        fig.undo();assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_slice_optional_label_controls_remain_booleans_and_materialize_colors(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].pie([3,2,1]);owner=next(v for v in fig.editor_properties() if v['id']=='bounded/series/slice_0_0')
        for prop in ('custom_labels','custom_label_format','custom_label_color'):
            field=next(v for v in fig.editor_properties(owner['id'])['fields'] if v['id']=='Slice labels/'+prop)
            assert field['kind']=='boolean' and not field['choices']
            fig.edit_property(owner['id'],field['id'],True,expected_revision=fig.revision)
        item=fig.get_settings()['radial']['slices'][0]
        assert item['labels'] is not None and item['label_format'] is not None and item['label_color']['a']==1

@pytest.mark.parametrize('backend',['native','webgpu'])
def test_axis_membership_preserves_existing_group_ids_and_noop_commands(backend):
    with fg.Figure(backend=backend,grid=[['a','b','c','d']]) as fig:
        for name in ('a','b','c','d'):fig.subplots[name].axes.plot([0,1],[1,2],id=name+'/data')
        fig.share_axes('x',['a','b','c'],id='time');fig.share_axes('y',['c','d'],id='temperature')
        owner=fig.editor_properties('panel/a');before=fig.get_settings();revision=fig.revision;history=fig.edit_history
        current=next(v['value'] for v in owner['fields'] if v['id']=='Shared axes/x')
        fig.edit_property(owner['id'],'Shared axes/x',current,expected_revision=revision)
        assert fig.get_settings()==before and fig.revision==revision and fig.edit_history==history
        fig.edit_property(owner['id'],'Shared axes/x','',expected_revision=fig.revision)
        groups=fig.get_settings()['identity']['groups']
        assert set(groups)=={'time','temperature'} and groups['time']['members']==['b','c']
        assert groups['temperature']==before['identity']['groups']['temperature']
        fig.undo();assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_reapplying_an_enabled_optional_control_preserves_its_custom_values(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].pie([3,2,1]);edit(fig,'data_area','Pie / donut/mode','Donut');edit(fig,'data_area','Pie / donut/Donut/inner_radius',.7)
        before=fig.get_settings();revision=fig.revision;history=fig.edit_history
        edit(fig,'data_area','Pie / donut/mode','Donut')
        assert fig.get_settings()==before and fig.revision==revision and fig.edit_history==history


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_size_only_point_styles_inherit_mapped_colors_until_explicit_override(backend):
    with fg.Figure(backend=backend) as fig:
        ax=fig.axes[0];ax.scatter([0,1,2],[1,1,1],c=[0,.5,1],s=400,id='points');ax.set_xlim(-.5,2.5);ax.set_ylim(0,2)
        before=fig.get_settings();owner=object_for(fig,'points')
        if backend=='native':
            import json
            def colors():
                pixels=fig.render_rgba()[:,:,:3].astype(int)
                x,y,w,h=json.loads(fig._native.bounds_json('data_area'))['rect']
                result=[]
                for i in range(3):
                    cx=round(x+2+(w-4)*(i+.5)/3);cy=round(y+h/2)
                    block=pixels[cy-3:cy+4,cx-3:cx+4].reshape(-1,3)
                    saturation=block.max(axis=1)-block.min(axis=1)
                    opaque=block[saturation==saturation.max()]
                    result.append(opaque[opaque.sum(axis=1).argmin()].tolist())
                return result
            mapped_colors=colors()
        fig.edit_property(owner['id'],'Marker palette/add',True,expected_revision=fig.revision)
        assert fig.get_settings()['series'][0]['render_type']['Scatter']['scatter']['point_style_table']==[{}]
        edit(fig,'points','Marker palette/source','points/x')
        edit(fig,'points','Marker palette/entry/1/override/point_size',True)
        edit(fig,'points','Marker palette/entry/1/point_size',9)
        style=fig.get_settings()['series'][0]['render_type']['Scatter']['scatter']
        assert style['point_style_table']==[{'point_size':9}]
        if backend=='native':assert colors()==mapped_colors
        assert style['point_color_map']==before['series'][0]['render_type']['Scatter']['scatter']['point_color_map']
        edit(fig,'points','Marker palette/entry/1/override/point_color',True)
        assert fig.get_settings()['series'][0]['render_type']['Scatter']['scatter']['point_style_table'][0]['point_color']==style['point_color']
        # The shader's documented order is override > value map > table > base.
        if backend=='native':assert colors()==mapped_colors
        edit(fig,'points','Marker palette/entry/1/override/point_color',False)
        assert fig.get_settings()['series'][0]['render_type']['Scatter']['scatter']['point_style_table']==[{'point_size':9}]
        if backend=='native':assert colors()==mapped_colors
        fig.edit_property(owner['id'],'Marker point overrides/add',True,expected_revision=fig.revision)
        edit(fig,'points','Marker point overrides/entry/1/override/point_color',True)
        if backend=='native':assert colors()[0]!=mapped_colors[0]
        edit(fig,'points','Marker point overrides/entry/1/override/point_color',False)
        if backend=='native':assert colors()==mapped_colors

@pytest.mark.parametrize('backend',['native','webgpu'])
def test_colorbar_title_command_preserves_character_style_and_replays(backend):
    with fg.Figure(backend=backend) as fig:
        ax=fig.axes[0];ax.imshow([[0,1],[2,3]],id='field');ax.set_title('Temperature')
        text=copy.deepcopy(fig.get_settings()['config']['chart_title']['text']);text['segments'][0]['bold']=True
        fig.configure(config={'colorbar':{'axis':{'title_option':{'visible':True,'text':text}}}})
        before=fig.get_settings();owner=fig.editor_properties('panel/main/colorbar_title')
        fig.edit_property(owner['id'],'Title/text/plain_text','Temperature (K)',expected_revision=fig.revision)
        after=fig.get_settings();rich=after['config']['colorbar']['axis']['title_option']['text']
        assert ''.join(v['text'] for v in rich['segments'])=='Temperature (K)' and rich['segments'][0]['bold']
        assert rich['font_size']==text['font_size']
        fig.undo();assert fig.get_settings()==before
        fig.redo();assert fig.get_settings()==after
        exec(fig.to_code(),{'fig':fig});assert fig.get_settings()==after


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_radial_detail_slice_commands_resolve_the_selected_group(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].pie([3,2,1])
        child=copy.deepcopy(fig.get_settings()['radial']['slices'][0]);child.update(value=1,label='Detail A')
        other=copy.deepcopy(child);other.update(value=2,label='Detail B')
        fig.configure_radial(split={'slice_index':0,'children':[child,other],'kind':'Pie'})
        before=fig.get_settings();owner=fig.editor_properties('bounded/series/slice_1_1')
        fig.edit_property(owner['id'],'Series style/custom',True,expected_revision=fig.revision)
        fig.edit_property(owner['id'],'Series style/style/gap_degrees',5,expected_revision=fig.revision)
        fig.edit_property(owner['id'],'Detail shape/mode','Donut',expected_revision=fig.revision)
        after=fig.get_settings();assert after['radial']['split']['kind']=={'Donut':{'inner_radius':.5}}
        assert after['radial']['split']['children'][1]['style']['gap_degrees']==5
        assert after['radial']['split']['children'][0]==before['radial']['split']['children'][0]
        assert after['radial']['slices']==before['radial']['slices']
        fig.undo();fig.undo();fig.undo();assert fig.get_settings()==before
