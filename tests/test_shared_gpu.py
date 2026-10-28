"""Public behavior of shared native resources and independent SSOT documents."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import figgyplot as figgy


def test_multiple_figures_isolate_same_ids_picks_exports_and_close():
    first, ax = figgy.subplots(backend='native', figsize=(5, 4), dpi=100)
    second, bx = figgy.subplots(backend='native', figsize=(5, 4), dpi=100)
    try:
        ax.imshow(np.array([[0., 1.], [1., 0.]]), id='signal')
        bx.imshow(np.array([[1., 0.], [0., 1.]]), id='signal')
        ax.set_title('first'); bx.set_title('second')
        assert first.info['gpu_context_id'] == second.info['gpu_context_id']
        assert first.info['figure_id'] != second.info['figure_id']
        assert first.info['pool_used_bytes'] == second.info['pool_used_bytes']
        image = first.render_rgba()
        assert not np.array_equal(image, second.render_rgba())
        assert np.array_equal(image, first.render_rgba())
        # Renderer fitting/export/picking also need scoped matrix/series ids.
        second.fit()
        import json
        for figure in (first, second):
            bounds = json.loads(figure._native.bounds_json('data_area'))['rect']
            x, y, w, h = bounds
            assert figure.select(x+w/3, y+h/3) == 'signal'
            assert figure.get_settings()['config']['picked_data']['refs'][0]['series_id'] == 'signal'
            assert figure.get_settings()['series'][0]['series_id'] == 'signal'
            assert 'figgy/' not in figure.to_code()
            assert len(figure.to_png(scale=2)) > 100
        before = second.render_rgba()
        used = second.info['pool_used_bytes']
        first.close()
        assert second.info['active_figures'] == 1
        assert second.info['pool_used_bytes'] < used
        assert second.info['column_uploads'] == 4
        assert np.array_equal(before, second.render_rgba())
    finally:
        first.close(); second.close()


def test_closed_figures_reuse_context_and_explicit_release_resets_it():
    code = '''import gc, numpy as np, figgyplot as figgy
assert figgy.release_gpu() is False
fig, ax = figgy.subplots(backend="native", pool_bytes=4096)
ax.plot(np.arange(4000, dtype=np.float32))
assert fig.info["pool_capacity_bytes"] > 4096
identity = fig.info["gpu_context_id"]
prepared = fig.prepare()
try: figgy.release_gpu()
except RuntimeError as e: assert "close all" in str(e)
else: raise AssertionError("released a live Figure")
fig.close()
fig, ax = figgy.subplots(backend="native")
assert fig.info["gpu_context_id"] == identity
assert fig.info["pool_used_bytes"] == 0 and fig.info["active_figures"] == 1
assert len(fig.prepare()["stages"]) < len(prepared["stages"])
ax.plot([0, 1], [1, 0])
fig.close()
# GC without explicit close must also release ownership, without a GIL deadlock.
fig, ax = figgy.subplots(backend="native")
ax.plot([0, 1], [1, 0])
del fig, ax
gc.collect()
assert figgy.release_gpu() is True
fig, ax = figgy.subplots(backend="native")
assert fig.info["gpu_context_id"] != identity and fig.info["pool_used_bytes"] == 0
fig.close()
assert figgy.release_gpu() is True
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_concurrent_figures_share_initialization_without_gil_deadlock():
    code = '''import threading, numpy as np, figgyplot as figgy
start = threading.Barrier(4)
identities, errors = [], []
def work(index):
    try:
        start.wait()
        with figgy.Figure(backend="native") as fig:
            fig.axes[0].plot(np.arange(10_000, dtype=np.float32), id="same-id")
            identities.append(fig.info["gpu_context_id"])
            for n in range(4):
                fig.axes[0].set_title(str(index))
                assert fig.render_rgba().shape == (600, 960, 4)
    except Exception as e: errors.append(repr(e))
threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
for t in threads: t.start()
for t in threads: t.join()
assert not errors, errors
assert len(identities) == 4 and len(set(identities)) == 1
with figgy.Figure(backend="native") as fig:
    assert fig.info["active_figures"] == 1 and fig.info["pool_used_bytes"] == 0
figgy.release_gpu()
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr


def test_failed_second_figure_upload_keeps_existing_data_and_rolls_back():
    first, ax = figgy.subplots(backend='native')
    second, bx = figgy.subplots(backend='native')
    try:
        ax.plot([0, 1, 2], [0, 1, 0], id='signal')
        image, settings = first.render_rgba(), first.get_settings()
        limit = first.info['adapter']['maximum_column_pool_bytes']
        if limit > 128 * 1024**2:
            pytest.skip('bound the allocation failure test to software adapter limits')
        used = first.info['pool_used_bytes']
        values = np.zeros(limit // 16 + 1, dtype=np.float32)
        # First column fits, second exceeds the shared pool's binding ceiling.
        with pytest.raises(MemoryError, match='requested_gpu_bytes=.*pool_used_bytes='):
            bx.plot(values, values, id='signal')
        assert second.info['columns'] == 0
        assert first.info['pool_used_bytes'] == used
        assert first.get_settings() == settings
        assert np.array_equal(image, first.render_rgba())
    finally:
        first.close(); second.close()


def test_text_size_color_and_font_change_render_and_replay():
    with figgy.Figure(backend='native') as figure:
        ax = figure.axes[0]
        ax.plot([0, 1], [1, 0]); ax.set_title('Typography')
        before = figure.render_rgba()
        ax.set_title('Typography', color='red', fontsize=24, font='DejaVu Serif')
        figure.update('tick_labels_bottom', font='DejaVu Serif', fontsize=14, color='blue')
        state = figure.get_settings()
        assert state['config']['chart_title']['text']['font'] == 'DejaVu Serif'
        assert state['config']['bottom_x']['label_style']['label_font'] == 'DejaVu Serif'
        assert not np.array_equal(before, figure.render_rgba())
        if Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf').exists():
            serif = figure.render_rgba()
            ax.set_title('Typography', font='')
            assert not np.array_equal(serif, figure.render_rgba())
            figure.apply_settings(state)
        with figgy.Figure(backend='native') as other:
            other.axes[0].plot([0, 1], [1, 0])
            exec(figure.to_code('other', mode='exact'), {'other': other})
            assert other.get_settings() == state
            assert np.array_equal(figure.render_rgba(), other.render_rgba())
