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

## CI #52 annotation-input follow-up

The preceding local 640-case pass did not reproduce CI #52's browser input
failure. CI passed four layout probes and 51 priority cases, then stopped at
**250 passed and one failed** in 1472.42 seconds. The radial multiline-text
case sent its reopening double-click to **(1243, 873.94)** in a **980 x 820**
viewport. Its separately read protocol bounding box still described a
960 x 600 canvas, while the subsequent DOM record was 511 x 319.375. No text
hit was recorded; all three GPU submissions had completed and the host queue
was idle. This establishes an invalid test input, not a renderer/SSOT failure.
The evidence does not determine whether the earlier protocol box was stale
when returned or the DOM layout changed between the separate reads.

The shared annotation-input helper now prepares annotation geometry and reads
the live DOM rectangle and coordinate units in one browser operation. It rejects
points outside the visible canvas before sending real Playwright mouse input.
Both existing-text helpers use this path. No timing deadline or post-input
assertion changed. A controlled browser case reproduces the recorded resize:
the old point delivers no canvas double-click, while the current point delivers
a trusted mouse event. [The CI request, accepted SSOT and settled host state](measurements/ci52-annotation-input-20261022.json)
retain the measured failure.

All **five affected cases passed in 94.48 seconds**: the controlled input
regression, Cartesian/radial multiline editing, and scale 1/2 editing. Runtime
files and the release wheel are unchanged. The collection now contains **641
cases**; no complete local 641-case pass is claimed. Required CI validates the
complete updated collection.

## CI #53 resize-readiness correction

CI #53 failed the same radial multiline case after **251 passed and one failed**
in 1726.82 seconds. Unlike the preceding separate observations, its input helper
read annotation geometry and live DOM bounds together. The DOM itself was still
960 x 600 in the new 980 x 820 viewport; the requested point remained
(1243, 873.94). Thus the preceding coordinate-read correction did not fix the
underlying readiness error: matching CSS and backing dimensions can both be old.
[The measured input, host and GPU state](measurements/ci53-surface-readiness-20261022.json)
preserve this distinction. No renderer or SSOT failure is established here.

A controlled browser regression using the exact CI allocation **failed against
the old predicate** (one failed in 1.69 seconds). Readiness now also requires a
positive canvas allocation that fits the requested horizontal viewport, while
preserving CSS/backing/DPR agreement. The regression withholds the new allocation
for 200 ms and checks that readiness waits for its delivery. It does not wait for
the asserted text content, font or inline-editor bounds. This is an input
precondition, not a claim that all automatic layout or GPU work has completed;
notebook output may still scroll vertically.

All **six affected cases passed in 96.74 seconds** on the unchanged runtime
wheel: that readiness regression, the trusted annotation-input regression,
Cartesian/radial multiline editing in both hosts and queued resize/editing at
scales 1 and 2. CI orders the exact failed radial case and both controlled input
regressions first in the full suite. The collection now has **642 cases**. The
existing full suite, assertions and time limits remain in place; no complete
local 642-case pass is claimed. Local Chromium is 154; CI #53 used Chromium 156.

## Acceptance gaps observed before the oracle correction

Counts include packaging and release guards and do not measure feature or UX
coverage. Before the correction below, isolated assertion audits found two gaps:

- All nine native feature round-trip cases accept a substituted white RGBA
  image with one black pixel. Their model/replay assertions still execute, but
  nonblank output plus replay-image equality is not an independent visual oracle.
  A targeted data/colorbar pixel-change case rejects that same substituted image.
- All ten column-backed restoration family/backend cases accept arrays zeroed
  only during restoration, while preserving shape and dtype. Settings equality
  and a valid PNG signature do not verify every restored data value. A separate
  input-snapshot test checks one stored float32 payload, not every restore handoff.

These were demonstrated test gaps, not observed production data corruption.
The independent scene and restored-array assertions below address these cases.
Finite acceptance scenes still do not establish every feature combination or
general usability.

