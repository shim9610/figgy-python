"""Public contracts discovered by six independent users of the frozen wheel."""
import copy

import numpy as np
import pytest
import figgyplot as fg


def populate(ax, method, **kwargs):
    if method in ('bar', 'barh'):
        getattr(ax, method)(['A', 'B'], [2, 4], **kwargs)
        return 'categorical'
    if method == 'boxplot':
        ax.boxplot([[1, 2, 3], [2, 3, 5]], labels=['A', 'B'], **kwargs)
        # Material grain is salted by each resident series' identity.
        ax.chart.set_material('flat')
        return 'boxplot'
    if method == 'radar':
        ax.radar(['A', 'B', 'C'], [2, 4, 3], **kwargs)
        return 'radar'
    getattr(ax, method)([2, 4], labels=['A', 'B'], **kwargs)
    return 'radial'


def owner(state, kind):
    return state['radial'] if kind == 'radial' else state['config']


def wording(title):
    return ''.join(s['text'] for s in title['text']['segments'])


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('style', [None, 'paper'])
@pytest.mark.parametrize('method,horizontal', [('bar', False), ('barh', True),
                                              ('boxplot', False), ('boxplot', True)])
def test_axis_names_survive_first_bounded_chart(backend, style, method, horizontal):
    with fg.Figure(backend=backend, style=style) as before, fg.Figure(backend=backend, style=style) as after:
        charts = []
        for fig, early in [(before, True), (after, False)]:
            ax = fig.axes[0]
            if early:
                ax.set_xlabel('Requested X'); ax.set_ylabel('Requested Y')
            kind = populate(ax, method, **({'orientation': 'horizontal'} if method == 'boxplot' and horizontal else {}))
            if not early:
                ax.set_xlabel('Requested X'); ax.set_ylabel('Requested Y')
            charts.append(fig.get_settings()['config'])
        assert wording(charts[0]['left_y' if horizontal else 'bottom_x']['title_option']) == ('Requested Y' if horizontal else 'Requested X')
        assert wording(charts[0]['bottom_x' if horizontal else 'left_y']['title_option']) == ('Requested X' if horizontal else 'Requested Y')
        # Compare the entire actual model, not a guessed subset of constructor defaults.
        assert charts[0] == charts[1]
        if backend == 'native':
            np.testing.assert_array_equal(before.render_rgba(), after.render_rgba())


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_explicit_bounded_axis_names_including_empty_override_inherited_names(backend):
    with fg.Figure(backend=backend, style='paper') as fig:
        ax = fig.axes[0]
        ax.set_xlabel('Earlier X'); ax.set_ylabel('Earlier Y')
        ax.barh(['A'], [2], category_title='', value_title='Explicit X')
        chart = fig.get_settings()['config']
        assert wording(chart['left_y']['title_option']) == ''
        assert wording(chart['bottom_x']['title_option']) == 'Explicit X'
    with fg.Figure(backend=backend, style='paper') as fig:
        fig.axes[0].set_title('Earlier\nTitle')
        fig.axes[0].bar(['A'], [2], title='Explicit\nHeading')
        assert wording(fig.get_settings()['config']['chart_title']) == 'Explicit\nHeading'
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].set_title('Earlier title')
        fig.axes[0].bar(['A'], [2], title='')
        assert wording(fig.get_settings()['config']['chart_title']) == ''


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('method', ['bar', 'boxplot', 'radar', 'pie', 'donut'])
def test_multiline_titles_before_and_after_construction_preserve_wording_and_format(backend, method):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.set_title('First line\nSecond line', fontsize=18, color='purple', align='right')
        kind = populate(ax, method)
        chart = owner(fig.get_settings(), kind)
        assert wording(chart['chart_title']) == 'First line\nSecond line'
        assert chart['chart_title']['text']['align'] == 'Right'
        assert chart['chart_title']['text']['font_size'] == 30
        ax.set_title('Revised\nSecond line')
        chart = owner(fig.get_settings(), kind)
        assert wording(chart['chart_title']) == 'Revised\nSecond line'
        assert len(chart['chart_title']['text']['segments']) > 0
        # A size-only edit preserves character formatting and all unrelated chart fields.
        state = fig.get_settings()
        owner(state, kind)['chart_title']['text']['segments'][0]['bold'] = True
        fig.apply_settings(state)
        expected = fig.get_settings()
        owner(expected, kind)['chart_title']['text']['font_size'] = 35
        fig.update('chart_title', fontsize=21)
        current=fig.get_settings()
        if kind != 'radial':
            assert current['config']['chart_title']['top_margin'] >= expected['config']['chart_title']['top_margin']
            expected['config']['chart_title']['top_margin']=current['config']['chart_title']['top_margin']
        assert current == expected
        if backend == 'native':
            image = fig.render_rgba()
            assert image[..., :3].var() > 1


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('method', ['bar', 'boxplot', 'radar', 'pie'])
def test_title_text_tokens_and_code_replay_preserve_rich_text(backend, method):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        kind = populate(source.axes[0], method)
        populate(target.axes[0], method)
        source.axes[0].set_title('Heading\nDetail')
        state = source.get_settings()
        owner(state, kind)['chart_title']['text']['segments'][0]['italic'] = True
        source.apply_settings(state)
        token = fg.StyleToken.from_json(source.extract_style(text=True).to_json())
        target.axes[0].set_title('Destination')
        before = target.get_settings()
        target.apply_style(token)
        assert owner(target.get_settings(), kind)['chart_title']['text']['segments'] == owner(before, kind)['chart_title']['text']['segments']
        target.apply_style(token, text={'titles'})
        assert owner(target.get_settings(), kind)['chart_title']['text']['segments'] == owner(state, kind)['chart_title']['text']['segments']
        # Previously serialized tokens with only a plain title remain usable.
        legacy = fg.StyleToken.from_json(token.to_json())
        if kind == 'radial':
            legacy.text['bounded'].pop('title_segments')
        target.apply_style(legacy, text={'titles'})
        assert wording(owner(target.get_settings(), kind)['chart_title']) == 'Heading\nDetail'
        target.axes[0].set_title('Other')
        exec(source.to_code(mode='exact'), {'fig': target})
        assert owner(target.get_settings(), kind) == owner(source.get_settings(), kind)
        if backend == 'native':
            np.testing.assert_array_equal(source.render_rgba(), target.render_rgba())


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_title_appearance_token_preserves_destination_title(backend):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        source.axes[0].bar(['A'], [2]); target.axes[0].bar(['A'], [7])
        source.axes[0].set_title('SOURCE WORDING', fontsize=20, color='purple')
        target.axes[0].set_title('DESTINATION WORDING')
        values = [(v['x_column'], v['y_column']) for v in target.get_settings()['series']]
        target.apply_style(source.extract_style(text=True))
        chart = target.get_settings()['config']
        assert wording(chart['chart_title']) == 'DESTINATION WORDING'
        assert chart['chart_title']['text']['font_size'] == pytest.approx(100/3)
        assert [(v['x_column'], v['y_column']) for v in target.get_settings()['series']] == values


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_rich_title_limits_still_reject_atomically_and_keep_full_valid_text(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]; ax.bar(['A'], [2])
        valid = 'x' * 200 + '\n' + 'y' * 200
        ax.set_title(valid)
        assert wording(fig.get_settings()['config']['chart_title']) == valid
        for bad in ['x' * 513, '\n'.join(['line'] * 9), 'bad\x00title']:
            state, revision = fig.get_settings(), fig.revision
            with pytest.raises(ValueError): ax.set_title(bad)
            assert fig.get_settings() == state and fig.revision == revision


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_axis_inversion_is_scoped_and_preserves_other_settings(backend):
    with fg.Figure(backend=backend, grid=[['first', 'second']]) as fig:
        ax = fig.subplots['second']; ax.plot([1, 2], [2, 4])
        before = fig.get_settings()
        ax.invert_yaxis()
        expected = copy.deepcopy(before)
        for side in ('left_y', 'right_y'): expected['config']['subplots'][0]['config'][side]['inverted'] = True
        assert fig.get_settings() == expected
        ax.invert_yaxis()
        assert fig.get_settings() == before
        ax.invert_xaxis()
        expected = copy.deepcopy(before)
        for side in ('bottom_x', 'top_x'): expected['config']['subplots'][0]['config'][side]['inverted'] = True
        assert fig.get_settings() == expected
        ax.invert_xaxis()
        assert fig.get_settings() == before
        twin = ax.twinx(); before = fig.get_settings(); twin.invert_yaxis()
        expected = copy.deepcopy(before)
        expected['config']['subplots'][0]['config']['overlays'][0]['y_axis']['inverted'] = True
        assert fig.get_settings() == expected
        twin.invert_yaxis()
        assert fig.get_settings() == before
        fig.share_axes('y', ['first', 'second'])
        ax.invert_yaxis()
        state = fig.get_settings()
        assert state['config']['left_y']['inverted']
        assert state['config']['subplots'][0]['config']['left_y']['inverted']
    for kind in ('bounded', 'polar'):
        with fg.Figure(backend=backend) as fig:
            ax = fig.axes[0]
            if kind == 'bounded': ax.bar(['A'], [2])
            else: ax.set_polar()
            state, revision = fig.get_settings(), fig.revision
            for edit in (ax.invert_xaxis, ax.invert_yaxis):
                if kind == 'polar':
                    with pytest.raises(ValueError): edit()
                    assert fig.get_settings() == state and fig.revision == revision
                else:
                    edit();assert fig.get_settings()['series'] == state['series']
                    edit();assert fig.get_settings() == state


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_legend_location_helpers_share_model_and_invalid_edits_are_atomic(backend):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]; ax.plot([1, 2], [2, 3], label='Signal')
        ax.legend(loc='upper left')
        assert fig.get_settings()['config']['legend']['corner'] == 'TopLeft'
        fig.update('legend', corner='BottomRight')
        assert fig.get_settings()['config']['legend']['corner'] == 'BottomRight'
        before, rev = fig.get_settings(), fig.revision
        with pytest.raises(ValueError): ax.legend(loc='best')
        assert fig.get_settings() == before and fig.revision == rev
        with pytest.raises(ValueError): fig.update('legend', corner='bogus')
        assert fig.get_settings() == before and fig.revision == rev
        twin = ax.twinx()
        twin.plot([1, 2], [3, 4], label='Secondary', id='secondary')
        before = fig.get_settings()
        twin.legend(loc='lower left')
        after = fig.get_settings()
        assert after['config']['legend'] == before['config']['legend']
        overlay_legend = after['config']['overlays'][0]['legend']
        assert overlay_legend['corner'] == 'BottomLeft'
        assert 'Secondary' in ''.join(s['text'] for s in overlay_legend['content']['segments'])
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]; ax.bar(['A'], [2])
        before, revision = fig.get_settings(), fig.revision
        ax.legend(loc='upper left')
        assert fig.get_settings()['config']['legend']['corner'] == 'TopLeft'
        assert fig.get_settings()['series'] == before['series']


@pytest.mark.parametrize('method', ['bar', 'boxplot'])
def test_multiline_category_labels_have_actionable_errors_and_no_partial_chart(method):
    with fg.Figure(backend='native') as fig:
        before, revision = fig.get_settings(), fig.revision
        with pytest.raises(ValueError, match='category labels must be single-line'):
            if method == 'bar': fig.axes[0].bar(['A\nB'], [2])
            else: fig.axes[0].boxplot([[1, 2, 3]], labels=['A\nB'])
        assert fig.get_settings() == before and fig.revision == revision
