"""Public feature paths, stable addresses and complete-document replay."""
import copy
import json

import numpy as np
import pytest
import figgyplot as figgy


def populate(figure, feature):
    ax = figure.axes[0]
    if feature == 'mapped_points':
        ax.scatter([0, 1, 2], [2, 1, 3], c=[1, 2, 4], s=[2, 5, 9], id='points')
    elif feature == 'vector_points':
        ax.quiver([0, 1, 2], [0, 2, 1], [1, 0, -1], [0, 1, 1],
                  values=[1, 2, 3], scale=20, pivot='middle', id='arrows')
    elif feature == 'vector_grid':
        ax.quiver([0, 1, 2], [0, 1], [[1, 0, -1], [0, 1, 1]], [[0, 1, 1], [1, 0, -1]],
                  values=[[1, 2, 3], [3, 2, 1]], scale=20, id='arrows')
    elif feature == 'steps':
        ax.step([0, 1, 2, 3], [0, 2, 1, 3], where='mid', id='steps')
    elif feature == 'baseline_fill':
        ax.fill_between([0, 1, 2], [1, 3, 2], .5, id='band')
    elif feature == 'series_fill':
        ax.fill_between([0, 1, 2], [2, 4, 3], [1, 1, 2], id='band')
    elif feature == 'polar':
        ax.set_polar(angle_unit='Radians', clockwise=True)
        ax.plot(np.linspace(0, 2*np.pi, 9), [1, 2, 3, 2, 1, 2, 3, 2, 1], id='orbit')
        ax.text(.4, .4, 'Polar', coords='ratio', id='note')
    elif feature == 'radar':
        ax.radar(['A', 'B', 'C', 'D'], [[1, 2, 4, 3], [4, 2, 1, 3]], labels=['First', 'Second'])
        ax.set_title('Independent title', fontsize=18, color='purple')
    elif feature == 'annotations':
        ax.plot([0, 1, 2], [1, 2, 0], id='signal')
        ax.axhline(1, color='red', id='threshold')
        ax.text(.3, .2, 'Reference', coords='ratio', id='note')
    else:
        raise AssertionError(feature)
    return ax


