"""Real X11 clicks exercise radial editing and the Milkyway UI restriction."""
import json
import os
import shutil
import subprocess
import time

import pytest
import figgyplot as figgy
from figgyplot.desktop import poll_events

requires_x11 = pytest.mark.skipif(
    not os.environ.get("DISPLAY") or not shutil.which("xdotool") or not shutil.which("xclip") or not shutil.which("wmctrl"),
    reason="requires X11, xdotool, xclip and wmctrl",
)


class Inputs:
    def __init__(self, window):
        self.window = window
        self.pump()
        self.wid = self.xdo("search", "--pid", os.getpid(), "--name", "^Figgy$").splitlines()[-1]
        # A window manager may reuse an offscreen/right-edge placement after
        # earlier tests; keep the expanding inspector and popups on the display.
        self.xdo("windowmove", self.wid, 20, 40)
        self.xdo("windowraise", self.wid)
        self.xdo("windowfocus", self.wid)
        self.pump()

    @staticmethod
    def xdo(*args):
        return subprocess.check_output(["xdotool", *map(str, args)], text=True).strip()

    @staticmethod
    def pump():
        for _ in range(25):
            poll_events()
            time.sleep(.004)

    def info(self):
        return json.loads(self.window.info_json())

    def click_rect(self, rect):
        x, y = round(rect[0]+rect[2]/2), round(rect[1]+rect[3]/2)
        # X11 may suppress same-position motion left over from an earlier window.
        # Deliver a real motion event before pressing on the new chart surface.
        self.xdo("mousemove", "--window", self.wid, x+8, y+8)
        self.pump()
        self.xdo("mousemove", "--window", self.wid, x, y)
        self.pump()
        self.xdo("mousedown", 1)
        self.pump()
        self.xdo("mouseup", 1)
        self.pump()

    def click(self, name):
        self.click_rect(self.info()["controls"][name])

    def key(self, key):
        self.xdo("key", key)
        self.pump()


@requires_x11
def test_radial_native_edit_copy_selection_and_no_readback(tmp_path):
    fig, ax = figgy.subplots(backend="native")
    ax.pie([40, 30, 0, 30], labels=["A", "B", "Zero", "C"], material="ceramic")
    ax.set_title("Radial input test")
    handle = fig.show(block=False)
    try:
        inputs = Inputs(handle)
        before = inputs.info()
        assert before["chart_family"] == "radial" and not before["error"]
        panel, size = before["chart_panel"], before["surface_size"]
        # A real pie surface hit opens properties and selects a source category.
        inputs.click_rect([panel[0] + panel[2]*0.65, panel[1]+panel[3]*0.4, 0, 0])
        assert inputs.info()["selected"] is not None
        assert inputs.info()["properties_open"]
        assert inputs.info()["surface_size"] == [size[0]+320, size[1]]
        assert inputs.info()["chart_panel"] == panel
        original = fig.get_settings()["radial"]["interaction"]["selected"]["index"]
        inputs.key("Right")
        selected = fig.get_settings()["radial"]["interaction"]["selected"]["index"]
        assert selected != original and selected != 2
        inputs.key("Escape")
        assert inputs.info()["selected"] is None
        inputs.click_rect(inputs.info()["controls"]["radial_title"])
        inputs.key("ctrl+a")
        inputs.xdo("type", "--clearmodifiers", "Reviewed donut")
        inputs.pump()
        assert fig.get_settings()["radial"]["title"] == "Reviewed donut"
        inputs.click("radial_material")
        inputs.click("radial_material_Wood")
        assert fig.get_settings()["radial"]["style"]["material"] == "Wood"
        inputs.click("copy")
        copied = subprocess.check_output(
            ["xclip", "-selection", "clipboard", "-o", "-t", "UTF8_STRING"], text=True)
        assert copied == fig.to_code() and "configure_radial" in copied
        assert "'value':" not in copied
        subprocess.run(["wmctrl", "-ir", inputs.wid, "-b", "add,maximized_vert,maximized_horz"], check=True)
        inputs.pump()
        assert inputs.info()["inspector_overlay"]
        assert inputs.info()["chart_panel"][2]/inputs.info()["chart_panel"][3] == pytest.approx(960/600, abs=.005)
        subprocess.run(["wmctrl", "-ir", inputs.wid, "-b", "remove,maximized_vert,maximized_horz"], check=True)
        inputs.pump()
        assert fig.info["column_uploads"] == fig.info["rgba_readbacks"] == fig.info["png_encodes"] == 0
        fig.savefig(tmp_path/"reviewed.png")
        assert (tmp_path/"reviewed.png").is_file()
    finally:
        handle.close()
        Inputs.pump()
        fig.close()


@requires_x11
def test_draw_style_menu_disables_milkyway_for_scatter():
    fig, ax = figgy.subplots(backend="native")
    ax.scatter([0, 1, 2], [0, 1, 0])
    handle = fig.show(block=False)
    try:
        inputs = Inputs(handle)
        inputs.click("draw_style_menu")
        inputs.click("style_milkyway")
        assert "draw_style" not in fig.get_settings()["config"]
        inputs.click("style_sketch")
        assert fig.get_settings()["config"]["draw_style"]["mode"] == "sketch"
        assert not inputs.info()["error"]
        assert fig.info["rgba_readbacks"] == fig.info["png_encodes"] == 0
    finally:
        handle.close()
        Inputs.pump()
        fig.close()