## Execute the complete collection once

The historical 640-case local JUnit record contains 2443.445 seconds of case
time. Running the priority groups separately repeats 55 of those cases, adding
246.020 seconds: **2689.465 seconds (44m 49s)** before collection, job setup and
shutdown. That leaves no useful margin within the unchanged 45-minute job
budget. These are measured local costs, not a prediction of the CI runner's
exact runtime. [The per-case costs and collection comparison](measurements/ci-test-order-20261022.json)
retain the calculation.

`scripts/run_ci_tests.py` now runs one complete pytest collection and orders the
past failures first. A comparison against ordinary pytest collection found
**642 original IDs, 642 ordered IDs and 642 unique IDs**, with identical
multisets: zero omissions or additions. The runner records both lists in the
CI artifact `test-plan.json`. It rejects duplicated node IDs and missing required
priority cases with exit code 4; both rejection paths were exercised locally.
The workflow retains every test, its assertions, fail-fast behavior and the
45-minute job budget. Only duplicate execution is removed.

The first **57 cases passed together in 254.33 seconds** in the recorded order,
including the exact failed radial editor case, two resize/input regressions,
both scale cases, inactive-overlay editing, packaged assets, slow native clicks,
radial detail selection and radial annotation drawing in both hosts. Preflight
passed **117 cases in 2.03 seconds**. The runtime wheel is unchanged.

The integration job also used `if: always()`. GitHub's [cancellation reference](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-cancellation)
explicitly states that a running job with this condition continues on
cancellation. The job now uses `if: ${{ !cancelled() }}`: an upstream failed or
skipped build still runs the existing result guard and fails the required check,
while a superseded workflow can stop. Preflight passed **117 cases in 2.10
seconds** after this workflow-only change. An already-running job retains the
workflow definition with which it started; this change does not alter that job
retroactively.

## Independent feature and recovery oracles

The original API/combination replay fixtures remain intact. Each of the nine
native feature replay cases now also renders an independently authored reference
scene. Its expected probes come from declared input geometry and colors, never
from another rendered image or renderer-reported bounds. The document is
960 x 600 with a fixed 400 x 400 plot at (100,100), hidden Cartesian decoration
and fixed [0,4] ranges. The assertions check:

- Mapped points: gray values, positions, different marker areas and empty space.
- Point/grid vectors: mapped colors, shafts, directional heads and empty tails.
- Steps: required horizontal/vertical segments and absence of linear diagonals.
- Baseline/series fills: filled interiors and empty regions below/above the
  declared boundaries.
- Polar coordinates: asymmetric radii, radians, clockwise direction and chords.
- Radar: two differently colored polygons, declared range and empty interiors.
- Annotations: reference-line color/position, span opacity and text in its
  authored region.

The identical oracle checks nine actual displayed Jupyter WebGPU canvases. A
fractional Jupyter output origin otherwise creates a 601-row enclosing capture
for a 600px canvas. The fixture translates the entire widget onto the device
pixel grid, retaining exactly 960 x 600 CSS/backing dimensions at DPR 1. No rows
are cropped, pixels resampled or dimension assertions relaxed.

Recovery tests retain independent copies of the original renderer inputs in
test code only, before the cache writer or renderer can mutate them. They compare every baseline/approved NPY payload and every
restored upload by column identity, dtype, shape, all values and payload bits.
The NPY oracle reads files directly rather than reusing the restore reader.
Bounded numeric checkpoints are also compared with literal expectations for
pie/bar/box/radar inputs, including box statistics and sample-count dtype.
Coverage includes mapped values/sizes, matrices and edge coordinates, point/grid
vector components and mapped grids, shared-X fill pairs and panel/overlay data.

