"""Selected values come from resident GPU samples, independent of NumPy lifetime."""
import json
import numpy as np
import pytest
import figgy


def choose(figure, identity):
    state = figure.get_settings()
    state['config']['picked_data'] = {'refs': [identity]}
    figure.apply_settings(state)


def details(figure):
    return json.loads(figure._native.selection_details_json())


def test_selected_values_survive_source_mutation_and_arrow_navigation():
    x = 1e9 + np.arange(8, dtype=np.float64) / 1000
    y = np.arange(8, dtype=np.float64) ** 2
    expected = x.copy()
    with figgy.Figure(backend='native') as figure:
        figure.axes[0].plot(x, y, id='signal')
        figure.axes[0].plot(x[:4], -y[:4], id='reference')
        choose(figure, {'kind':'point', 'series_id':'signal', 'point_index':2})
        x[:] = -100; y[:] = -200
        assert details(figure)['x'] == pytest.approx(expected[2], abs=1e-7)
        assert details(figure)['y'] == 4
        assert figure._native.move_data_selection(1, 0)
        assert details(figure)['index'] == 3 and details(figure)['y'] == 9
        assert figure._native.move_data_selection(0, 1)
        assert details(figure)['series_id'] == 'reference' and details(figure)['y'] == -9
        assert not figure._native.move_data_selection(1, 0)  # End of shorter series.
        assert figure.info['column_uploads'] == 4
        assert figure.info['rgba_readbacks'] == figure.info['png_encodes'] == 0
        figure._native.clear_data_selection()
        assert details(figure) is None


def test_heatmap_cell_values_and_two_dimensional_navigation():
    z = np.array([[10., 20., 30.], [40., 50., 60.]])
    with figgy.Figure(backend='native') as figure:
        figure.axes[0].imshow(z, origin='lower', extent=(0, 6, 0, 4), id='heat')
        choose(figure, {'kind':'matrix_cell', 'series_id':'heat', 'x_index':0, 'y_index':0})
        z[:] = 999
        assert (details(figure)['x'], details(figure)['y'], details(figure)['value']) == (1., 1., 10.)
        assert figure._native.move_data_selection(1, 1)
        selected = details(figure)
        assert (selected['x'], selected['y'], selected['value']) == (3., 3., 50.)
        assert figure._native.move_data_selection(100, 100)
        assert details(figure)['value'] == 60
        assert not figure._native.move_data_selection(1, 1)
        assert figure.info['column_uploads'] == 4
        assert figure.info['rgba_readbacks'] == 0
