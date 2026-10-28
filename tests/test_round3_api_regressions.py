"""User-visible contracts found by the third blind public-data evaluation."""
import copy
import json

import numpy as np
import pytest

import figgyplot as fg
from figgyplot.ticker import MultipleLocator, LogLocator
from recovery_assertions import assert_renderer_columns


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('method', ['constructor', 'set_label', 'axis_label'])
def test_explicit_colorbar_label_is_visible_and_explicit_hiding_is_respected(backend, method):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        points = ax.scatter([1, 2], [3, 4], c=[10, 20], id='points')
        if method == 'constructor':
            bar = fig.colorbar(points, label='Temperature (K)')
        else:
            bar = fig.colorbar(points)
            (bar.set_label if method == 'set_label' else bar.ax.yaxis.set_label_text)('Temperature (K)')
        assert bar.ax.yaxis.label.get_text() == 'Temperature (K)'
        assert bar.ax.yaxis.label.get_visible()
        before = fig.get_settings()
        bar.set_label('Hidden on purpose', visible=False)
        assert not bar.ax.yaxis.label.get_visible()
        after = fig.get_settings()
        assert after['series'] == before['series']
        assert after['config']['colorbar']['axis']['min'] == 10
        assert after['config']['colorbar']['axis']['max'] == 20


