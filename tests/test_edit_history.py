"""Persistent state, stale revisions and real undo branches across both models."""
import copy
import pytest
import figgyplot as fg


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_undo_redo_restores_real_styles_and_keeps_resident_columns(backend):
    with fg.Figure(backend=backend,id='history') as fig:
        fig.axes[0].plot([0,1,2],[2,4,3],id='signal',label='Signal')
        before=fig.get_settings();uploads=fig.info.get('column_uploads',fig.info.get('columns'))
        fig.configure(series={'signal':{'render_type':{'Line':{'line':{'line_width':7}}}}})
        after=fig.get_settings();revision=fig.revision
        operation=fig.edit_operations()[-1]
        assert operation['revision']==revision
        assert operation['base_revision']<revision
        width=next(c for c in operation['changes'] if c['path'].endswith('/line_width'))
        assert width['object_id']=='figure/history/series/signal'
        assert width['before']==before['series'][0]['render_type']['Line']['line']['line_width']
        assert width['after']==7
        fig.undo(expected_revision=revision)
        assert fig.get_settings()==before
        assert fig.revision>revision and fig.edit_history['can_redo']
        fig.redo(expected_revision=fig.revision)
        assert fig.get_settings()==after
        assert fig.info.get('column_uploads',fig.info.get('columns'))==uploads


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_invalid_stale_and_noop_edits_do_not_create_history(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1],[1,2],id='signal')
        fig.configure(config={'chart_title':{'offset_x':12}})
        before=fig.get_settings();history=fig.edit_history;revision=fig.revision
        bad=copy.deepcopy(before);bad['config']['bottom_x']['min']=bad['config']['bottom_x']['max']
        with pytest.raises(ValueError):fig.apply_settings(bad)
        with pytest.raises(ValueError,match='stale'):fig.undo(expected_revision=revision-1)
        fig.apply_settings(before)
        assert fig.get_settings()==before and fig.revision==revision and fig.edit_history==history
        fig.undo();fig.configure(config={'chart_title':{'offset_x':33}})
        assert not fig.edit_history['can_redo']
        with pytest.raises(ValueError,match='nothing to redo'):fig.redo()


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_one_continuous_gesture_is_one_operation_and_selection_is_transient(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1],[1,2],id='signal')
        before=fig.get_settings();count=fig.edit_history['undo_count']
        fig._native.begin_edit('Move title')
        for offset in (3,8,14,27):fig.configure(config={'chart_title':{'offset_x':offset}})
        fig._native.end_edit()
        assert fig.edit_history['undo_count']==count+1
        assert fig.edit_operations()[-1]['label']=='Move title'
        after=fig.get_settings()
        state=copy.deepcopy(after);state['config']['active_layer']='Annotations';fig.apply_settings(state)
        assert fig.edit_history['undo_count']==count+1
        expected=copy.deepcopy(before);expected['config']['active_layer']='Annotations'
        fig.undo();assert fig.get_settings()==expected
        expected=copy.deepcopy(after);expected['config']['active_layer']='Annotations'
        fig.redo();assert fig.get_settings()==expected


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('kind',['radial','categorical','boxplot','radar'])
def test_bounded_history_restores_authored_document_and_ignores_selection(backend,kind):
    with fg.Figure(backend=backend) as fig:
        ax=fig.axes[0]
        if kind=='radial':ax.donut([3,2,1])
        elif kind=='categorical':ax.bar(['A','B'],[3,5])
        elif kind=='boxplot':ax.boxplot([[1,2,3],[2,4,6]])
        else:ax.radar(['A','B','C'],[[2,3,4]])
        before=fig.get_settings()
        fig.update('chart_title',text='Updated')
        after=fig.get_settings();count=fig.edit_history['undo_count']
        state=copy.deepcopy(after)
        state[kind]['active_layer']='Annotations'
        if kind=='radial':state[kind]['interaction'].update(hovered={'group':0,'index':1},hover_progress=.5)
        fig.apply_settings(state)
        assert fig.edit_history['undo_count']==count
        expected=copy.deepcopy(before);expected[kind]['active_layer']='Annotations'
        fig.undo();assert fig.get_settings()==expected
        expected=copy.deepcopy(after);expected[kind]['active_layer']='Annotations'
        fig.redo();assert fig.get_settings()==expected


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_shared_panel_history_and_independent_figures(backend):
    with fg.Figure(backend=backend,id='first',grid=[['left','right']]) as fig, fg.Figure(backend=backend,id='other') as other:
        fig.subplots['left'].axes.plot([0,1],[1,3],id='a')
        fig.subplots['right'].axes.plot([0,1],[2,4],id='b')
        fig.share_axes('x',['left','right'],id='shared')
        before=fig.get_settings();other_before=other.get_settings()
        fig.subplots['right'].axes.set_xlim(-2,5)
        after=fig.get_settings()
        fig.undo();assert fig.get_settings()==before
        fig.redo();assert fig.get_settings()==after
        assert other.get_settings()==other_before and not other.edit_history['can_undo']


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_reset_uses_the_marked_presentation_and_is_itself_undoable(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1],[1,3],id='signal')
        fig.axes[0].set_title('Authored title')
        fig.mark_edit_baseline();before=fig.get_settings();count=fig.edit_history['undo_count']
        assert not fig.edit_history['can_reset']
        fig.configure(series={'signal':{'render_type':{'Line':{'line':{'line_width':9}}}}})
        fig.update('chart_title',text='Review edit');edited=fig.get_settings()
        fig.reset_edits(expected_revision=fig.revision)
        assert fig.get_settings()==before and not fig.edit_history['can_reset']
        assert fig.edit_history['undo_count']==count+3
        assert fig.edit_operations()[-1]['label']=='Reset edits'
        fig.undo();assert fig.get_settings()==edited
        fig.redo();assert fig.get_settings()==before

@pytest.mark.parametrize('backend',['native','webgpu'])
def test_gui_commit_boundary_retires_ids_but_explicit_history_can_restore_them(backend):
    import json
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1],[1,2]);fig.axes[0].text(.3,.4,'Probe',coords='ratio',id='probe')
        fig.mark_edit_baseline();before=fig.get_settings()
        removed=copy.deepcopy(before);removed['config']['annotations']['items']=[]
        fig._native.apply_settings(json.dumps(removed))  # GUI uses this validated boundary too.
        after=fig.get_settings();assert 'annotation/probe' in after['identity']['retired']
        with pytest.raises(ValueError,match='retired'):fig._native.apply_settings(json.dumps(before))
        assert fig.get_settings()==after
        fig.undo();assert fig.get_settings()==before
        fig.redo();assert fig.get_settings()==after
        fig.reset_edits();assert fig.get_settings()==before
        fig.undo();assert fig.get_settings()==after


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_reset_availability_remains_correct_when_undo_crosses_a_new_baseline(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1],[1,2]);fig.update('chart_title',text='Presentation')
        fig.mark_edit_baseline();baseline=fig.get_settings();assert not fig.edit_history['can_reset']
        fig.undo();assert fig.edit_history['can_reset']
        fig.reset_edits();assert fig.get_settings()==baseline and not fig.edit_history['can_reset']
