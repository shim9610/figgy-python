"""Record real native input and clipboard replay for the README GIF.

Requires an isolated X11 display at 1440x900 or larger, xdotool, xclip, Pillow and VS Code.
See docs/README_DEMO.md. Captions, pointer highlights and the clipboard/results
chapters use real screen captures, including the installed VS Code editor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from edit_and_reuse import make_figure
from figgy.desktop import poll_events

SIZE = (1440, 900)
BG = "#edf1f6"
INK = "#172b43"
BLUE = "#2467ad"


def font(size, mono=False, bold=False):
    family = "LiberationMono" if mono else "LiberationSans"
    weight = "Bold" if bold else "Regular"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/liberation/{family}-{weight}.ttf", size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/images/edit-and-reuse.gif")
    parser.add_argument("--workdir", type=Path, default=Path("/tmp/figgy-readme-demo"))
    args = parser.parse_args()
    for command in ("xdotool", "xclip", "xwininfo", "code"):
        if not shutil.which(command):
            parser.error(f"{command} must be on PATH")
    if not os.environ.get("DISPLAY"):
        parser.error("DISPLAY must point to an isolated X11 screen")
    args.workdir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames, durations = [], []
    pointer = None
    caption = "The legend covers the peak. Fix the view without rewriting the plot."
    chapter = "01 / EDIT THE PLOT"
    shortcut = ""
    editor_process = None
    editor_pid = None
    editor_log = None
    edited = make_figure()
    window = edited.show(block=False)

    def pump(count=8):
        for _ in range(count):
            poll_events()
            time.sleep(.006)

    def xdo(*parts):
        return subprocess.check_output(["xdotool", *map(str, parts)], text=True).strip()

    def info(): return json.loads(window.info_json())

    def add(image, duration=70):
        frames.append(image.convert("RGB")); durations.append(((duration+5)//10)*10)

    def chrome(image):
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, SIZE[0], 60), fill="white")
        draw.text((36, 17), "figgy-python", font=font(27, bold=True), fill=BLUE)
        draw.text((SIZE[0]-440, 23), chapter, font=font(17, bold=True), fill=INK)
        draw.rectangle((0, 850, SIZE[0], 900), fill="white")
        draw.text((36, 864), caption, font=font(20), fill=INK)
        if shortcut:
            box = (1055, 780, 1390, 832)
            draw.rounded_rectangle(box, radius=10, fill=INK)
            draw.text((1074, 794), shortcut, font=font(20, bold=True), fill="white")
        return image

    def capture(duration=70, highlight=False):
        image = ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((0, 0, *SIZE)).convert("RGB")
        if pointer:
            overlay = Image.new("RGBA", SIZE)
            draw = ImageDraw.Draw(overlay)
            x, y = pointer
            draw.ellipse((x-14, y-14, x+14, y+14), fill=(244, 164, 56, 65), outline=(230, 139, 22, 255), width=2)
            if highlight:
                draw.ellipse((x-22, y-22, x+22, y+22), outline=(230, 139, 22, 210), width=3)
            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        add(chrome(image), duration)

    def move(x, y, count=8):
        nonlocal pointer
        if pointer is None: pointer = (x, y)
        start = pointer
        for step in range(1, count+1):
            pointer = (round(start[0]+(x-start[0])*step/count), round(start[1]+(y-start[1])*step/count))
            xdo("mousemove", *pointer); pump(3); capture()

    def geometry():
        # xwininfo reports the client origin accurately after WM reparent/resize.
        output = subprocess.check_output(["xwininfo", "-id", wid], text=True)
        return {axis: int(re.search(rf"Absolute upper-left {axis}:\s+(-?\d+)", output).group(1)) for axis in ("X", "Y")}

    def screen_point(rect):
        g = geometry()
        return int(g["X"])+round(rect[0]+rect[2]/2), int(g["Y"])+round(rect[1]+rect[3]/2)

    def click_control(name):
        move(*screen_point(info()["controls"][name]), count=6)
        xdo("mousedown", 1); pump(6); capture(highlight=True)
        xdo("mouseup", 1); pump(12); capture(250)

    try:
        pump(30)
        wid = xdo("search", "--pid", os.getpid(), "--name", "^Figgy$").splitlines()[-1]
        subprocess.run(["xsetroot", "-solid", BG], check=True)
        xdo("windowmove", wid, 54, 78); xdo("windowfocus", wid); pump(20)
        initial = edited.get_settings()
        initial_uploads = edited.info["column_uploads"]
        assert initial["config"]["legend"]["corner"] == "TopRight"
        assert initial["config"]["legend"]["offset_x"] == initial["config"]["legend"]["offset_y"] == 0
        assert initial["config"]["left_y"]["out_margin"] == 110
        capture(850)
        # Native Ctrl/Shift wheel events, anchored just below the response peak.
        data = info()["decorations"]["data_area"]
        g = geometry()
        px = int(g["X"])+data[0]+data[2]*.9
        py = int(g["Y"])+data[1]+data[3]*.6
        caption = "Zoom the time window around the pointer."
        shortcut = "Ctrl + wheel  /  Zoom X"
        move(px, py)
        xdo("keydown", "ctrl"); pump()
        for _ in range(2):
            xdo("click", 4); pump(15); capture(170, highlight=True)
        xdo("keyup", "ctrl"); pump(); capture(250)
        assert edited.get_settings()["config"]["left_y"] == initial["config"]["left_y"]
        caption = "Adjust the amplitude scale independently."
        shortcut = "Shift + wheel  /  Zoom Y"
        xdo("keydown", "shift"); pump()
        for _ in range(1):
            xdo("click", 4); pump(15); capture(170, highlight=True)
        xdo("keyup", "shift"); pump(); capture(300)
        caption = "Make more room for the Y-axis labels."
        shortcut = "Layout  /  Adjust margin"
        click_control("layout_mode")
        data = info()["decorations"]["data_area"]
        move(*screen_point([data[0]+80, data[1]+100, 0, 0]), count=4)
        xdo("click", 1); pump(18)
        assert info()["selected"] == "data_area"
        data = info()["decorations"]["data_area"]
        move(*screen_point([data[0], data[1]+data[3]/2, 0, 0]), count=4)
        xdo("mousedown", 1); pump(); capture(100, highlight=True)
        move(pointer[0]+35, pointer[1], count=7)
        xdo("mouseup", 1); pump(15); capture(250)
        assert edited.get_settings()["config"]["left_y"]["out_margin"] >= 140
        click_control("select_mode")
        caption = "Position the Y-axis title in the wider margin."
        shortcut = "Drag  /  Move axis title"
        title = info()["decorations"]["axis_title_left"]
        move(*screen_point(title), count=4)
        xdo("mousedown", 1); pump(); capture(100, highlight=True)
        move(pointer[0]-8, pointer[1], count=5)
        xdo("mouseup", 1); pump(15); capture(250)
        assert info()["selected"] == "axis_title_left"
        assert edited.get_settings()["config"]["left_y"]["title_option"] != initial["config"]["left_y"]["title_option"]
        caption = "Drag the legend away from the data."
        shortcut = "Drag  /  Move legend"
        legend = info()["decorations"]["legend"]
        data = info()["decorations"]["data_area"]
        move(*screen_point(legend))
        xdo("mousedown", 1); pump(); capture(120, highlight=True)
        target = [data[0]+16, data[1]+16, legend[2], legend[3]]
        move(*screen_point(target), count=14)
        xdo("mouseup", 1); pump(24); capture(500)
        assert info()["selected"] == "legend"
        assert edited.get_settings()["config"]["legend"]["offset_x"] != initial["config"]["legend"]["offset_x"]
        chrome(ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((0,0,*SIZE)).convert("RGB")).save(args.output.with_suffix(".png"))
        chapter = "02 / COPY PYTHON"
        caption = "Copy Python exports the edited ranges, legend position and styles."
        shortcut = "Copy Python"
        click_control("copy")
        code = subprocess.check_output(["xclip", "-selection", "clipboard", "-o", "-t", "UTF8_STRING"], text=True, timeout=5)
        assert code == edited.to_code() and "ax.set_xlim(" in code and "json.loads" not in code
        code_path = ROOT / "docs/examples/chart_style.py"
        code_path.write_text(code, encoding="utf-8")
        capture(300)
        chapter = "03 / PASTE INTO VS CODE"
        caption = "Paste the copied settings into VS Code and save chart_style.py."
        shortcut = "Ctrl + V  /  Paste Python"
        profile = args.workdir.with_name(args.workdir.name + "-profile")
        (profile / "User").mkdir(parents=True, exist_ok=True)
        (profile / "User/settings.json").write_text(json.dumps({
            "workbench.startupEditor": "none", "workbench.colorTheme": "Default Dark Modern",
            "workbench.editor.enablePreview": False, "editor.fontSize": 16, "editor.lineHeight": 23,
            "editor.minimap.enabled": False, "editor.wordWrap": "off", "editor.formatOnPaste": False,
            "editor.stickyScroll.enabled": False, "window.commandCenter": False,
            "security.workspace.trust.enabled": False, "telemetry.telemetryLevel": "off", "update.mode": "none",
            "terminal.integrated.fontSize": 15,
            "terminal.integrated.profiles.linux": {
                "Demo": {"path": "/bin/bash", "args": ["--noprofile", "--norc"],
                         "env": {"PS1": "figgy-demo $ ", "PROMPT_COMMAND": ""}}
            },
            "terminal.integrated.defaultProfile.linux": "Demo",
            "window.title": "${activeEditorShort}${separator}Visual Studio Code",
            "workbench.statusBar.visible": False, "breadcrumbs.enabled": False,
            "files.autoSave": "off", "window.restoreWindows": "none",
            "extensions.ignoreRecommendations": True, "chat.disableAIFeatures": True,
            "workbench.secondarySideBar.defaultVisibility": "hidden",
            "files.exclude": {"failure.*": True, "*.json": True, "*.log": True}
        }))
        pasted_path = args.workdir / "chart_style.py"
        pasted_path.write_text("")
        result_path = args.workdir / "vscode-results.json"
        result_path.unlink(missing_ok=True)
        runner = args.workdir / "apply_to_runs.py"
        runner.write_text("\n".join([
            "from pathlib import Path", "import hashlib, json, sys",
            f"sys.path.insert(0, {str(ROOT / 'examples')!r})",
            "from edit_and_reuse import export_batch", "",
            "output = Path(__file__).parent",
            "style_code = (output / 'chart_style.py').read_text()",
            "figures = export_batch(style_code, output)", "try:",
            "    report = {'result_settings': [f.get_settings() for f in figures],",
            "              'column_uploads': [f.info['column_uploads'] for f in figures],",
            "              'code_sha256': hashlib.sha256(style_code.encode()).hexdigest(),",
            "              'distinct_image_hashes': [hashlib.sha256(f.render_rgba().tobytes()).hexdigest() for f in figures]}",
            "    (output / 'vscode-results.json').write_text(json.dumps(report))",
            "    print('Applied pasted settings: run-01.png, run-02.png, run-03.png')",
            "finally:", "    for fig in figures: fig.close()", ""
        ]))
        editor_log = (args.workdir / "vscode.log").open("w+")
        editor_env = dict(os.environ, PATH=str(ROOT / ".venv/bin")+os.pathsep+os.environ["PATH"])
        editor_process = subprocess.Popen([
            "code", "--wait", "--new-window", "--user-data-dir", str(profile),
            "--extensions-dir", str(profile / "empty-extensions"),
            "--skip-welcome", "--skip-release-notes", "--disable-workspace-trust",
            "--no-sandbox", "--disable-gpu", "--ozone-platform=x11", "--locale=en-US",
            str(args.workdir), str(pasted_path)
        ], env=editor_env, stdout=editor_log, stderr=subprocess.STDOUT)

        def wait_for(predicate, timeout=30):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                value = predicate()
                if value: return value
                pump(4)
            editor_log.flush(); editor_log.seek(0)
            raise TimeoutError(editor_log.read()[-2000:])

        def code_window():
            result = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "chart_style.py.*Visual Studio Code"], capture_output=True, text=True)
            return result.stdout.splitlines()

        editor_wid = wait_for(code_window)[-1]
        editor_pid = int(xdo("getwindowpid", editor_wid))
        xdo("windowmove", editor_wid, 54, 78); xdo("windowsize", editor_wid, 1312, 744)
        xdo("windowactivate", "--sync", editor_wid); pump(400)
        # The file was opened by the CLI. Click its text surface after startup,
        # and prepare an actually empty saved buffer before recording Ctrl+V.
        xdo("key", "ctrl+b"); pump(20)
        pointer = (500, 220)
        xdo("mousemove", *pointer); xdo("click", 1); pump(15)
        xdo("key", "ctrl+a", "BackSpace", "ctrl+s"); pump(20)
        wait_for(lambda: pasted_path.read_text() == "")
        capture(450)
        xdo("key", "ctrl+v"); pump(15)
        xdo("key", "ctrl+s"); pump(15)
        wait_for(lambda: pasted_path.read_text() == code)
        xdo("key", "ctrl+Home"); pump(10); capture(1000, highlight=True)
        pasted_hash = hashlib.sha256(pasted_path.read_bytes()).hexdigest()
        assert pasted_hash == hashlib.sha256(code.encode()).hexdigest()
        caption = "Run the pasted settings on three datasets in the VS Code terminal."
        shortcut = "python apply_to_runs.py"
        xdo("key", "ctrl+grave"); pump(35)
        xdo("type", "--clearmodifiers", "python apply_to_runs.py"); capture(400)
        xdo("key", "Return"); pump(10); capture(200)
        wait_for(result_path.exists)
        completed = json.loads(result_path.read_text())
        assert completed["code_sha256"] == pasted_hash
        assert edited.info["column_uploads"] == initial_uploads
        for settings in completed["result_settings"]:
            a, b = edited.get_settings()["config"], settings["config"]
            assert a["bottom_x"] == b["bottom_x"] and a["left_y"] == b["left_y"] and a["legend"] == b["legend"]
            assert edited.get_settings()["series"] == settings["series"]
        digests = completed["distinct_image_hashes"]
        assert len(set(digests)) == 3 and completed["column_uploads"] == [6, 6, 6]
        capture(500)
        frames[-1].save(args.workdir / "terminal-preview.png")
        chapter = "04 / REUSE ACROSS DATASETS"
        caption = "One pasted script. Three datasets. Matching margins, titles and legend placement."
        shortcut = ""
        # Show the actual output files in three VS Code image editor groups.
        xdo("key", "ctrl+grave"); pump(15)
        xdo("key", "ctrl+shift+p"); pump(10)
        xdo("type", "--clearmodifiers", "View: Three Columns Editor Layout"); pump(80)
        xdo("key", "Return"); pump(80)
        for run in range(3):
            pointer = (312+run*420, 210)
            xdo("mousemove", *pointer); xdo("click", 1); pump(35)
            xdo("key", "ctrl+p"); pump(50)
            name = f"run-{run+1:02d}.png"
            xdo("type", "--clearmodifiers", str(args.workdir / name)); pump(130)
            xdo("key", "Return"); pump(115)
            wait_for(lambda: name in xdo("getwindowname", editor_wid))
        capture(2400)
        chrome(ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((0,0,*SIZE)).convert("RGB")).save(args.workdir / "batch-preview.png")
        # A shared palette avoids flicker; dither is disabled for crisp UI text.
        palette_source = Image.new("RGB", (360*len(frames[::8]), 225))
        for i, frame in enumerate(frames[::8]):
            palette_source.paste(frame.resize((360,225)), (i*360,0))
        palette = palette_source.quantize(colors=240, method=Image.Quantize.MEDIANCUT)
        reserved = ["#2467ad", "#e5893d", "#4a8f76", INK, BLUE, BG, "#ffffff", "#000000"]
        from PIL import ImageColor
        colors = palette.getpalette()[:720]
        colors += [channel for color in reserved*2 for channel in ImageColor.getrgb(color)]
        palette.putpalette(colors)
        quantized = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        quantized[0].save(args.output, save_all=True, append_images=quantized[1:], duration=durations, loop=0, optimize=True, disposal=1)
        with Image.open(args.output) as encoded:
            encoded_duration = 0
            for index in range(encoded.n_frames):
                encoded.seek(index)
                encoded_duration += encoded.info["duration"]
            encoded_frames = encoded.n_frames
        metadata = {"frames": encoded_frames, "captured_frames": len(frames), "duration_ms": encoded_duration, "size": SIZE,
                    "data": "synthetic; 100,000 samples per series, 3 series per chart", "adapter": edited.info["adapter"]["name"],
                    "input": "actual X11 axis zoom, plot-area resize, Y-title drag, default-legend drag, Copy Python, VS Code Ctrl+V/save and Python terminal execution",
                    "initial_legend": {key: initial["config"]["legend"][key] for key in ("corner", "offset_x", "offset_y")},
                    "initial_margins": {"left": initial["config"]["left_y"]["out_margin"], "bottom": initial["config"]["bottom_x"]["out_margin"]},
                    "editor": "Visual Studio Code",
                    "paste_verified": pasted_hash == hashlib.sha256(code.encode()).hexdigest(),
                    "compositing": "instruction captions and pointer halo around actual Figgy and VS Code windows",
                    "replay": "three independent datasets; matching axes/legend/series styles; no style re-upload", "distinct_image_hashes": digests,
                    "code_sha256": hashlib.sha256(code.encode()).hexdigest()}
        args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2)+"\n")
        print(json.dumps({"gif": str(args.output), "bytes": args.output.stat().st_size, "frames":encoded_frames, "duration_ms":encoded_duration}))
    except BaseException:
        (args.workdir / "failure.json").write_text(json.dumps({"info": info(), "settings": edited.get_settings()}, indent=2))
        ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).save(args.workdir / "failure.png")
        raise
    finally:
        window.close(); pump()
        edited.close()
        if editor_process is not None:
            if editor_pid is not None:
                try: os.kill(editor_pid, signal.SIGTERM)
                except ProcessLookupError: pass
            if editor_process.poll() is None:
                editor_process.terminate()
                editor_process.wait(timeout=10)
            editor_log.close()


if __name__ == "__main__": main()