@pytest.mark.parametrize('dpi', [72, 144])
@pytest.mark.parametrize('side', ['left', 'right', 'top', 'bottom'])
def test_colorbar_label_pixels_are_separate_from_ticks_and_inside_canvas(dpi, side):
    with fg.Figure(backend='native', figsize=(10, 6), dpi=dpi) as fig:
        points = fig.axes[0].scatter([1, 2], [3, 4], c=[10, 20], cmap='gray')
        bar = fig.colorbar(points)
        bar.set_layout(side=side)
        bar.set_label('Temperature (K)', color='red', fontsize=18)
        bar.ax.tick_params(labelsize=12, labelcolor='blue')
        image = fig.render_rgba()
        rgb = image[..., :3].astype(int)
        red = (rgb[..., 0] > 200) & (rgb[..., 1] < 40) & (rgb[..., 2] < 40)
        blue = (rgb[..., 2] > 200) & (rgb[..., 0] < 40) & (rgb[..., 1] < 40)
        assert red.sum() > 20 and blue.sum() > 20
        ry, rx = np.where(red); by, bx = np.where(blue)
        if side == 'right': assert rx.min() > bx.max()
        elif side == 'left': assert rx.max() < bx.min()
        elif side == 'top': assert ry.max() < by.min()
        else: assert ry.min() > by.max()
        # Pixel separation alone must not pass by clipping away part of a label.
        bounds = json.loads(fig._native.bounds_json('colorbar_title'))['rect']
        x, y, w, h = bounds
        assert x >= 0 and y >= 0
        assert x+w <= image.shape[1] and y+h <= image.shape[0]


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('horizontal', [False, True])
def test_categorical_limits_are_guarded_without_partial_edits(backend, horizontal):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        (ax.barh if horizontal else ax.bar)(['A', 'B'], [2, 3])
        before, revision = fig.get_settings(), fig.revision
        uploads = fig.info.get('column_uploads')
        setter = ax.set_xlim if horizontal else ax.set_ylim
        with pytest.raises(NotImplementedError, match='categorical.*automatic.*range'):
            setter(0, 10)
        assert fig.get_settings() == before
        assert fig.revision == revision
        assert fig.info.get('column_uploads') == uploads
        for getter in (ax.get_xlim, ax.get_ylim):
            with pytest.raises(NotImplementedError, match='automatic bounded-axis limits'):
                getter()
        assert fig.get_settings() == before and fig.revision == revision


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('compact', [True, False])
def test_exact_report_style_restores_explicit_white_background_and_entire_ssot(backend, compact):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            fig.axes[0].plot([0, 1], [2, 3], id='signal')
        source.apply_style('report')
        before = source.get_settings()
        assert before['background'] == dict(r=1., g=1., b=1., a=1.)
        target.set_facecolor('#123456')
        uploads = target.info.get('column_uploads')
        exec(source.to_code(mode='exact', compact=compact), {'fig': target})
        assert target.get_settings() == before
        assert source.get_settings() == before
        assert target.info.get('column_uploads') == uploads
        if backend == 'native':
            np.testing.assert_array_equal(source.render_rgba(), target.render_rgba())


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('policy', ['implicit', 'auto', 'fixed', 'mixed'])
def test_public_code_preserves_tick_intent_without_replanning_current_ticks(backend, policy):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        for fig in (source, target):
            ax = fig.axes[0]
            ax.plot([0, 1000], [1, 4], id='signal')
        ax = source.axes[0]
        if policy != 'implicit':
            ax.set_xlim(0, 1000)
            ax.set_ylim(0, 5)
        # A deliberately retained spacing differs from the fresh 200-unit
        # plan. Public setters establish this accepted state; no snapshot
        # fields are fabricated, and AutoLocator cannot reproduce it.
        ax.xaxis.set_major_locator(MultipleLocator(125))
        if policy in ('implicit', 'auto'):
            ax.xaxis.set_tick_auto(None if policy == 'implicit' else True)
        if policy in ('fixed', 'mixed'):
            ax.xaxis.set_tick_auto(False)
        if policy == 'mixed':
            ax.secondary_xaxis('top').xaxis.set_tick_auto(True)
        # A previously accepted auto layout need not match a fresh tick plan.
        # Restoring policy must keep this actual SSOT rather than recompute it.
        before = source.get_settings()
        assert before['config']['bottom_x']['major_spacing'] == 125
        target.axes[0].xaxis.set_major_locator(MultipleLocator(25))
        uploads = target.info.get('column_uploads')
        exec(source.to_code(), {'fig': target})
        after = target.get_settings()
        assert after['identity'].get('tick_modes') == before['identity'].get('tick_modes')
        assert after['config'] == before['config']
        assert after['series'] == before['series']
        assert source.get_settings() == before
        assert target.info.get('column_uploads') == uploads
        if backend == 'native':
            np.testing.assert_array_equal(source.render_rgba(), target.render_rgba())


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_public_code_preserves_tick_policies_of_shared_panels_and_overlay(backend):
    def scene(fig):
        fig.set_layout([['left', 'right']])
        for panel in fig.subplots.values():
            panel.plot([0, 10], [1, 4], id='signal_'+panel.id)
            panel.set_xlim(0, 10)
        fig.subplots['right'].twinx(id='pressure').plot([0, 10], [100, 300], id='pressure_data')
        fig.share_axes('x', ['left', 'right'])
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        scene(source); scene(target)
        source.subplots['right'].axes.get_overlay('pressure').yaxis.set_major_locator(MultipleLocator(50))
        before = copy.deepcopy(source.get_settings())
        exec(source.to_code(), {'fig': target})
        after = target.get_settings()
        assert after['identity'].get('tick_modes') == before['identity'].get('tick_modes')
        assert after['config'] == before['config']
        assert after['series'] == before['series']


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('fixed', [False, True])
def test_public_log_axis_replay_preserves_policy_and_current_decade_layout(backend, fixed):
    with fg.Figure(backend=backend) as fig:
        ax = fig.axes[0]
        ax.plot([1, 10, 1000], [1, 2, 4], id='signal')
        ax.set_xlim(1, 1000); ax.set_xscale('log')
        ax.xaxis.set_major_locator(LogLocator(100))
        if not fixed:
            ax.xaxis.set_tick_auto(True)
        before = fig.get_settings()
        assert before['config']['bottom_x']['major_spacing'] == 2
        exec(fig.to_code(), {'fig': fig})
        assert fig.get_settings() == before


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('mode', ['api', 'exact'])
def test_code_replay_preserves_independently_expected_destination_arrays(backend, mode):
    with fg.Figure(backend=backend) as source, fg.Figure(backend=backend) as target:
        source.axes[0].plot([0, 1000], [1, 4], id='signal')
        x = np.array([10., 20.], dtype=np.float64)
        y = np.array([9., 8.], dtype=np.float64)
        target.axes[0].plot(x, y, id='signal')
        source.apply_style('report')
        source.axes[0].set_xlim(0, 1000)
        exec(source.to_code(mode=mode), {'fig': target})
        # Read actual native GPU buffers / browser transfer bytes independently
        # of settings and upload counts. This probe is last and discards target.
        assert_renderer_columns(target, {'signal/x': x, 'signal/y': y})