FEATURES = ['mapped_points', 'vector_points', 'vector_grid', 'steps', 'baseline_fill',
            'series_fill', 'polar', 'radar', 'annotations']


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('feature', FEATURES)
def test_features_round_trip_and_replay_without_reupload(backend, feature):
    with figgy.Figure(backend=backend) as source, figgy.Figure(backend=backend) as target:
        populate(source, feature)
        populate(target, feature)
        state = source.get_settings()
        assert state['schema_version'] == 2
        revision = source.revision
        source.apply_settings(state)
        assert source.revision == revision
        uploads = target.info.get('column_uploads')
        exec(source.to_code(), {'fig': target})
        assert target.get_settings() == state
        assert target.info.get('column_uploads') == uploads
        if backend == 'native':
            image = source.render_rgba()
            assert image.shape == (600, 960, 4)
            assert np.any(image[..., :3] < 150)
            assert np.array_equal(image, target.render_rgba())


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_grid_ownership_shared_ranges_and_stable_placement(backend):
    with figgy.Figure(backend=backend, grid=[['left', 'right'], ['left', 'lower']]) as figure:
        left, right, lower = [figure.subplots[key].axes for key in ('left', 'right', 'lower')]
        left.plot([0, 1], [1, 2], id='temperature')
        right.plot([100, 200], [10, 20], id='pressure')
        lower.scatter([0, 1], [3, 4], id='residual')
        right.set_title('Pressure')
        state = figure.get_settings()
        assert not state['config']['chart_title']['text']['segments']
        assert state['config']['subplots'][0]['series'] == ['pressure']
        assert state['config']['subplots'][0]['config']['left_y']['max'] == pytest.approx(20.5)
        figure.share_axes('x', ['left', 'lower'])
        lower.set_xlim(-5, 5)
        state = figure.get_settings()
        assert state['config']['bottom_x']['min'] == -5
        assert state['config']['subplots'][1]['config']['bottom_x']['max'] == 5
        before = copy.deepcopy(state['config']['subplots'][0]['config'])
        figure.place('right', slot='lower')
        right.set_title('Moved pressure')
        state = figure.get_settings()
        moved = state['config']['subplots'][0]['config']
        assert figure.subplots.placement == {'left': 'left', 'lower': 'right', 'right': 'lower'}
        assert moved['chart_area'] != before['chart_area']
        assert moved['left_y'] == before['left_y']
        assert right.id == 'right' and right.subplot.figure is figure
        if backend == 'native':
            assert figure.render_rgba().shape == (600, 960, 4)
            assert figure.render_rgba(scale=2).shape == (1200, 1920, 4)


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_secondary_y_axis_is_owned_locally_and_replays(backend):
    with figgy.Figure(backend=backend, grid=[['first', 'second']]) as figure:
        ax = figure.subplots['second'].axes
        ax.plot([0, 1], [1, 2], id='primary')
        twin = ax.twinx(id='pressure_axis')
        twin.plot([0, 1], [100, 200], id='secondary')
        twin.set_ylim(50, 250)
        twin.set_ylabel('Pressure')
        state = figure.get_settings()
        panel = state['config']['subplots'][0]
        assert panel['config']['left_y']['max'] < 10
        assert panel['config']['overlays'][0]['y_axis']['max'] == 250
        assert panel['config']['overlays'][0]['series'] == ['secondary']
        assert state['identity']['panels'][1]['overlays'] == ['pressure_axis']
        assert twin.subplot.id == 'second'
        if backend == 'native':
            assert figure.render_rgba(scale=2).shape == (1200, 1920, 4)


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_rejected_combinations_and_stale_edits_are_atomic(backend):
    with figgy.Figure(backend=backend, grid=[['first', 'second']]) as figure:
        ax = figure.subplots['second'].axes
        before, revision = figure.get_settings(), figure.revision
        for call in [lambda: ax.radar(['A', 'B', 'C'], [1, 2, 3]),
                     lambda: ax.text(.5, .5, 'Unsupported', coords='ratio'),
                     lambda: figure.set_layout([['bad', 'other'], ['bad', 'bad']])]:
            with pytest.raises(ValueError):
                call()
            assert figure.get_settings() == before and figure.revision == revision
        ax.set_polar()
        before, revision = figure.get_settings(), figure.revision
        for call in [lambda: ax.twinx(), lambda: ax.quiver([0], [0], [1], [1])]:
            with pytest.raises(ValueError):
                call()
            assert figure.get_settings() == before and figure.revision == revision
        bad = copy.deepcopy(before)
        bad['identity']['panels'][1]['id'] = 'first'
        with pytest.raises(ValueError, match='duplicate'):
            figure.apply_settings(bad)
        assert figure.get_settings() == before


def test_selected_mapped_values_and_vector_components_remain_gpu_owned():
    with figgy.Figure(backend='native') as figure:
        values = np.array([2., 5., 9.])
        figure.axes[0].scatter([0, 1, 2], [1, 2, 3], c=values, s=values, id='mapped')
        state = figure.get_settings()
        state['config']['picked_data'] = {'refs': [{'kind': 'point', 'series_id': 'mapped', 'point_index': 1}]}
        figure.apply_settings(state)
        values[:] = -1
        details = json.loads(figure._native.selection_details_json())
        assert details['color_value'] == details['size_value'] == 5
        assert figure.info['rgba_readbacks'] == 0


