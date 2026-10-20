"""Renderer migration must preserve saved settings and Figure-local references."""
import copy
import json

import numpy as np
import pytest
import figgyplot as figgy


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('kind', ['line', 'radial', 'categorical', 'boxplot'])
def test_previous_settings_preserve_edits_and_reject_unknown_versions(backend, kind):
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        if kind == 'line':
            ax.plot([0, 1, 2], [1, 0, 2], id='signal')
        elif kind == 'radial':
            ax.donut([2, 3, 4])
        elif kind == 'categorical':
            ax.bar(['A', 'B'], [2, 3])
        else:
            ax.boxplot([[1, 2, 3], [2, 3, 4]])
        ax.set_title('Saved presentation')
        saved = figure.get_settings()
        saved['renderer_version'] = '0.17.0'
        ax.set_title('Temporary edit')
        figure.apply_settings(saved)
        current = figure.get_settings()
        expected = dict(saved, renderer_version='0.18.0')
        assert current == expected
        revision = figure.revision
        for key, value in [('renderer_version', '0.19.0'), ('schema_version', 2)]:
            invalid = dict(saved, **{key: value})
            with pytest.raises(ValueError, match='version'):
                figure.apply_settings(invalid)
            assert figure.get_settings() == current
            assert figure.revision == revision
        if backend == 'native':
            assert figure.render_rgba().shape == (600, 960, 4)


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_heatmap_legend_updates_colormap_and_replays_without_losing_text(backend):
    with figgy.Figure(backend=backend) as source, figgy.Figure(backend=backend) as target:
        for figure in (source, target):
            figure.axes[0].imshow([[0, 1], [1, 0]], id='field')
            figure.update('field', label='Temperature')
            figure.axes[0].legend()
        before = source.get_settings()['config']['legend']['content']['segments']
        source.update('field', cmap='magma')
        after = source.get_settings()['config']['legend']['content']['segments']
        assert before != after
        assert 'Temperature' in ''.join(segment['text'] for segment in after)
        exec(source.to_code(), {'fig': target})
        assert target.get_settings() == source.get_settings()
        if backend == 'native':
            assert np.array_equal(source.render_rgba(), target.render_rgba())


def reference_chart(figure, kind, reverse):
    """Use the existing low-level model path, without adding new public APIs."""
    ax = figure.axes[0]
    x = np.array([0., 1., 2.], dtype=np.float32)
    values = np.array([0., 2., 1.] if reverse else [2., 0., 1.], dtype=np.float32)
    if kind == 'fill':
        ax.plot(x, np.ones(3, dtype=np.float32), id='lower')
        figure._native.upload_column('upper/y', values)
        spec = copy.deepcopy(figure.get_settings()['series'][0])
        spec.update(series_id='upper', y_column='upper/y')
        spec['render_type']['Line']['line'].update(
            fill={'ToSeries': 'lower'}, fill_color=dict(r=1., g=0., b=0., a=1.))
        figure._native.add_series_fitted(json.dumps(spec), None, [0., 2., -1., 3.])
    elif kind == 'maps':
        ax.scatter(x, np.ones(3), id='signal')
        figure._native.upload_column('color', values)
        figure._native.upload_column('size', values)
        state = figure.get_settings()
        from figgyplot._native import default_colorbar_json
        state['config']['colorbar'] = json.loads(default_colorbar_json())
        state['config']['colorbar']['axis'].update(min=0., max=2., major_spacing=.5)
        scatter = state['series'][0]['render_type']['Scatter']['scatter']
        scatter['point_color_map'] = {'column': 'color'}
        scatter['point_size_map'] = dict(column='size', domain_min=0., domain_max=2., min_px=3., max_px=15.)
        figure.apply_settings(state)
    else:
        from figgyplot._native import default_colorbar_json
        config = figure.get_settings()['config']
        config['colorbar'] = json.loads(default_colorbar_json())
        config['colorbar']['axis'].update(min=0., max=2., major_spacing=.5)
        grid = lambda names: dict(columns=names, orientation='ColumnsAreX', grid_layout='Centers')
        if kind == 'vector_points':
            components = {'Points': {'u': 'u', 'v': 'v'}}
            color_map = {'Column': 'color'}
            extra = [('u', values), ('v', np.ones(3)), ('color', values)]
        else:
            components = {'Grid': {'u': grid(['u0', 'u1', 'u2']), 'v': grid(['v0', 'v1', 'v2'])}}
            color_map = {'Grid': grid(['c0', 'c1', 'c2'])}
            extra = [(f'{name}{i}', values if name != 'v' else np.ones(3))
                     for name in ('u', 'v', 'c') for i in range(3)]
        extra = [(name, np.asarray(array, dtype=np.float32)) for name, array in extra]
        style = dict(color=dict(r=0., g=0., b=0., a=1.), width_px=2.,
                     scale={'Pixels': {'px_per_unit': 25.}}, head_length_px=8., head_width_px=6.,
                     color_map=color_map)
        ax._add(x, x, {'Vector': dict(components=components, style=style)},
                id='signal', extra_columns=extra, config=config, bounds=[-1., 3., -1., 3.])
    ax.set_xlim(-1., 3.)
    ax.set_ylim(-1., 3.)


@pytest.mark.parametrize('kind', ['fill', 'maps', 'vector_points', 'vector_grid'])
def test_new_references_isolate_figures_and_survive_other_figure_close(kind):
    with figgy.Figure(backend='native') as first, figgy.Figure(backend='native') as second:
        reference_chart(first, kind, False)
        reference_chart(second, kind, True)
        settings = second.get_settings()
        assert 'figgy/' not in json.dumps(settings)
        image = second.render_rgba()
        assert not np.array_equal(first.render_rgba(), image)
        uploads = second.info['column_uploads']
        revision = second.revision
        invalid = copy.deepcopy(settings)
        if kind == 'fill':
            invalid['series'][1]['render_type']['Line']['line']['fill'] = {'ToSeries': 'missing'}
        else:
            invalid['config']['colorbar'] = None
        with pytest.raises(ValueError):
            second.apply_settings(invalid)
        assert second.revision == revision
        assert second.get_settings() == settings
        assert np.array_equal(second.render_rgba(), image)
        first.close()
        assert np.array_equal(second.render_rgba(), image)
        assert second.info['column_uploads'] == uploads
        assert second.get_settings() == settings
