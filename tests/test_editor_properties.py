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
