"""Opposite-axis convenience edits share changed fields, never whole styles."""
import copy

import pytest
import figgyplot as figgy


PAIRS = [('bottom', 'bottom_x', 'top', 'top_x'), ('top', 'top_x', 'bottom', 'bottom_x'),
         ('left', 'left_y', 'right', 'right_y'), ('right', 'right_y', 'left', 'left_y')]


@pytest.fixture(params=['native', 'webgpu'])
def figure(request):
    with figgy.figure(backend=request.param) as fig:
        fig.axes[0].plot([1., 10., 100.], [1., 10., 100.])
        fig.configure(config={key: {'min': 1., 'max': 100., 'scale': 'Linear', 'inverted': False}
                              for key in ['bottom_x', 'top_x', 'left_y', 'right_y']})
        yield fig


@pytest.mark.parametrize('side,key,opposite,peer', PAIRS)
def test_axis_edits_work_in_both_directions_and_preserve_unedited_differences(figure, side, key, opposite, peer):
    figure.configure(config={key: {'minor_count': 3, 'line_visible': False, 'line_offset': 2,
                                  'label_style': {'font_size': 11, 'significant_digits': 3}},
                             peer: {'minor_count': 7, 'line_visible': True, 'line_offset': 9,
                                    'label_style': {'font_size': 19, 'significant_digits': 6}}})
    expected=copy.deepcopy(figure.get_settings())
    for name in (key, peer):
        expected['config'][name].update(major_spacing=4., tick='Inside', line_width=2.)
    figure.update('axis_'+side, major_spacing=4., tick='Inside', line_width=2.)
    assert figure.get_settings()==expected
    # A secondary-side edit uses the same rule in reverse; no explicit link flag.
    for name in (key, peer):
        expected['config'][name]['minor_count']=2
    figure.update('axis_'+opposite, minor_count=2)
    assert figure.get_settings()==expected


@pytest.mark.parametrize('side,key,opposite,peer', PAIRS)
def test_tick_labels_sync_changed_subfields_but_preserve_edge_offsets(figure, side, key, opposite, peer):
    figure.configure(config={key: {'label_style': {'font_size': 11, 'significant_digits': 3, 'label_offset_x': 1}},
                             peer: {'label_style': {'font_size': 19, 'significant_digits': 6, 'label_offset_x': 7}}})
    expected=copy.deepcopy(figure.get_settings())
    for name in (key, peer):
        expected['config'][name]['label_style'].update(format='Scientific', significant_digits=4)
    expected['config'][key]['label_style']['label_offset_x']=12.
    figure.update('tick_labels_'+side, format='Scientific', significant_digits=4, label_offset_x=12.)
    assert figure.get_settings()==expected
    # Formatting is also reachable from the axis object itself.
    for name in (key, peer):
        expected['config'][name]['label_style']['format']='Power'
    figure.update('axis_'+opposite, format='Power')
    assert figure.get_settings()==expected


@pytest.mark.parametrize('difference,value', [('min', 1.000000000001), ('max', 101.),
                                              ('scale', 'Logarithmic'), ('inverted', True)])
def test_distinct_coordinate_axes_remain_independent_without_rounding(figure, difference, value):
    figure.configure(config={'top_x': {difference: value}})
    expected=copy.deepcopy(figure.get_settings())
    expected['config']['bottom_x']['major_spacing']=4.
    expected['config']['bottom_x']['label_style']['significant_digits']=4
    figure.update('axis_bottom', major_spacing=4., significant_digits=4)
    assert figure.get_settings()==expected


def test_link_decision_uses_pre_edit_coordinates_and_preserves_other_axis_state(figure):
    before=figure.get_settings()
    expected=copy.deepcopy(before)
    for key in ('bottom_x','top_x'):
        expected['config'][key].update(min=2.,max=20.,inverted=True)
    figure.update('axis_top', min=2.,max=20.,inverted=True)
    assert figure.get_settings()==expected
    # Hiding one axis line must not hide its opposite or its title.
    expected['config']['top_x']['line_visible']=False
    figure.update('axis_top', line_visible=False)
    assert figure.get_settings()==expected
    before=figure.get_settings()['config']['bottom_x']['title_option']
    figure.update('axis_title_top', text='Independent top title')
    assert figure.get_settings()['config']['bottom_x']['title_option']==before


def test_log_scale_switch_shares_fitted_bounds_and_spacing_only_when_linked(figure):
    figure.configure(config={key:{'min':-5.,'max':105.} for key in ('bottom_x','top_x')})
    other=copy.deepcopy(figure.get_settings()['config']['left_y'])
    figure.update('axis_top', scale='log')
    config=figure.get_settings()['config']
    for key in ('bottom_x','top_x'):
        assert (config[key]['min'],config[key]['max'])==(1.,100.)
        assert config[key]['scale']=='Logarithmic' and config[key]['major_spacing']==1.
    assert config['left_y']==other


def test_raw_ssot_edits_do_not_run_opposite_axis_helpers(figure):
    before=figure.get_settings()
    figure.configure(config={'bottom_x':{'major_spacing':7.,'label_style':{'format':'Power'}}})
    assert figure.get_settings()['config']['top_x']==before['config']['top_x']
    state=figure.get_settings()
    state['config']['top_x']['tick']='Inside'
    expected=copy.deepcopy(state)
    figure.apply_settings(state)
    assert figure.get_settings()==expected


def test_nested_style_edits_copy_only_changed_label_fields_and_atomic_colors(figure):
    color={'r':.75,'g':.25,'b':.5,'a':1.}
    figure.configure(config={'bottom_x':{'label_style':{'font_size':11.,'significant_digits':3}},
                             'top_x':{'label_style':{'font_size':19.,'significant_digits':6}}})
    expected=copy.deepcopy(figure.get_settings())
    for key in ('bottom_x','top_x'):
        expected['config'][key]['label_style']['color']=color
        expected['config'][key]['label_style']['visible']=False
    figure.update('axis_bottom', label_style={'color':color,'visible':False})
    assert figure.get_settings()==expected
