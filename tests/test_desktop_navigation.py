"""Real X11 events: independent windows, modifier gestures and axis transforms."""
import copy
import json
import math
import os
import shutil
import subprocess
import time

import figgy
import pytest
from figgy.desktop import poll_events


@pytest.mark.skipif(not os.environ.get("DISPLAY") or not shutil.which("xdotool"), reason="requires X11 and xdotool")
def test_multiple_windows_zoom_pan_and_help():
    first, ax = figgy.subplots(backend="native")
    second, bx = figgy.subplots(backend="native")
    ax.plot([1, 10, 100], [1, 10, 100], id="signal")
    bx.plot([1, 10, 100], [100, 10, 1], id="signal")
    ax.set_title("First"); bx.set_title("Second")

    def xdo(*args):
        return subprocess.check_output(["xdotool", *map(str, args)], text=True).strip()

    def pump():
        for _ in range(20):
            poll_events(); time.sleep(.004)

    def ids():
        return set(xdo("search", "--pid", os.getpid(), "--name", "^Figgy$").splitlines())

    h1 = first.show(block=False)
    pump(); wid = next(iter(ids()))
    h2 = second.show(block=False)
    try:
        pump()
        assert len(ids()) == 2
        assert json.loads(h1.info_json())["surface_frames"] > 0
        assert json.loads(h2.info_json())["surface_frames"] > 0
        assert first.info["gpu_context_id"] == second.info["gpu_context_id"]
        original_second = copy.deepcopy(second.get_settings())
        xdo("windowraise", wid); xdo("windowfocus", wid); pump()

        def info(): return json.loads(h1.info_json())
        def cfg(): return first.get_settings()["config"]
        def position(rx=.3, ry=.35):
            r = info()["decorations"]["data_area"]
            x, y = round(r[0]+r[2]*rx), round(r[1]+r[3]*ry)
            xdo("mousemove", "--window", wid, x, y); pump()
            return x, y, r
        def wheel(modifier=None, button=4):
            if modifier: xdo("keydown", modifier); pump()
            xdo("click", button); pump()
            if modifier: xdo("keyup", modifier); pump()
        def span(node): return node["max"]-node["min"]

        assert info()["controls"]["navigation_help"][1] < info()["chart_panel"][1]
        def at_pointer(config, key, pixel, rect):
            node = config[key]
            fraction = (pixel[0]-rect[0])/rect[2] if key == "bottom_x" else 1-(pixel[1]-rect[1])/rect[3]
            if node["inverted"]: fraction = 1-fraction
            low, high = node["min"], node["max"]
            if node["scale"] == "Logarithmic":
                return 10**(math.log10(low)+(math.log10(high)-math.log10(low))*fraction)
            return low+(high-low)*fraction

        def check_zoom(modifier):
            x, y, r = position(.23, .68)
            start = cfg()
            for button in (4, 5):
                before = cfg(); old_rect = info()["decorations"]["data_area"]
                wheel(modifier, button); after = cfg()
                new_rect = info()["decorations"]["data_area"]
                for key in ("bottom_x", "left_y"):
                    active = modifier is None or (modifier == "ctrl" and key == "bottom_x") or (modifier == "shift" and key == "left_y")
                    if not active:
                        assert after[key] == before[key]
                    else:
                        assert (span(after[key]) < span(before[key])) == (button == 4)
                        assert at_pointer(before,key,(x,y),old_rect) == pytest.approx(at_pointer(after,key,(x,y),new_rect),rel=2e-6,abs=1e-7)
                assert first.info["column_uploads"] == 2
            # The same pointer anchors zoom-in and zoom-out, so reversing the
            # wheel restores both ranges rather than drifting toward the center.
            for key in ("bottom_x", "left_y"):
                assert cfg()[key]["min"] == pytest.approx(start[key]["min"])
                assert cfg()[key]["max"] == pytest.approx(start[key]["max"])

        for modifier in ("ctrl", "shift", None):
            check_zoom(modifier)
        x, y, _ = position(.4, .3); before = cfg()
        xdo("mousedown", 1); pump()
        for step in range(1, 5):
            xdo("mousemove", "--window", wid, x+step*10, y+step*5); pump()
        xdo("mouseup", 1); pump(); after = cfg()
        assert span(after["bottom_x"]) == pytest.approx(span(before["bottom_x"]))
        assert span(after["left_y"]) == pytest.approx(span(before["left_y"]))
        assert after["bottom_x"]["min"] < before["bottom_x"]["min"]
        assert after["left_y"]["min"] > before["left_y"]["min"]
        assert info()["selected"] is None
        assert after.get("picked_data") is None
        # Anchor and axis isolation hold for both logarithmic and inverted axes.
        ax.set_xlim(1, 1000); ax.set_ylim(1, 1000)
        ax.set_xscale("log"); ax.set_yscale("log"); pump()
        for modifier in ("ctrl", "shift", None):
            check_zoom(modifier)
        inverted = first.get_settings()
        for key in ("bottom_x", "top_x", "left_y", "right_y"):
            inverted["config"][key]["inverted"] = True
        first.apply_settings(inverted); pump()
        for modifier in ("ctrl", "shift", None):
            check_zoom(modifier)
        assert second.get_settings() == original_second
        assert first.info["column_uploads"] == second.info["column_uploads"] == 2
        h1.close(); pump()
        assert not h2.closed and json.loads(h2.info_json())["surface_frames"] > 0
        bx.set_title("Second remains editable"); pump()
        assert "Second remains editable" in second.to_code()
    finally:
        h1.close(); h2.close(); pump()
        first.close(); second.close()
