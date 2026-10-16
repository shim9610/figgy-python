"""Selected values come from resident GPU samples, independent of NumPy lifetime."""
import json
import numpy as np
import pytest
import figgyplot as figgy


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


@pytest.mark.parametrize('orientation', ['vertical', 'horizontal'])
@pytest.mark.parametrize('mode', ['counts', 'density', 'weighted', 'stairs'])
def test_histogram_bin_values_and_navigation_survive_source_mutation(orientation, mode):
    edges=np.array([0.,1.,2.,4.])
    source=np.array([.25,.5,1.5,3.5])
    weights=np.array([.5,1.5,3.,4.])
    with figgy.Figure(backend='native') as figure:
        ax=figure.axes[0]
        if mode=='stairs':
            values=np.array([2.25,-1.5,4.75])
            ax.stairs(values,edges,orientation=orientation,id='bins')
        else:
            values,_,_=ax.hist(source,bins=edges,weights=weights if mode=='weighted' else None,
                               density=mode=='density',orientation=orientation,id='bins')
        expected=values.copy()
        original_series=figure.get_settings()['series'];uploads=figure.info['column_uploads']
        choose(figure,{'kind':'histogram_bin','series_id':'bins','bin_index':1})
        source[:]=-99;weights[:]=-99;edges[:]=-99;values[:]=-99
        selected=details(figure)
        assert selected['identity']['kind']=='histogram_bin'
        assert selected['index']==1
        assert (selected['bin_start'],selected['bin_end'],selected['value'])==pytest.approx((1,2,expected[1]))
        assert selected['orientation']==orientation.title()
        assert 'count' not in selected  # Stored heights may be weighted, density or arbitrary stairs.
        step=(1,0) if orientation=='vertical' else (0,1)
        assert figure._native.move_data_selection(*step)
        selected=details(figure)
        assert selected['index']==2
        assert (selected['bin_start'],selected['bin_end'],selected['value'])==pytest.approx((2,4,expected[2]))
        assert not figure._native.move_data_selection(*step)
        assert figure.get_settings()['series']==original_series
        assert figure.info['column_uploads']==uploads
        assert figure.info['rgba_readbacks']==figure.info['png_encodes']==0


@pytest.mark.parametrize('orientation', ['vertical', 'horizontal'])
def test_histogram_navigation_switches_compatible_series_and_clamps(orientation):
    with figgy.Figure(backend='native') as figure:
        ax=figure.axes[0]
        ax.stairs([1.,2.,3.],[0.,1.,2.,3.],orientation=orientation,id='long')
        ax.plot([0.,1.],[1.,2.],id='unrelated-line')
        ax.stairs([99.],[0.,1.],orientation='horizontal' if orientation=='vertical' else 'vertical',id='other-direction')
        ax.stairs([7.],[10.,20.],orientation=orientation,id='short')
        choose(figure,{'kind':'histogram_bin','series_id':'long','bin_index':2})
        series_step=(0,1) if orientation=='vertical' else (1,0)
        assert figure._native.move_data_selection(*series_step)
        selected=details(figure)
        assert selected['series_id']=='short' and selected['index']==0
        assert (selected['bin_start'],selected['bin_end'],selected['value'])==(10.,20.,7.)
        assert not figure._native.move_data_selection(*series_step)
