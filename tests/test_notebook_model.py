"""Kernel document/transfer policy is testable without any GPU initialization."""
import json
import asyncio
import numpy as np
import pytest
from figgyplot import subplots

def test_gpu_free_binary_snapshot_release_and_revision(monkeypatch):
    import importlib
    module = importlib.import_module("figgyplot.figure")
    monkeypatch.setattr(module, 'NativeFigure', lambda *a: pytest.fail('kernel must not initialize GPU'))
    fig, ax = subplots(backend='webgpu')
    x = np.arange(16, dtype=np.float32)
    ax.plot(x, x * 2, id='line')
    x[:] = -99
    widget = fig.widget()
    assert widget.manifest[0]['dtype'] == 'float32'
    assert np.frombuffer(widget.columns[0], dtype='<f4')[3] == 3
    assert widget.state['settings']['series'][0]['series_id'] == 'line'
    old = fig.revision
    settings = fig.get_settings()
    settings['config']['chart_title']['text']['segments'] = [{'text':'X','bold':False,'italic':False,'underline':False,'superscript':False,'subscript':False,'greek':False}]
    widget._command(widget, {'action':'edit','sequence':1,'revision':old,'settings':settings}, [])
    assert fig.revision > old
    assert 'X' in fig.to_code()
    assert widget.state['code'] == fig.to_code()
    assert 'ax.set_title(' in widget.state['code']
    settings['config']['bottom_x']['min'] = 999
    widget._command(widget, {'action':'edit','sequence':2,'revision':old,'settings':settings}, [])
    assert fig.get_settings()['config']['bottom_x']['min'] != 999
    assert widget.wasm[:4] == b'\x00asm'
    widget._command(widget, {'action':'ready','info':{'column_uploads':2}}, [])
    assert widget.columns == [] and widget.wasm == b''
    assert fig._native.columns == {}
    with pytest.raises(RuntimeError, match='sealed'):
        ax.plot([1,2],[1,2])
    fig.close()

def test_native_notebook_fallback_is_explicit():
    # No native construction is necessary to assert backend policy.
    fig, _ = subplots(backend='webgpu')
    with pytest.raises(RuntimeError, match='native'):
        fig.widget(backend='png')
    with pytest.raises(RuntimeError, match='asynchronous'):
        fig.to_png()
    fig.close()


def test_positive_log_bounds_survive_binary_transfer_release():
    fig, ax = subplots(backend='webgpu')
    try:
        ax.imshow(np.array([[-2., 0.], [10., 1000.]]), extent=(-1, 3, -2, 4), origin='lower')
        widget = fig.widget()
        bounds = widget.state['log_bounds']
        assert bounds['z'] == pytest.approx((10., 1000.))
        series = fig.get_settings()['series']
        widget._command(widget, {'action':'ready','info':{'column_uploads':4}}, [])
        assert widget.columns == [] and fig._native.columns == {}
        ax.set_xscale('log')
        ax.set_yscale('log')
        assert widget.state['log_bounds'] == bounds
        config = fig.get_settings()['config']
        for axis, dimension in [('bottom_x', 'x'), ('left_y', 'y')]:
            assert (config[axis]['min'], config[axis]['max']) == pytest.approx(bounds[dimension])
            assert config[axis]['scale'] == 'Logarithmic'
        assert fig.get_settings()['series'] == series
    finally:
        fig.close()

def test_manual_preparation_requires_a_mounted_view_and_propagates_result():
    fig, ax = subplots(backend='webgpu')
    ax.plot([0, 1], [1, 0])
    widget = fig.widget(auto_prepare=False)
    assert not widget.auto_prepare
    with pytest.raises(RuntimeError, match='asynchronous'):
        fig.prepare()
    async def check():
        with pytest.raises(RuntimeError, match='prepare_async'):
            await fig.to_png_async()
        with pytest.raises(TimeoutError):
            await fig.prepare_async(timeout=.01)
        widget._command(widget, {'action':'mounted','client':'test-view'}, [])
        expected = {'backend':'webgpu','ready':True,'persistent_cache_supported':False}
        def send(message, **kwargs):
            assert message['action'] == 'prepare' and message['client'] == 'test-view'
            widget._command(widget, {'action':'result','id':message['id'],'result':expected}, [])
        widget.send = send
        assert await fig.prepare_async() == expected
        assert not widget._pending
        fig.close()
        with pytest.raises(RuntimeError, match='closed'):
            await widget.request('prepare', timeout=.01)
        with pytest.raises(RuntimeError, match='closed'):
            await fig.prepare_async(timeout=.01)
    asyncio.run(check())


def test_widget_created_before_async_loop_recovers_across_separate_loops():
    fig, ax = subplots(backend="webgpu")
    ax.plot([0, 1], [1, 0])
    widget = fig.widget(auto_prepare=False)
    try:
        for _ in range(2):
            with pytest.raises(TimeoutError, match="display the widget"):
                asyncio.run(fig.prepare_async(timeout=0.01))
            assert not widget._mounted_event._waiters and not widget._pending
        widget._command(widget, {"action": "mounted", "client": "reconnected"}, [])
        expected = {"ready": True, "backend": "webgpu"}
        def send(message, **kwargs):
            widget._command(widget, {"action": "result", "id": message["id"], "result": expected}, [])
        widget.send = send
        assert asyncio.run(fig.prepare_async()) == expected
    finally:
        fig.close()


def test_empty_subplots_can_fit_and_copy_snap_settings():
    fig, axes = subplots(1, 2, backend="webgpu")
    target, target_axes = subplots(1, 2, backend="webgpu")
    with fig, target:
        axes[0].plot([0, 1], [2, 3], id="line")
        target_axes[0].plot([0, 1], [4, 5], id="line")
        assert fig.fit().tight_layout() is fig
        fig.configure(config={"snap_to_guides": False})
        exec(fig.to_code(), {"fig": target})
        assert target.get_settings()["config"]["snap_to_guides"] is False


def test_radar_value_range_preserves_float32_transfer():
    fig, ax = subplots(backend="webgpu")
    with fig:
        ax.radar(["N", "E", "S"], np.asarray([1, 2, 3], dtype=np.float32), value_range=(0, 10))
        assert ax.get_ylim() == (0, 10)
        assert [(column["dtype"], column["bytes"]) for column in fig.widget().manifest] == [
            ("float32", 12), ("float32", 12),
        ]


def test_widget_seals_at_display_and_isolates_failed_views():
    async def check():
        fig, ax = subplots(backend="webgpu")
        with fig:
            ax.plot([0, 1], [1, 0])
            widget = fig.widget()
            ax.plot([0, 1], [2, 3])
            assert len(widget.manifest) == 4
            widget._repr_mimebundle_()
            with pytest.raises(RuntimeError, match="sealed after display"):
                ax.plot([0, 1], [0, 1])
            for action, client in [("mounted", "first"), ("ready", "first"),
                                   ("mounted", "second"), ("failed", "second")]:
                widget._command(widget, {"action": action, "client": client, "error": "view failed"}, [])
            assert widget.status == "ready"

            def send(message, **kwargs):
                assert message["client"] == "first"
                widget._command(widget, {"action": "result", "id": message["id"]}, [])

            widget.send = send
            assert await fig.sync() == fig.get_settings()

    asyncio.run(check())
