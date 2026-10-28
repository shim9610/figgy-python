"""Actual X11 native toolbar/inspector/surface interactions."""

import json
import os
import shutil
import subprocess
import time
import numpy as np
import pytest
from native_input import click as send_native_click
from figgyplot import Figure, subplots, release_gpu
from figgyplot.desktop import poll_events
from object_navigation import ensure_native_control_visible


def test_surface_drag_resize_reopen_and_no_png(tmp_path):
    tool = shutil.which("xdotool")
    if not os.environ.get("DISPLAY") or not tool:
        pytest.skip("requires X11 display and xdotool")
    release_gpu()
    fig, ax = subplots(backend="native", pool_bytes=4096)
    ax.plot(
        np.arange(32, dtype=np.float32),
        np.arange(32, dtype=np.float32),
        id="signal",
        label="Signal",
    )
    ax.set_title("Editable title")
    handle = fig.show(block=False)

    def pump():
        for _ in range(14):
            poll_events()
            time.sleep(0.005)

    def info():
        return json.loads(handle.info_json())

    def xdo(*a):
        return subprocess.check_output([tool, *map(str, a)], text=True).strip()

    def point(rect):
        return round(rect[0] + rect[2] / 2), round(rect[1] + rect[3] / 2)

    def click_rect(rect, double=False):
        x, y = point(rect)
        xdo("mousemove", "--window", wid, x, y)
        pump()
        send_native_click(xdo,double=double)
        pump()

    def click(name):
        ensure_native_control_visible(info, xdo, pump, wid, name)
        click_rect(info()["controls"][name])

    def type_field(name, value):
        click(name)
        xdo("key", "ctrl+a")
        xdo("type", str(value))
        pump()

    try:
        pump()
        wid = xdo("search", "--pid", os.getpid(), "--name", "Figgy").splitlines()[-1]
        xdo("windowfocus", wid)
        pump()
        assert not info()["properties_open"]
        initial_width = info()["chart_panel"][2]
        click_rect(info()["decorations"]["chart_title"])
        assert info()["properties_open"] and info()["selected"] == "chart_title"
        assert info()["chart_panel"][2] == initial_width
        # With properties already open, dragging does not change the stage.
        before = fig.revision
        x, y = point(info()["decorations"]["chart_title"])
        xdo("mousemove", "--window", wid, x, y)
        pump()
        xdo("mousedown", 1)
        pump()
        for step in range(1, 5):
            xdo("mousemove", "--window", wid, x + step * 5, y + step * 2)
            pump()
        xdo("mouseup", 1)
        pump()
        assert (
            fig.revision > before
            and fig.get_settings()["config"]["chart_title"]["offset_x"] > 0
        )
        type_field("text", "Rust edited")
        type_field("font", "DejaVu Serif")
        ensure_native_control_visible(info, xdo, pump, wid, "font_size")
        click_rect(info()["controls"]["font_size"], double=True)
        xdo("key", "ctrl+a")
        xdo("type", "36")
        xdo("key", "Return")
        pump()
        assert "Rust edited" in fig.to_code()
        assert (
            fig.get_settings()["config"]["chart_title"]["text"]["font"]
            == "DejaVu Serif"
        )
        assert fig.get_settings()["config"]["chart_title"]["text"]["font_size"] == 36
        # The object hierarchy is visible and collapses without a popup.
        toggles = [key for key in info()["controls"] if key.startswith("tree_toggle:figure/")]
        assert len(toggles) == 1 and "tree:panel/main" in info()["controls"]
        click(toggles[0])
        assert "tree:panel/main" not in info()["controls"]
        click(toggles[0])
        assert "tree:panel/main" in info()["controls"]
        xdo("windowsize", wid, 1350, 760)
        pump()
        assert info()["surface_size"] == [1350, 760]
        assert info()["surface_frames"] > 1 and info()["column_uploads"] == 2
        assert info()["rgba_readbacks"] == 0 and info()["png_encodes"] == 0
        before_axis = fig.get_settings()["config"]["bottom_x"]
        x, y = point(info()["decorations"]["data_area"])
        xdo("mousemove", "--window", wid, x, y)
        pump()
        xdo("keydown", "ctrl")
        pump()
        xdo("click", 4)
        xdo("keyup", "ctrl")
        pump()
        zoomed = fig.get_settings()["config"]["bottom_x"]
        assert zoomed["max"] - zoomed["min"] < before_axis["max"] - before_axis["min"]
        click("fit")
        fitted = fig.get_settings()["config"]["bottom_x"]
        assert fitted["min"] <= 0 and fitted["max"] >= 31
        click("copy")
        clip = shutil.which("xclip")
        if clip:
            copied = subprocess.check_output(
                [clip, "-selection", "clipboard", "-o", "-t", "UTF8_STRING"], text=True, timeout=5
            )
            assert "ax.set_title(" in copied
            assert "json.loads" not in copied
            assert copied == fig.to_code()
            exec(copied, {"fig": fig})
        click("close_properties")
        click("save")
        type_field("save_path", tmp_path / "ui.png")
        assert not info()["properties_open"]
        # Wheel over a popup must not zoom the chart below it.
        xdo("click", 4)
        pump()
        assert fig.get_settings()["config"]["bottom_x"] == fitted
        click("save_confirm")
        assert (tmp_path / "ui.png").read_bytes().startswith(b"\x89PNG")
        fig.savefig(tmp_path / "native.png")
        pump()
        assert (tmp_path / "native.png").read_bytes().startswith(b"\x89PNG")
        from PIL import Image

        with (
            Image.open(tmp_path / "ui.png") as ui_png,
            Image.open(tmp_path / "native.png") as python_png,
        ):
            assert ui_png.size == python_png.size == (960, 600)
            assert np.array_equal(np.asarray(ui_png), np.asarray(python_png))
        assert not info()["properties_open"]
        handle.close()
        pump()
        handle = fig.show(block=False)
        pump()
        assert info()["column_uploads"] == 2 and info()["png_encodes"] == 2
        capacity = fig.info["pool_capacity_bytes"]
        other, other_ax = subplots(backend="native")
        other_ax.scatter(
            np.arange(4000, dtype=np.float32),
            np.arange(4000, dtype=np.float32),
            id="signal",
        )
        second = other.show(block=False)
        pump()
        assert json.loads(second.info_json())["surface_frames"] > 0
        assert (
            fig.info["gpu_context_id"]
            == other.info["gpu_context_id"]
            == json.loads(second.info_json())["gpu_context_id"]
        )
        assert fig.info["pool_capacity_bytes"] > capacity
        other.close()
        pump()
        assert info()["surface_frames"] > 0 and not handle.closed
        assert fig.info["columns"] == 2 and fig.info["active_figures"] == 1
    finally:
        handle.close()
        pump()
        fig.close()