def test_single_panel_convenience_and_explicit_legacy_migration():
    with figgy.Figure(backend='webgpu') as figure:
        state = figure.get_settings()
        state.pop('identity')
        state.update(schema_version=1, renderer_version='0.17.0')
        figure.apply_settings(state)
        assert figure.get_settings()['schema_version'] == 2
    figure, axes = figgy.subplots(2, 2, backend='webgpu', sharex='col', squeeze=False)
    try:
        assert axes.shape == (2, 2) and len(figure.subplots) == 4
        assert len(figure.shared_axes) == 2
    finally:
        figure.close()


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_first_panel_moves_without_changing_its_identity_or_data(backend):
    with figgy.Figure(backend=backend, grid=[['first', 'second']]) as figure:
        ax = figure.subplots['first'].axes
        ax.plot([0, 1, 2], [1, 3, 2], id='signal')
        figure.place('first', slot='second')
        ax.set_title('Moved first panel')
        state = figure.get_settings()
        assert state['config']['chart_area']['x'] > 0
        assert state['identity']['panels'][0]['id'] == 'first'
        assert state['series'][0]['series_id'] == 'signal'
        if backend == 'native':
            assert figure.render_rgba(scale=2).shape == (1200, 1920, 4)


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_deleted_handles_and_retired_annotation_ids_are_rejected(backend):
    with figgy.Figure(backend=backend, grid=[['first', 'second']]) as figure:
        old = figure.subplots['second'].axes
        state = figure.get_settings()
        state['config'].pop('subplots')
        state['identity']['panels'].pop()
        state['identity']['layout'] = None
        figure.apply_settings(state)
        with pytest.raises(ValueError, match='no longer exists'):
            old.set_title('Stale')
        ax = figure.axes[0]
        note = ax.text(.3, .3, 'Note', coords='ratio', id='note')
        note.remove()
        revision = figure.revision
        with pytest.raises(ValueError, match='retired'):
            ax.text(.3, .3, 'Different object', coords='ratio', id='note')
        assert figure.revision == revision


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_native_advanced_settings_share_metadata_validation(backend):
    with figgy.Figure(backend=backend, grid=[['first', 'second']]) as figure:
        before, revision = figure.get_settings(), figure.revision
        bad = copy.deepcopy(before)
        bad['identity']['layout']['unexpected'] = True
        with pytest.raises(ValueError):
            figure._native.apply_settings(json.dumps(bad))
        assert figure.get_settings() == before and figure.revision == revision


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_mapped_colormap_update_addresses_the_series_panel(backend):
    with figgy.Figure(backend=backend, grid=[['first', 'second']]) as figure:
        figure.subplots['second'].scatter([0, 1], [1, 2], c=[1, 2], id='mapped')
        figure.update('mapped', cmap='magma', vmin=.5, vmax=3)
        state = figure.get_settings()
        assert 'colorbar' not in state['config']
        assert state['config']['subplots'][0]['config']['colorbar']['colormap'] == 'Magma'


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_size_domains_and_polar_root_combinations_fail_before_upload(backend):
    with figgy.Figure(backend=backend, grid=[['polar', 'cartesian']]) as figure:
        ax = figure.subplots['cartesian'].axes
        before, revision = figure.get_settings(), figure.revision
        with pytest.raises(ValueError, match='size_domain'):
            ax.scatter([0, 1], [1, 2], s=[1, 2], size_domain=(2, 1))
        assert figure.get_settings() == before and figure.revision == revision
        figure.subplots['polar'].set_polar()
        before, revision = figure.get_settings(), figure.revision
        columns = figure.info['columns']
        with pytest.raises(ValueError, match='Cartesian root'):
            ax.quiver([0, 1], [0, 1], [1, 0], [0, 1])
        assert figure.get_settings() == before and figure.revision == revision
        assert figure.info['columns'] == columns


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_axis_helpers_use_their_panel_domain_and_preserve_other_styles(backend):
    with figgy.Figure(backend=backend, grid=[['first', 'second']]) as figure:
        first, second = figure.subplots['first'].axes, figure.subplots['second'].axes
        first.plot([0, 1], [1e6, 2e6], id='large')
        second.plot([0, 1, 2], [-1, 2, 3], id='small')
        first.activate()
        before = copy.deepcopy(figure.get_settings()['config']['left_y'])
        second.set_yscale('log')
        second.set_draw_style('sketch')
        state = figure.get_settings()
        assert state['config']['left_y'] == before
        assert 'draw_style' not in state['config']
        assert state['config']['subplots'][0]['config']['left_y']['max'] == 3
        assert state['config']['subplots'][0]['config']['draw_style']['mode'] == 'sketch'


