"""A searchable object hierarchy must route edits without a target dropdown."""
import json

import numpy as np
import pytest
import figgyplot as figgy
from figgyplot._native import object_outline_json


def flatten(nodes):
    return [node for parent in nodes for node in [parent, *flatten(parent['children'])]]


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_outline_preserves_named_owners_after_panel_moves(backend):
    with figgy.Figure(backend=backend, grid=[['left', 'right']]) as figure:
        figure.subplots['left'].set_title('Overview')
        figure.subplots['right'].set_title('Measurements')
        twin = figure.subplots['right'].twinx(id='pressure_axis')
        twin.plot([0, 1], [100, 200], label='Pressure readings', id='pressure')
        figure.subplots['left'].text(.2, .2, 'Review note', coords='ratio', id='note')
        def nodes():
            return {n['key']: n for n in flatten(json.loads(object_outline_json(json.dumps(figure.get_settings()))))}
        before = nodes()
        assert before['panel/left']['label'] == 'Overview'
        assert before['series/pressure']['label'] == 'Pressure readings'
        assert before['series/pressure']['layer'] == {'SubplotOverlay': [0, 0]}
        assert before['panel/left/annotation/note']['label'] == 'Review note'
        assert before['panel/left/annotation/note']['layer'] == 'Annotations'
        figure.place('left', slot='right')
        after = nodes()
        assert after == before


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('horizontal', [False, True])
def test_boxplot_limits_control_the_actual_value_model_and_fit_restores_auto(backend, horizontal):
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        ax.boxplot([[1, 2, 4], [2, 5, 9]], orientation='horizontal' if horizontal else 'vertical')
        bounds = (0., 12.)
        (ax.set_xlim if horizontal else ax.set_ylim)(*bounds)
        assert figure.get_settings()['boxplot']['value_range'] == list(bounds)
        before, revision = figure.get_settings(), figure.revision
        with pytest.raises(ValueError, match='value axis'):
            (ax.set_ylim if horizontal else ax.set_xlim)(*bounds)
        assert figure.get_settings() == before and figure.revision == revision
        if backend == 'native':
            assert figure.render_rgba().shape == (600, 960, 4)
        figure.fit()
        assert figure.get_settings()['boxplot']['value_range'] is None


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_radar_value_range_is_editable_and_fit_restores_auto(backend):
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        ax.radar(['A', 'B', 'C'], [2, 4, 3])
        ax.set_ylim(0, 8)
        assert figure.get_settings()['radar']['value_range'] == [0, 8]
        figure.fit()
        assert figure.get_settings()['radar']['value_range'] is None
