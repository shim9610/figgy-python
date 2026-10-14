"""Actual X11 events, invalid SSOT edits, surface resize and window lifetimes."""

import json
import os
import shutil
import subprocess
import time

from check_randomized import mutate


def exercise(fig, rng, steps, counts, record, fail):
    from figgy.desktop import poll_events

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
        return xdo("search", "--pid", os.getpid(), "--name", "Figgy").splitlines()[-1]

    def click(rect):
        x, y = round(rect[0] + rect[2] / 2), round(rect[1] + rect[3] / 2)
        xdo("mousemove", "--window", wid, x, y)
        pump()
        xdo("mousedown", 1)
        pump()
        xdo("mouseup", 1)
        pump()

    def paste(value):
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
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
                if not info()["properties_open"]:
                    click(info()["controls"]["properties"])
                if "settings_json" not in info()["controls"]:
                    click(info()["controls"]["advanced"])
                before, revision = fig.get_settings(), fig.revision
                value, detail = mutate(before, rng)
                record({"stage": "ui_input", "index": i, "mutation": detail})
                click(info()["controls"]["settings_json"])
                paste(json.dumps(value))
                click(info()["controls"]["apply_settings"])
                if info()["error"]:
                    counts["ui_errors"] += 1
                    if fig.get_settings() != before or fig.revision != revision:
                        fail(
                            "ui_non_atomic_rejection",
                            {"index": i, "mutation": detail, "error": info()["error"]},
                        )
                else:
                    counts["ui_accepted_edits"] += 1
                    fig.apply_settings(before)
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
