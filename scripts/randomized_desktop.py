"""Actual X11 events, invalid SSOT edits, surface resize and window lifetimes."""

import json
import os
import shutil
import subprocess
import time

from check_randomized import mutate


def exercise(fig, rng, steps, counts, record, fail):
    from figgyplot.desktop import poll_events

    if (
        not os.environ.get("DISPLAY")
        or not shutil.which("xdotool")
        or not shutil.which("xclip")
    ):
        raise RuntimeError("desktop fuzzing requires DISPLAY, xdotool and xclip")
    handle = fig.show(block=False)
    cumulative_frames = 0

    def pump():
        for _ in range(8):
            poll_events()
            time.sleep(0.001)

    def info():
        return json.loads(handle.info_json())

    def xdo(*args):
        return subprocess.check_output(["xdotool", *map(str, args)], text=True).strip()

    def window():
        return xdo("search", "--onlyvisible", "--pid", os.getpid(), "--name", "^Figgy$").splitlines()[-1]

    def click(rect, target=None):
        x, y = round(rect[0] + rect[2] / 2), round(rect[1] + rect[3] / 2)
        # Force a motion event after returning from another native window.
        xdo("mousemove", "--window", target or wid, x + 2, y + 2)
        pump()
        xdo("mousemove", "--window", target or wid, x, y)
        pump()
        xdo("mousedown", 1)
        pump()
        xdo("mouseup", 1)
        pump()

    def paste(value):
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "UTF8_STRING"],
            input=value,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=3,
        )
        xdo("key", "ctrl+a")
        xdo("key", "ctrl+v")
        pump()

    try:
        pump()
        wid = window()
        xdo("windowfocus", wid)
        pump()
        uploads = info()["column_uploads"]
        for i in range(steps):
            mode = rng.choice(
                ["ssot", "ssot", "pointer", "drag", "resize", "close", "control"]
            )
            record({"stage": "ui_call", "index": i, "operation": mode})
            if mode == "ssot":
                # Window-manager focus/geometry events may outlive a short pump.
                for _ in range(16):
                    pump()
                if not info()["properties_open"]:
                    click(info()["controls"]["properties"])
                if not info().get("settings_window"):
                    click(info()["controls"]["advanced"])
                deadline = time.monotonic() + 3
                retry = time.monotonic() + .5
                while not info().get("settings_window"):
                    pump()
                    if time.monotonic() > deadline:
                        raise RuntimeError("advanced settings window did not open")
                    if time.monotonic() > retry:
                        xdo("windowfocus", wid)
                        click(info()["controls"]["advanced"])
                        retry = time.monotonic() + .5
                settings_id = xdo("search", "--onlyvisible", "--pid", os.getpid(), "--name", "Advanced chart settings").splitlines()[-1]
                xdo("windowfocus", settings_id)
                pump()
                before, revision = fig.get_settings(), fig.revision
                value, detail = mutate(before, rng)
                record({"stage": "ui_input", "index": i, "mutation": detail})
                click(info()["settings_window"]["controls"]["settings_json"], settings_id)
                paste(json.dumps(value))
                click(info()["settings_window"]["controls"]["apply_settings"], settings_id)
                if info()["settings_window"]["error"]:
                    counts["ui_errors"] += 1
                    if fig.get_settings() != before or fig.revision != revision:
                        fail(
                            "ui_non_atomic_rejection",
                            {"index": i, "mutation": detail, "error": info()["settings_window"]["error"]},
                        )
                else:
                    counts["ui_accepted_edits"] += 1
                    fig.apply_settings(before)
                    pump()
                xdo("key", "alt+F4")
                pump()
                xdo("windowfocus", wid)
                pump()
            elif mode == "resize":
                xdo(
                    "windowsize", wid, rng.randrange(900, 1450), rng.randrange(520, 900)
                )
                pump()
                counts["ui_resizes"] += 1
            elif mode == "close":
                cumulative_frames += info()["surface_frames"]
                handle.close()
                pump()
                handle = fig.show(block=False)
                pump()
                wid = window()
                xdo("windowfocus", wid)
                pump()
                counts["ui_reopens"] += 1
            elif mode == "control":
                choices = [
                    k
                    for k in info()["controls"]
                    if k
                    in (
                        "fit",
                        "select_mode",
                        "layout_mode",
                        "properties",
                        "close_properties",
                        "object",
                    )
                ]
                click(info()["controls"][rng.choice(choices)])
                xdo("key", "Escape")
                pump()
                counts["ui_control_clicks"] += 1
            else:
                w, h = info()["surface_size"]
                x, y = rng.randrange(w), rng.randrange(h)
                xdo("mousemove", "--window", wid, x, y)
                pump()
                if mode == "drag":
                    xdo("mousedown", 1)
                    pump()
                    xdo(
                        "mousemove", "--window", wid, rng.randrange(w), rng.randrange(h)
                    )
                    pump()
                    xdo("mouseup", 1)
                    pump()
                else:
                    xdo("click", rng.choice([1, 3, 4, 5]))
                    pump()
                counts["ui_pointer_events"] += 1
            assert not handle.closed, "window closed after a recoverable interaction"
            assert info()["column_uploads"] == uploads
            assert info()["rgba_readbacks"] == info()["png_encodes"] == 0
            record({"stage": "ui_returned", "index": i})
        counts["surface_frames"] = cumulative_frames + info()["surface_frames"]
        assert counts["surface_frames"] > steps
    finally:
        handle.close()
        pump()
