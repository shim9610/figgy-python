import copy
import io

import numpy as np
from PIL import Image
import pytest

import figgy
from figgy.editor import EditorSession


@pytest.fixture
def plot():
    fig, ax = figgy.subplots(figsize=(6, 4), dpi=100, pool_bytes=8 * 1024**2)
    yield fig, ax
    fig.close()


def test_numpy_uploads_are_reused_and_source_mutations_do_not_change_chart(plot):
    fig, ax = plot
    x = np.linspace(0, 10, 500, dtype=np.float32)
    y = np.sin(x)
    artist, = ax.plot(x, y)
    before = fig.render_rgba().copy()
    y[:] = 1000
    assert np.array_equal(before, fig.render_rgba())
    artist.set_color("red")
    assert not np.array_equal(before, fig.render_rgba())
    assert fig.info["column_uploads"] == 2


def test_exported_python_replays_layout_and_style(plot):
    fig, ax = plot
    x = np.linspace(0, 10, 300)
    artist, = ax.plot(x, np.sin(x), id="signal", label="Signal")
    ax.set_title("Edited title", color="purple")
    ax.legend()
    assert fig.drag("chart_title", 12.5, -2)
    artist.set_linewidth(3)
    state = fig.get_settings()
    image = fig.render_rgba().copy()
    code = fig.to_code("restored")
    with figgy.Figure(figsize=(6, 4), dpi=100, pool_bytes=8 * 1024**2) as restored:
        restored.axes[0].plot(x, np.sin(x), id="signal", label="Signal")
        exec(code, {"restored": restored})
        assert restored.get_settings() == state
        assert np.array_equal(image, restored.render_rgba())


def test_bad_settings_and_stale_editor_commands_are_atomic(plot):
    fig, ax = plot
    ax.plot([0, 1, 2], [0, 1, 0])
    before = fig.get_settings()
    revision = fig.revision
    invalid = copy.deepcopy(before)
    invalid["config"]["bottom_x"]["min"] = invalid["config"]["bottom_x"]["max"]
    with pytest.raises(ValueError): fig.apply_settings(invalid)
    unknown = copy.deepcopy(before)
    unknown["config"]["typo"] = True
    with pytest.raises(ValueError, match="unknown"): fig.apply_settings(unknown)
    assert fig.get_settings() == before and fig.revision == revision
    editor = EditorSession(fig)
    state = editor.dispatch({"action": "update", "target": "chart_title", "properties": {"text": "bad"}, "revision": revision - 1, "request_id": 1})
    assert "stale" in state["error"]
    assert fig.get_settings() == before


def test_noncontiguous_input_and_png_scale(plot):
    fig, ax = plot
    x = np.linspace(0, 10, 1000)[::2]
    ax.plot(x, np.sin(x))
    output = io.BytesIO()
    fig.savefig(output, scale=2)
    image = Image.open(io.BytesIO(output.getvalue()))
    assert image.size == (1200, 800)
    pixels = np.array(image)
    assert np.any(pixels[100:-100, 100:-100, :3] < 100)


def test_heatmap_orientation_and_series_selection(plot):
    fig, ax = plot
    ax.imshow(np.array([[0., 0., 0.], [1., 1., 1.]]), origin="lower", id="image")
    image = fig.render_rgba()
    cfg = fig.get_settings()["config"]
    assert cfg["colorbar"]["axis"]["min"] == 0
    assert cfg["left_y"]["inverted"] is False
    # Heatmap cells are picked by the renderer, not inferred in Python.
    bounds = json_bounds(fig, "data_area")
    x, y, w, h = bounds["rect"]
    assert fig.select(x + w / 2, y + h / 2) == "image"


def json_bounds(fig, target):
    import json
    return json.loads(fig._native.bounds_json(target))


def test_widget_command_updates_native_state_and_png(plot):
    fig, ax = plot
    ax.scatter([0, 1, 2], [0, 1, 0], id="points")
    widget = fig.widget()
    before = widget.image
    widget._command(widget, {"action": "update", "target": "points", "properties": {"color": "red"}, "revision": fig.revision, "request_id": 3}, [])
    assert widget.state["last_request"] == 3
    assert widget.state["error"] == ""
    assert widget.image != before
    assert fig.get_settings()["series"][0]["render_type"]["Scatter"]["scatter"]["point_color"]["r"] == 1
    widget.close()


def test_invalid_arrays_do_not_leak_columns(plot):
    fig, ax = plot
    for y in ([np.nan, np.nan], ["a", "b"]):
        with pytest.raises(ValueError): ax.plot([0, 1], y)
    assert fig.info["columns"] == 0
    with pytest.raises(ValueError): ax.plot([0, 1], [0, 1], linewidth=-1)
    ax.plot([0, 1], [0, 1])
    fig.close()
    with pytest.raises(RuntimeError, match="closed"): fig.render_rgba()


def test_resident_pool_grows_without_changing_modes():
    with figgy.Figure(pool_bytes=4096) as fig:
        fig.axes[0].plot(np.arange(4000, dtype=np.float64))
        assert fig.info["pool_capacity_bytes"] > 4096
        assert fig.info["allocation_mode"] == "resident"
        assert fig.render_rgba().shape == (600, 960, 4)


def test_device_limit_error_preserves_existing_plot(plot):
    fig, ax = plot
    ax.plot([0, 1, 2], [0, 1, 0])
    before = fig.render_rgba().copy()
    limit = fig.info["adapter"]["maximum_column_pool_bytes"]
    # Avoid a hardware-specific multi-GB test; software Vulkan's 128 MiB
    # binding ceiling gives a bounded, real allocation failure here.
    if limit > 128 * 1024**2:
        pytest.skip("device binding limit too large for bounded CI failure test")
    oversized = np.zeros(limit // 8 + 1, dtype=np.float32)
    with pytest.raises(MemoryError, match="requested_gpu_bytes=.*adapter_column_pool_limit_bytes="):
        ax.plot(oversized)
    assert fig.info["columns"] == 2
    assert np.array_equal(before, fig.render_rgba())