@pytest.mark.parametrize('order', [['field', 'line'], ['line', 'field']])
def test_mixed_panel_styles_replay_identically_at_multiple_export_scales(order):
    with figgy.Figure(backend='native', grid=[order]) as source, figgy.Figure(backend='native', grid=[order]) as target:
        for figure in (source, target):
            figure.subplots['field'].imshow([[0, 1], [1, 0]], id='field')
            ax = figure.subplots['line'].axes
            ax.plot([0, 1, 2], [1, 2, 1], id='signal')
            ax.set_draw_style('sketch')
        exec(source.to_code(), {'fig': target})
        assert source.get_settings() == target.get_settings()
        for scale in (1, 1.25, 2):
            first, second = source.render_rgba(scale=scale), target.render_rgba(scale=scale)
            assert first.shape == (round(600*scale), round(960*scale), 4)
            assert np.array_equal(first, second)


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_failed_vector_registration_does_not_leave_fit_metadata(backend):
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        ax.set_draw_style('sketch')
        before, revision = figure.get_settings(), figure.revision
        with pytest.raises(ValueError):
            ax.quiver([0, 1], [0, 1], [100, 100], [100, 100], units='data', id='retry')
        assert figure.get_settings() == before and figure.revision == revision
        ax.set_draw_style('precise')
        ax.plot([0, 1], [0, 1], id='retry')
        assert figure.get_settings()['config']['left_y']['max'] == pytest.approx(1.05)


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_baseline_fills_fit_the_complete_filled_geometry(backend):
    with figgy.Figure(backend=backend) as figure:
        figure.axes[0].fill_between([0, 1], [10, 20], 0)
        axis = figure.get_settings()['config']['left_y']
        assert axis['min'] < 0 and axis['max'] > 20


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_malformed_document_shapes_are_rejected_without_state_changes(backend):
    with figgy.Figure(backend=backend) as figure:
        figure.axes[0].plot([0, 1], [1, 2], id='signal')
        before, revision = figure.get_settings(), figure.revision
        cases = [1e38]
        for path, value in [(('config',), 6743),
                            (('series', 0, 'render_type'), ''),
                            (('series', 0, 'render_type'), {'Line': 1})]:
            broken = copy.deepcopy(before)
            node = broken
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            cases.append(broken)
        for broken in cases:
            with pytest.raises(ValueError):
                figure.apply_settings(broken)
            assert figure.get_settings() == before and figure.revision == revision


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_tick_intent_replays_by_owner_and_rejects_invalid_metadata(backend):
    with figgy.Figure(backend=backend,grid=[['first','second']]) as fig:
        ax=fig.subplots['second'].axes
        ax.plot([0,100],[1,10],id='signal')
        ax.configure(bottom_x={'major_spacing':7})
        twin=ax.twinx(id='pressure')
        twin.plot([0,100],[10,100],id='pressure_data')
        twin.configure(y_axis={'major_spacing':11})
        state=fig.get_settings()
        assert state['identity']['tick_modes']['second']=={'bottom_x':'Fixed'}
        assert state['identity']['tick_modes']['pressure']=={'y_axis':'Fixed'}
        namespace={'fig':fig};exec(fig.to_code(),namespace)
        assert fig.get_settings()==state
        for owner,key,mode in [('missing','bottom_x','Auto'),('second','y_axis','Auto'),('pressure','y_axis','Unknown')]:
            bad=copy.deepcopy(state)
            bad['identity']['tick_modes'].setdefault(owner,{})[key]=mode
            revision=fig.revision
            with pytest.raises(ValueError):fig.apply_settings(bad)
            assert fig.get_settings()==state and fig.revision==revision
        ax.set_xlim(0,50)
        assert fig.get_settings()['identity']['tick_modes']['second']['bottom_x']=='Auto'
        assert fig.get_settings()['identity']['tick_modes']['pressure']['y_axis']=='Fixed'
