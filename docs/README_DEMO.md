# README edit → copy → reuse demo

The checked-in recording and validation results document the 0.2 development
checkpoint on 2026-10-14, not a new 0.3 capture or performance measurement.
The commands below describe the runnable example and recorder; see
[desktop editing](DESKTOP_EDITOR.md) for the current native/Jupyter controls.

The README animation records actual Figgy and VS Code windows. It starts with
Figgy's automatic upper-right legend (zero position offsets) covering a late
synthetic response peak. Real Ctrl/Shift-wheel input adjusts the axes; Layout
mode increases the left margin, the Y-axis title is positioned, and the legend
is dragged into the empty upper-left corner.

After **Copy Python**, the recording opens an empty `chart_style.py` in the
installed **Visual Studio Code**, pastes with **Ctrl+V**, saves, and runs
`python apply_to_runs.py` in its integrated terminal. Three actual PNG files are
then opened in VS Code image-editor columns. There is no custom code editor or
simulated Run button. Captions and a pointer highlight are added for readability;
playback is shortened for a brisk walkthrough. This is not an FPS benchmark.

The VS Code instance uses a separate temporary profile and an empty user
extensions directory. The regular Figgy desktop editor still has no Qt/PySide6
dependency.
Its isolated Bash profile displays `figgy-demo $`, and the VS Code title shows
only the active filename. The regular user's shell/profile settings are untouched.

## Run the example

```bash
python examples/edit_and_reuse.py --output output/edit-and-reuse
```

Each chart has three series of 100,000 float32 samples, with stable IDs:
`measured`, `model`, and `baseline`. After editing, close the first window to
write `chart_style.py` and `run-01.png` through `run-03.png`. The resulting figures
open in separate windows. The first window’s closure retains its Figure settings.

The complete clipboard export shown in the recording is checked in as
[chart_style.py](examples/chart_style.py). It is intended for figures made by this
example (same series IDs/kinds, 960×600 canvas, 120 DPI). `export_batch()` restores
a distinct title after applying the shared settings. It keeps each dataset’s
arrays and verifies that styling causes no additional column uploads.

## Re-record on Linux / X11

The recorder requires an installed local package, NumPy, Pillow, the VS Code
`code` CLI, `xdotool`, `xclip`, `xwininfo`, `xsetroot` and a window manager. Use an
isolated X11 display with a 1440×900 or larger screen so it does not operate on
your working desktop. Install Pillow with `python -m pip install pillow`.
For example, after starting Xvfb and Openbox on `:93`:

```bash
DISPLAY=:93 Xvfb :93 -screen 0 1440x900x24 -ac -nolisten tcp
# In a second terminal:
DISPLAY=:93 openbox --sm-disable
# In a third terminal:
env -u WAYLAND_DISPLAY DISPLAY=:93 WGPU_BACKEND=vulkan \
  python scripts/record_readme_demo.py
```

A headless Xvfb server may require a software Vulkan adapter. The checked-in
[recording metadata](images/edit-and-reuse.json) names the adapter used; the
interaction and export code are the same native host APIs as hardware rendering.
This does not establish a hardware performance result.

The script writes:

- `docs/images/edit-and-reuse.gif`: real input sequence with captions and pointer halo
- `docs/images/edit-and-reuse.png`: still frame after moving the legend
- `docs/examples/chart_style.py`: the exact clipboard text
- `docs/images/edit-and-reuse.json`: capture dimensions, input provenance, code hash and verification
- `/tmp/figgy-readme-demo/`: exported code, the actual pasted text, three PNGs,
  VS Code batch verification, temporary editor profile and the batch preview

It asserts axis isolation during Ctrl-wheel, a changed legend position, clipboard
identity with `Figure.to_code()`, byte-for-byte Ctrl+V paste identity,
VS Code terminal execution, identical replayed axes/legend/styles, unchanged
upload counts during styling, and three distinct rendered image hashes. The GIF
uses one shared palette to avoid color flicker. Font paths in the recorder use
Liberation Sans/Mono as installed on the recording host; adjust them if needed.

## Validation of the runnable example

The CLI command was also exercised end to end on an isolated X11 display: one
editable window, closing it to trigger code export, three distinct PNGs and three
independent result windows, followed by a clean exit. The recorded clipboard
code was additionally replayed for all three datasets on Radeon 8060S Vulkan,
with six initial column uploads per Figure and no additional uploads for styling.