def test_surface_heatmap_edits_sync_without_image_transport():
    tool = shutil.which("xdotool")
    if not os.environ.get("DISPLAY") or not tool:
        pytest.skip("requires X11 display and xdotool")
    fig, ax = subplots(backend="native")
    ax.imshow(np.array([[-1.0, 0.0], [1.0, 2.0]], dtype=np.float32), id="Temperature")
    handle = fig.show(block=False)

    def pump():
        for _ in range(14):
            poll_events()
            time.sleep(0.005)

    def info():
        return json.loads(handle.info_json())

    def xdo(*args):
        return subprocess.check_output([tool, *map(str, args)], text=True).strip()

    def click_rect(rect, double=False):
        x, y = round(rect[0] + rect[2] / 2), round(rect[1] + rect[3] / 2)
        xdo("mousemove", "--window", wid, x, y)
        pump()
        send_native_click(xdo,double=double)
        pump()

    try:
        pump()
        wid = xdo("search", "--pid", os.getpid(), "--name", "Figgy").splitlines()[-1]
        xdo("windowfocus", wid)
        pump()
        click_rect(info()["decorations"]["data_area"])
        assert info()["selected"] == "Temperature" and info()["properties_open"]
        for name, value in [("vmin", "-2"), ("vmax", "4")]:
            ensure_native_control_visible(info, xdo, pump, wid, name)
            click_rect(info()["controls"][name], double=True)
            xdo("key", "ctrl+a")
            xdo("type", "--", value)
            xdo("key", "Return")
            pump()
        # A picked heatmap also shows its sample details below the scrollable
        # properties. Scroll there before clicking controls below the viewport.
        rect = info()["controls"]["vmax"]
        xdo("mousemove", "--window", wid, round(rect[0] + rect[2] / 2), round(rect[1] + rect[3] / 2))
        xdo("click", "--repeat", 3, "--delay", 70, 5)
        pump()
        ensure_native_control_visible(info, xdo, pump, wid, "colormap")
        click_rect(info()["controls"]["colormap"])
        click_rect(info()["controls"]["colormap_Magma"])
        bar = fig.get_settings()["config"]["colorbar"]
        assert bar["axis"]["min"] == -2 and bar["axis"]["max"] == 4
        assert bar["colormap"] == "Magma"
        assert info()["column_uploads"] == 4
        assert info()["rgba_readbacks"] == info()["png_encodes"] == 0
        # The UI transport above must not read images back. Explicitly verify
        # exported behavior afterwards; public cmap names need not use the
        # renderer enum's spelling in the generated source text.
        state = fig.get_settings()
        code = fig.to_code()
        with Figure(backend="native") as restored:
            restored.axes[0].imshow(
                np.array([[-1.0, 0.0], [1.0, 2.0]], dtype=np.float32),
                id="Temperature",
            )
            uploads = restored.info["column_uploads"]
            exec(code, {"fig": restored})
            assert restored.get_settings()["config"] == state["config"]
            assert restored.get_settings()["series"] == state["series"]
            assert restored.info["column_uploads"] == uploads
            np.testing.assert_array_equal(fig.render_rgba(), restored.render_rgba())
    finally:
        handle.close()
        pump()
        fig.close()
