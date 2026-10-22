# Review mode validation

This records local validation of the unreleased #18 implementation. Required
GitHub checks still run on the draft PR's exact commit.

## Initial review implementation wheel

- CPython 3.12.14, NumPy 2.5.4, Linux, Mesa software Vulkan, Chromium 154.
- Wheel SHA-256: `93e14460b0430002f65d284b11dd99532864c52bc2ec6006f8fd215ff16103b2`.
- Every packaged Python, JavaScript, CSS, schema and skill file matches source.
- **46 review tests passed** in 134.33 seconds: 37 core cases and nine real native
  or Jupyter input cases. UI tests ran with Xvfb/Openbox at 1600 x 1000 and the
  required interaction/timing diagnostics enabled.
- **Four existing editor/layout probes passed** in 72.51 seconds, including
  resize at two scales, multiline text formatting and inactive overlay editing.
- **117 CI preflight tests passed**. Cargo format/check, JavaScript syntax,
  installed-package checks and editor-control inventory passed.

Run the review cases with the installed wheel and the normal CI UI environment:

```sh
python -m pytest -vv tests/test_review.py tests/test_interaction_parity.py -k review
```

The review cases compare the actual accepted baseline and approved settings,
then restore from the manifest and binary files. They cover all chart families
on both backends, unchanged binary reuse, corruption, stale revisions/instances,
writer leases, disconnect, duplicate delivery, concurrent comments, failed and
timed-out source/render workers, explicit edit supersession and completed-round
cleanup. Native and browser UI cases submit through real controls, retain pending
annotations and comments on storage failure, retry approval, and display every
Figure in the validated next round.

Additional regressions first failed against the preceding wheel, then passed:

- UI comments no longer erase separately targeted API comments.
- A close observer may read session state after a post-rename durability retry;
  approval does not close views while holding the manifest file lock.
- Cache creation cannot claim a nonempty foreign directory, and opening a missing
  cache creates no files.
- Native review buttons remain inside the surface with long comments. The final
  input check pastes 40 actual lines and verifies the complete stored text.
- Duplicate notebook views cannot approve while another view has pending input;
  duplicate native windows and reopening approved native Figures are rejected.

## Earlier full-suite run

Before those final review-specific fixes and six added regressions, one complete
UI-enabled invocation passed **633 tests in 2460.86 seconds**. The then-current wheel was
then rebuilt and the 46 review cases, four existing layout probes and preflight
checks above were rerun. Those results belong to the initial implementation;
the follow-up artifact and complete run are recorded separately below.

No thresholds, gesture assertions, pixel tolerances or CI time limits were relaxed.
The notebook harness now accepts an explicit expected initial view count and
requires every such view to reach Ready within the existing startup budget.

## Native input and popup follow-up

The same draft PR also fixes a short-click failure exposed while diagnosing
CI #51. Its workflow/assets check and wheel build passed, but integration stopped
near the existing 45-minute budget after recording a native radial-detail failure.
The job log did not reach the final failure traceback before cancellation.

A local reproduction of that scenario measured the old input driver's button
hold at 0.8216 seconds on failure and 0.7937 seconds on success. Egui 0.36.2's
default click limit is 0.8 seconds. The driver now sends a complete X11 click
before waiting for rendering; intentional drag input remains separate. A shared
helper covers the native test drivers. An injected 0.9-second frame delay fails
the preceding driver and passes the corrected driver. [The recorded input and
timing evidence](measurements/ci51-native-click-duration-20261022.json) separates
the local cause from what the cancelled CI log establishes.

The first full run with the corrected click driver stopped with **219 passed
and one failed** in 772.35 seconds, exposing a separate application issue. The Cartesian
inspector shared the Foreground order used by popup menus and could intercept a
reopened menu's item click. The inspector now uses Middle, keeping menus above
it. Review controls reserve their space before inspector sizing. [The actual
menu hit layers, before/after settings and review bounds](measurements/native-inspector-popup-layer-20261022.json)
record both fixes. Raw screenshots of the synthetic fixture show the [occluded menu before](measurements/native-inspector-menu-before-20261022.png) and the [visible menu after](measurements/native-inspector-menu-after-20261022.png). Five focused cases passed in 124.92 seconds, including native
and browser opposite-axis editing, properties with long review comments, and
the slow-frame click regression.

A subsequent full run stopped with **243 passed and one failed** in 1201.72
seconds. A native boxplot text-placement click exposed another input assumption:
egui clears `press_origin` after processing a release, even when both press and
release are buffered in one frame. Bounded drawing now recovers that frame's
actual primary-button press coordinate from the ordered raw events. Existing
image hit tests, drag previews and release commits remain intact. [The failed
placement, successful placement and paired raw events](measurements/native-buffered-click-20261022.json)
show `clicked=true`, a cleared snapshot origin and the recovered coordinate.
Opening the text draft leaves the complete chart SSOT identical to its armed
state. All **eight chart-family cases passed in 352.12 seconds**, each exercising
native and browser creation, text editing, cancellation, drawing and export.

Native diagnostics retain the last submitted pointer event and bounded input
records. Browser diagnostics separate server/browser startup, view readiness,
the test body, collection and shutdown in `harness-timing.json`. CI stops at the
first failure to print its traceback immediately, and runs the two click/detail
regressions in the priority group. The full collection, existing 45-minute budget,
pixel assertions and gesture deadlines remain unchanged. The opposite-axis SSOT
assertions that detected the application failure are unchanged.

The final follow-up wheel's SHA-256 is
`88e7f7cc4bfa8edf93ae9240f289144b530fc493dbe1f73a66355fb7b1537c2b`.
The complete UI-enabled suite passed **640 tests in 2444.04 seconds (40m 44s)**
on that wheel, with **zero failures, errors or skips**. This includes the full
review workflow and the existing native/Jupyter interaction, layout, pixel and
SSOT assertions, with all CI interaction/timing flags enabled. Current preflight
passed all **117 cases in 3.02 seconds**; Cargo format/check passed. All 33 installed runtime
files match the wheel byte for byte, including the native extension; its 32
non-native runtime files also match their packaged source files. Installed-wheel
smoke and editor-control inventory checks passed.