Native inspection reads every restored column through the production GPU
selection-readback path using temporary test-only probe series referencing the
existing buffers; sample-upload counters must remain unchanged. These probes
run after complete approved-SSOT assertions and are discarded with the test
Figure. Browser inspection compares actual transfer snapshot bytes. Additional
float32/float64 cases include signed zero, nontrivial finite precision, a custom
NaN payload and both infinities. Cache/upload/transfer bits are exact; native
finite GPU values use the packed pair-of-f32 representation's 2e-14 relative
bound, with zero absolute tolerance. Native selection JSON represents nonfinite
values as null, so exact nonfinite bit preservation is asserted at the lossless
boundaries rather than claimed for that JSON observation.

Negative controls are part of ordinary CI: **45 wrong image cases**, **nine
single-pixel substitutions through the actual replay test**, **42 wrong restore
payloads** (zero/reversed/wrong dtype), and **14 wrong device/transfer contents**
must all be rejected. Two additional controls require rejection when the cache
writer mutates its original input in place. Recording the expectation after the
writer incorrectly accepted both faults; pre-write snapshots now reject them.
In the resident-data cases, settings, cache and observed upload
arguments remain correct: only the final native upload or browser transfer bytes
are zeroed. Re-running the original baseline test accepted all ten original
family/backend resident-data faults; the strengthened checks reject them.

Local validation passed **209 focused cases in 11.14 seconds**, **nine headful
browser cases in 127.57 seconds**, and **131 preflight cases in 2.90 seconds**.
The unchanged runtime wheel is the previously verified
`88e7f7cc4bfa8edf93ae9240f289144b530fc493dbe1f73a66355fb7b1537c2b` artifact.
Ordinary and priority collection both contain **785 unique cases**: all previous
642 IDs remain, with 143 additions and zero duplicates. Each runner collects the complete plan, orders the priority cases first and
executes one disjoint quarter. No full local 785-case pass is claimed; required
CI must validate the final commit.
[The before/after contract and measurements](measurements/acceptance-oracles-20261022.json)
distinguish these results. These finite scenes do not claim every feature
combination, exact font rasterization or general usability.


### Complete execution is a required assertion

[CI #58](https://github.com/shim9610/figgy-python/actions/runs/39734785159)
passed 470 of 771 cases before its configured 45-minute job limit cancelled the
run. It reported no assertion failure; it did not establish a full-suite pass.
The nine added browser oracles occupied approximately 125 seconds of the logged
test interval. Existing radial GPU work was substantially slower: the same
radial-detail WebGPU test's first submission increased from 11.622 seconds in
CI #56 to 42.342 seconds, while pipeline preparation increased from 0.501 to
0.660 seconds. This observation locates the larger stall in GPU completion,
without attributing it to a particular runner CPU or renderer change.
[The measurements](measurements/ci58-execution-deadline-20261022.json) preserve
that distinction.

The suite now runs on four independent software-GPU runners. Each collects the
identical full ordered plan, then selects `ordered[index::4]`. Individual test
deadlines, correctness assertions and the 45-minute per-job limit are retained.
No test is intentionally run twice. The existing required check name,
`PR / Linux integration`, now verifies that every shard succeeded and audits
all four JUnit reports against their complete plans. Missing artifacts, changed
plans, wrong partitions, missing/duplicate execution IDs, failures, errors and
skips fail this check. Exact pytest node IDs are written into JUnit properties;
Python class names are not used to guess them.

Fourteen local execution-contract tests passed, including a real two-shard
pytest/JUnit run and twelve deliberately invalid reports. Collection proves
that the four selected lists contain all 785 current IDs exactly once, including
all original 642 cases. This audit is also part of CI preflight.


The first sharded run (CI #59) exposed a nested-test isolation error: its sample
pytest subprocess inherited the parent project's collection root when CI's
`--basetemp` lived inside the repository. The same repository-local layout
reproduced the failure locally. The sample subprocess now explicitly fixes its
root to its own temporary directory; the full audit remains strict. All 14
execution-contract cases pass in that repository-local layout (0.64 seconds),
and preflight passes all 131 cases (2.90 seconds).
