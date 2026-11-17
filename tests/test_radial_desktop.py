"""Real X11 clicks exercise radial editing and the Milkyway UI restriction."""
import json
import os
import shutil
import subprocess
import time

import numpy as np
import pytest
import figgyplot as figgy
from figgyplot.desktop import poll_events
from native_input import click as send_native_click

requires_x11 = pytest.mark.skipif(
    not os.environ.get("DISPLAY") or not shutil.which("xdotool") or not shutil.which("xclip") or not shutil.which("wmctrl"),
    reason="requires X11, xdotool, xclip and wmctrl",
)


class Inputs:
    def __init__(self, window):
        self.window = window
        self.events = []
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

    @staticmethod
    def input_state(state):
        # Keep the event trace bounded without retaining 64 complete layout
        # snapshots inside each of 128 before/after input records.
        result={key:state.get(key) for key in ['surface_frames','pointer_sequence',
            'pointer_input','selected','revision','properties_open','surface_size',
            'scale_factor','controls','error']}
        result['scale_probe']=[entry for entry in state.get('layout_probe',[])
                               if entry.get('kind')=='scale_control'][-6:]
        return result

    def input_frame(self, *args):
        """Wait for the host to present an input instead of assuming a fixed delay.

        Software Vulkan can take longer than the usual 100 ms under CI load;
        sending the next gesture before a toolbar click is consumed loses input.
        """
        state = self.info();before = state['surface_frames']
        entry={'input':args,'before':self.input_state(state),'started':time.monotonic()}
        self.events.append(entry)
        del self.events[:-128]
        pointer = self.xdo('getmouselocation', '--shell') if args[0]=='mousemove' else None
        self.xdo(*args)
        if pointer is not None and pointer == self.xdo('getmouselocation', '--shell'):
            self.pump()
            entry['after']=self.input_state(self.info())
            entry['finished']=time.monotonic()
            return
        deadline = time.monotonic()+5
        while True:
            self.pump()
            state=self.info();entry['after']=self.input_state(state)
            entry['finished']=time.monotonic()
            if state['surface_frames'] > before:
                return
            assert time.monotonic() < deadline, self.info()

    def click_rect(self, rect):
        x, y = round(rect[0]+rect[2]/2), round(rect[1]+rect[3]/2)
        # X11 may suppress same-position motion left over from an earlier window.
        # Deliver a real motion event before pressing on the new chart surface.
        self.input_frame("mousemove", "--window", self.wid, x+8, y+8)
        self.input_frame("mousemove", "--window", self.wid, x, y)
        send_native_click(self.input_frame)

    def click(self, name):
        from object_navigation import ensure_native_control_visible
        ensure_native_control_visible(self.info, self.xdo, self.pump, self.wid, name)
        self.click_rect(self.info()["controls"][name])

    def key(self, key):
        self.xdo("key", key)
        self.pump()


@requires_x11
def test_click_remains_a_short_press_when_frames_are_slow(tmp_path,monkeypatch):
    with figgy.Figure(backend='native') as fig:
        fig.axes[0].pie([3,2,1])
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);original=inputs.pump
            def slow_frame():
                time.sleep(.9)  # Exceed egui's 0.8s click duration between frames.
                original()
            monkeypatch.setattr(inputs,'pump',slow_frame)
            inputs.click('properties')
            (tmp_path/'click-events.json').write_text(json.dumps(inputs.events))
            assert inputs.info()['pointer_input']['state']=='Released'
            assert inputs.info()['properties_open']
        finally:handle.close();Inputs.pump()


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
        # Clearing a data selection restores the global form. Layout remains a
        # separate mode rather than replacing unselected title/style controls.
        (tmp_path/'cleared-selection.json').write_text(json.dumps(dict(window=inputs.info(),settings=fig.get_settings()),indent=2))
        assert "radial_title" in inputs.info()["controls"]
        # Compare mode switches with the same pointer/hover state. Moving from
        # a slice to the toolbar legitimately clears renderer hover animation.
        rect=inputs.info()['controls']['layout_mode']
        inputs.input_frame('mousemove','--window',inputs.wid,round(rect[0]+rect[2]/2),round(rect[1]+rect[3]/2))
        deadline=time.monotonic()+3
        while fig.get_settings()['radial']['interaction']['hover_progress']!=0:
            assert time.monotonic()<deadline
            inputs.pump()
        before_layout=fig.get_settings()
        inputs.click("layout_mode")
        assert "plot_width" in inputs.info()["controls"]
        assert "radial_title" not in inputs.info()["controls"]
        (tmp_path/'layout-mode-settings.json').write_text(json.dumps(dict(before=before_layout,after=fig.get_settings(),window=inputs.info()),indent=2))
        assert fig.get_settings()==before_layout
        inputs.click("select_mode")
        assert "radial_title" in inputs.info()["controls"]
        assert fig.get_settings()==before_layout
        inputs.click_rect(inputs.info()["controls"]["radial_title"])
        inputs.key("ctrl+a")
        inputs.xdo("type", "--clearmodifiers", "Reviewed donut")
        inputs.pump()
        assert fig.get_settings()["radial"]["title"] == "Reviewed donut"
        inputs.click("radial_material")
        inputs.click("radial_material_Wood")
        assert fig.get_settings()["radial"]["style"]["material"] == "Wood"
        inputs.click("copy")
        # X11 clipboard ownership is asynchronous, especially when previous
        # windows in the same process have just closed. Wait for this copy.
        expected=fig.to_code();deadline=time.monotonic()+3
        while True:
            result=subprocess.run(["xclip","-selection","clipboard","-o","-t","UTF8_STRING"],capture_output=True,text=True,timeout=3)
            copied=result.stdout
            if result.returncode==0 and copied==expected:break
            assert time.monotonic()<deadline,(result.returncode,result.stderr,copied)
            inputs.pump()
        assert copied == expected and ".chart.set_material('wood')" in copied
        assert "configure_radial" not in copied
        assert "'value':" not in copied
        subprocess.run(["wmctrl", "-ir", inputs.wid, "-b", "add,maximized_vert,maximized_horz"], check=True)
        inputs.pump()
        assert inputs.info()["inspector_overlay"]
        assert inputs.info()["chart_panel"][2]/inputs.info()["chart_panel"][3] == pytest.approx(960/600, abs=.005)
        subprocess.run(["wmctrl", "-ir", inputs.wid, "-b", "remove,maximized_vert,maximized_horz"], check=True)
        inputs.pump()
        assert fig.info["column_uploads"] == fig.info["rgba_readbacks"] == fig.info["png_encodes"] == 0
        # Verify the public appearance recipe on the original plotting setup.
        # Transient hover/selection are view state, covered by exact checkpoints.
        with figgy.Figure(backend="native") as replay:
            replay.axes[0].pie([40, 30, 0, 30], labels=["A", "B", "Zero", "C"], material="ceramic")
            exec(copied, {"fig": replay})
            source=fig.get_settings()['radial'];restored=replay.get_settings()['radial']
            assert {k:v for k,v in restored.items() if k!='interaction'} == {k:v for k,v in source.items() if k!='interaction'}
            np.testing.assert_array_equal(replay.render_rgba(),fig.render_rgba())
            assert replay.info['column_uploads']==0
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
