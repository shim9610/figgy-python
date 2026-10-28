"""Compact exports restore actual SSOT, including defaults and rich text."""
import ast
import copy
import pprint

import numpy as np
import pytest
import figgyplot as fg


def advanced_scene(fig, scene):
    ax = fig.axes[0]
    if scene == 'grid':
        fig.set_layout([['first', 'second']])
        ax = fig.subplots['first'].axes
        fig.subplots['second'].plot([0, 1], [3, 2], id='other', label='Other')
    if scene == 'mapped': ax.scatter([0, 1], [1, 2], c=[1, 4], id='signal', label='Mapped')
    else: ax.plot([0, 1], [1, 2], id='signal', label='Signal')
    if scene == 'overlay':
        right = ax.twinx(); right.plot([0, 1], [4, 8], id='pressure', label='Pressure')
        right.legend(loc='lower right')
    if scene == 'annotation': ax.text(.2, .3, 'Annotation\nwith details', coords='ratio', id='note')
    ax.set_title('Comparison\nObserved sample', fontsize=18)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('Value'); ax.legend()


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('scene', ['grid', 'mapped', 'overlay', 'annotation'])
def test_compact_document_replay_replaces_dirty_defaults_exactly(backend, scene):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        advanced_scene(source, scene); advanced_scene(target, scene)
        source_state = source.get_settings()
        dirty = target.get_settings()
        configs = [dirty['config']] + [p['config'] for p in dirty['config'].get('subplots', [])]
        for config in configs:
            config['grid']['major_x_width'] = 7
            config['legend']['border_color']['a'] = .1
            config['left_y']['label_style']['font_size'] = 35
            for overlay in config.get('overlays', []):
                overlay['y_axis']['line_width'] = 9
        target.apply_settings(dirty)
        code = source.to_code()
        assert len(code) < len(pprint.pformat(source_state, width=96, sort_dicts=False)) * .55
        expanded = source.to_code(compact=False)
        assert len(code) < len(expanded) * .55
        assert 'reset=True' in code
        assert 'json.loads' not in code and 'base64' not in code
        ast.parse(code)
        uploads = target.info.get('column_uploads')
        revision = target.revision
        exec(code, {'fig': target})
        assert target.get_settings() == source_state
        assert target.info.get('column_uploads') == uploads
        assert target.revision == revision + 1
        if backend == 'native': np.testing.assert_array_equal(source.render_rgba(), target.render_rgba())


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('family', ['categorical', 'boxplot', 'radar', 'radial'])
def test_bounded_compact_reset_preserves_destination_values_and_restores_defaults(backend, family):
    def build(fig, offset):
        ax = fig.axes[0]
        if family == 'categorical': ax.bar(['A', 'B'], [1+offset, 3+offset])
        elif family == 'boxplot': ax.boxplot([[1+offset, 2+offset], [3+offset, 5+offset]])
        elif family == 'radar': ax.radar(['A', 'B', 'C'], [1+offset, 3+offset, 2+offset])
        else: ax.pie([1+offset, 3+offset], labels=['A', 'B'])
        ax.set_title('A multiline\nrich heading')
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        build(source, 0); build(target, 10)
        dirty = target.get_settings()
        dirty[family]['font_size'] = 29
        dirty[family]['background'] = dict(r=.1, g=.1, b=.1, a=1.)
        target.apply_settings(dirty)
        before = copy.deepcopy(target.get_settings()[family])
        code = source.to_code()
        assert len(code) < len(pprint.pformat(source.get_settings()[family], width=96, sort_dicts=False)) * .55
        assert len(code) < len(source.to_code(compact=False)) * .55
        exec(code, {'fig': target})
        expected = source.get_settings()[family]
        data = 'slices' if family == 'radial' else 'series'
        values = 'value' if family == 'radial' else 'values'
        for item, original in zip(expected[data], before[data]): item[values] = original[values]
        assert target.get_settings()[family] == expected


@pytest.mark.parametrize('variable', ['fig', 'text_segments', '_text_segments', '_color1'])
def test_styled_text_runs_and_unicode_replay_without_character_dictionary_dumps(variable):
    with fg.Figure(backend='webgpu') as source, fg.Figure(backend='webgpu') as target:
        for fig in [source, target]: advanced_scene(fig, 'annotation')
        state = source.get_settings()
        segments = fg.text_segments('Plain ') + fg.text_segments('bold 한글', bold=True) + fg.text_segments('\n10⁻³')
        segments += fg.text_segments('한글 red', color={'r': .5, 'g': .25, 'b': .75, 'a': 1.}) * 2
        state['config']['chart_title']['text']['segments'] = segments
        source.apply_settings(state)
        code = source.to_code(variable)
        assert "bold=True" in code and "'bold':" not in code
        exec(code, {variable: target})
        assert target.get_settings() == source.get_settings()


def test_compact_resets_validate_atomically_and_do_not_mutate_input():
    with fg.Figure(backend='webgpu') as fig:
        fig.axes[0].bar(['A', 'B'], [2, 3])
        before, revision = fig.get_settings(), fig.revision
        with pytest.raises(ValueError): fig.configure_bounded(reset=True, font_size=-1)
        assert fig.get_settings() == before and fig.revision == revision
        patch = {'schema_version': 2, 'config': {'chart_area': before['config']['chart_area']},
                 'series': [], 'identity': copy.deepcopy(before['identity']), 'categorical': {'categories': []}}
        original = copy.deepcopy(patch)
        with pytest.raises(ValueError): fig.apply_settings(patch, reset=True)
        assert patch == original
        assert fig.get_settings() == before and fig.revision == revision
