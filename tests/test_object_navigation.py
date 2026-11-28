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
        cfg=figure.get_settings()['config'];axis='bottom_x' if horizontal else 'left_y'
        assert [cfg[axis][key] for key in ('min','max')]==list(bounds)
        if backend == 'native':
            assert figure.render_rgba().shape == (600, 960, 4)
        figure.fit()
        fitted=figure.get_settings()['config'][axis]
        assert fitted['min']<1 and fitted['max']>9 and fitted['max']<12


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_radar_value_range_is_editable_and_fit_restores_auto(backend):
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        ax.radar(['A', 'B', 'C'], [2, 4, 3])
        ax.set_ylim(0, 8)
        assert [figure.get_settings()['config']['left_y'][key] for key in ('min','max')]==[0,8]
        figure.fit()
        axis=figure.get_settings()['config']['left_y']
        assert axis['min']<2 and axis['max']>4 and axis['max']<8
