# Local layout validity measurements

Measured on 2026-10-21 against observation-only commit
`a1e79a800c25df9aa10fc20cffd661347f260a77` and its installed release wheel.
Production code, CI configuration, existing assertions and time budgets were
unchanged during this investigation. This report measures where the current
baseline implementation satisfies its contracts; it does not redefine supported
sizes. The subsequent implementation and acceptance-test changes are described
at the end of this report; they do not change the archived baseline observations.

## Evidence and reproduction

- [Per-case bounds CSV](evidence/layout-validity-20261021/bounds.csv)
- [Summary, archive hashes and installed-wheel verification](evidence/layout-validity-20261021/summary.json)
- [Measurement runner](../scripts/measure_layout_validity.py)
- Raw frame histories and atomic DOM snapshots are retained as compressed JSONL
  under `docs/evidence/layout-validity-20261021/`. Each run has an environment
  manifest and a measurement-script hash; matching script sources are archived
  alongside the data. Native source-module bytes match the recorded wheel.
  Installed browser JavaScript and CSS match this commit's source bytes.

The runtime was Linux/X11, Xvfb/Openbox, Python 3.12.14 and headed Chromium
154.0.8037.57 with SwiftShader. Native scale factors 1 and 2 were observed in
window statistics. Browser device scale factors 1, 1.25 and 2 were emulated
through Chromium's device-metrics API. These are local observations; the earlier
CI uses Chromium 156 and is not validated by a local timing distribution.

Run against the installed instrumented wheel, with the X11 and notebook runtime
configured as for the interaction suite:

```sh
python scripts/measure_layout_validity.py --host native --output /tmp/layout-native-1
WINIT_X11_SCALE_FACTOR=2 python scripts/measure_layout_validity.py --host native --output /tmp/layout-native-2
python scripts/measure_layout_validity.py --host browser --output /tmp/layout-browser
python scripts/measure_layout_validity.py --host browser-focus --output /tmp/layout-browser-focus
```

Output directories must be new. For byte-identical reproduction, decompress the
script archive whose full hash matches the run's environment manifest into the
repository's `scripts/` directory and run it there. The focused run records its
actual model font; comparisons must use that value, rather than assuming a font
from a different run.

The runner is a data collector: exit status zero means collection completed,
including recorded invalid layouts. Its exit status must not replace an
acceptance-test verdict; inspect the explicit per-case validity outcomes.

## Contracts measured

For each rectangle, record signed margins to its effective containing rectangle:
left, top, right and bottom. A negative margin identifies both the direction and
amount of an escape. Record exact containment and the existing 1px tolerance
separately. Native coordinates are physical window pixels from one statistics
snapshot; browser rectangles are CSS pixels from one JavaScript evaluation.
Physical canvas backing dimensions are compared with CSS size multiplied by DPR.

Native initial visibility is distinct from accessibility after deliberate wheel
or scrollbar interaction. The effective viewport is the intersection of the
Properties viewport and window bounds. Each case starts with the form explicitly
scrolled to its top. A bounded wheel experiment reverses direction after an
overshoot. Selected cases additionally use a precise scrollbar operation, perform
a real title edit and restore the fixture document. Successful later editing
does not replace an initial-visibility failure.

Browser input, the complete bordered input box, and its hint are measured
separately. Resize sampling retains every observation and finishes after the
requested viewport, physical backing and stable geometry agree. Bounds are never
a waiting condition: invalid geometry is allowed to stabilize and is recorded as
invalid. A separate focused experiment observes persistence after GPU work ends,
then re-dispatches an input event without changing text to test stale layout.

## Native results

The matrix covers logical widths 900, 1312 and 1600 and logical heights 520, 590,
700, 744, 800, 840, 844, 845, 900, 1000 and 1200 at both observed scale factors.
There are 66 matrix cases and 25 additional boundary observations.

| Observed scale | Matrix cases | Text initially inside, exact | Inside with existing 1px tolerance | Reached with ordinary wheel input |
| --- | ---: | ---: | ---: | ---: |
| 1 | 33 | 12 | 15 | 30 |
| 2 | 33 | 9 | 12 | 30 |

For the selected overlay title, at logical width 1312:

| Scale | Physical window height | Text bottom margin | Exact containment |
| --- | ---: | ---: | --- |
| 1 | 744 | -100.25px | Fails |
| 1 | 844 | -0.25px | Fails; the existing 1px check passes |
| 1 | 845 | +0.75px | Passes |
| 2 | 1488 | -202.5px | Fails |
| 2 | 1690 | -0.5px | Fails; the existing 1px check passes |
| 2 | 1691 | +0.5px | Passes |

These adjacent physical heights establish the observed crossing for this form,
font metrics, fixture and platform. They are not new minimum supported heights.
The application advertises a 900×520 logical minimum, so that size remains part
of the investigation and subsequent regression coverage.

At minimum height 520 (1040 physical pixels at scale 2), ordinary wheel steps
overshoot the interval where the text field fits. The precise scrollbar
experiment at logical width 1312 reveals the field and permits a real title
edit. All 12 selected edit checks pass, and ordinary scrolling changes no model
revision. Thus the minimum-size failure is not proof of complete inability to
edit; it proves that initial visibility and ordinary-wheel access differ from
access after a more precise operation.

## Browser results

The matrix uses viewports 1500×1000, 1200×900, 980×820, 800×600 and 640×600;
center and lower-right anchors; one line, two lines, eight lines and wrapped
scientific text. Model font sizes are 10, 16, 32 and 72 at DPR 1, and 16 at DPR
1.25 and 2. Both shrink and grow transitions occur. Actual canvas geometry is
recorded rather than inferred from the browser width.

| Measurement | Exact containment | Existing 1px tolerance |
| --- | ---: | ---: |
| Input rectangle | 166 / 200 | Retained per case in CSV |
| Whole box including hint | 126 / 200 | 126 / 200 |

Forty cases contain the input rectangle while the complete box escapes. All 200
measured cases reach the independent geometry-settled condition, preserve the
draft's exact contents, and retain input focus. Therefore geometry readiness,
focus and data preservation do not establish correct box placement.

Two additional draft-opening attempts at DPR 1, font sizes 32 and 72, lower-right
anchor produce no annotation geometry from the host API. These attempts are
recorded as opening failures. Their remaining 40 planned bounds combinations
were not measurable and must not be counted as passes or silently omitted from
future acceptance coverage. This measurement does not establish their cause.

The post-command geometry sampling interval is 20ms and requires three equal
observations; the median observed settling duration is about 95ms, p95 about
180ms and maximum about 258ms. These include sampler overhead and are descriptive
local observations, not proposed CI deadlines. Existing budgets remain unchanged.

### Persistent layout errors, separate from the earlier sequential-read race

The matrix captures a document font of 16 at a 960px-wide canvas becoming
65.3617px in the inline editor after growth from a 235px canvas. The value equals
`16 × 960 / 235`: the scale calculation uses the previous canvas backing width.
The final backing size has already caught up when this wrong font is observed.

The focused experiment compares the same final viewport, document and text before
and after a resize round trip. The large font and escaped box remain after an
additional two seconds, with no pending GPU frame. Re-dispatching `input` with
unchanged contents restores the model-consistent font and repositions the box.
This is evidence of a stale placement/typography update, rather than a capture
deadline problem. It is distinct from comparing an old input rectangle with a
new canvas rectangle in two separate Playwright calls.

The focused DPR-only experiment additionally observes `devicePixelRatio` changing
to 1.25 and 2 with CSS dimensions unchanged while the backing stays at 960×600.
The expected backing is respectively 1200×750 and 1920×1200. It does not catch up
within the unchanged 30-second observation budget. No CSS resize event occurs.
This identifies a missing readiness condition for that emulated transition;
moving a browser between physical monitors was not tested. A resize event is
required only when CSS viewport dimensions change; backing agreement is checked
independently for DPR-only transitions.

## Evidence-based CI changes to prepare

### Scope clarification and full SSOT audit

The geometry matrix does not verify all interactions. Its initial-visibility,
containment and accessibility results must not be described as a complete range
in which every interaction works. The unchanged-input intervention is a causal
diagnostic and is not included in an acceptance verdict.

A separate [SSOT and interaction audit](evidence/layout-validity-20261021/ssot-interaction-audit.json)
now compares complete documents, with no field exclusions. It preserves full
browser and native documents in the adjacent `ssot-*-full.json.gz` archives.

- Browser shrink/grow/idle observations have zero differences both from the
  pre-resize document and between Python and browser SSOT. The document font
  remains 16 while the HTML inline editor displays 65.3617px. Its complete box
  extends 77.34375 CSS pixels below the canvas. The divergence is in the host's
  view projection, not a changed annotation setting.
- Actual keyboard editing at that faulty state succeeds. Enter applies the exact
  text `First\nSecond!`; only the annotation's rich-text segments change in the
  complete Python document. Python and browser documents agree after application.
  Until application, the draft intentionally differs from the committed text.
- Native resizes through 1312×744, 900×520, 1312×845 and back to 1312×744 leave
  the complete document and revision unchanged. The title control still escapes
  its Properties viewport. Scrolling to it and performing a real text edit succeeds.

This establishes specific editing and application behavior while reproducing the
view defects. Selection, dragging, text selection, cancellation and every other
object/control combination are not all validated by these measurements.

### Live-state recheck and automatic-layout interpretation

Equality of accepted documents alone does **not** establish that all view output
must be history-independent. Automatic ranges, ticks, label placement and other
layout policies may legitimately retain state between operations. Whole-image or
whole-layout round-trip equality requires an explicit contract; it is not a
general consequence of SSOT equality.

The [live-state recheck](evidence/layout-validity-20261021/live-ssot-recheck.json)
adds read-only exports to a temporary diagnostic widget module. It reads the
renderer's actual configuration and series, composed live document, calculated
annotation geometry, calculated data-area geometry, inline draft and available
ephemeral selection/focus state. Comparing the same instance before shrinking
and after growing back, all eight exported groups are identical with sorted JSON
comparison, no numeric normalization and no field exclusions. The viewport, DPR,
backing dimensions, draft value and caret range also match. This does not claim
equality of every unexported renderer cache.

The input-style operand trace identifies the specific difference: while a resize
is queued, the CSS canvas width is already 960 but its physical backing width is
still 235. The host assigns `16 × 960 / 235 = 65.3617px` to the HTML input. No
subsequent position calculation runs when the backing reaches 960. The rendered
annotation and data-area geometry return to their initial values while that HTML
style remains. This is a mixed-epoch coordinate calculation in the host editor;
the observation does not establish a general defect in automatic layout or
justify requiring every layout choice to reverse exactly.

Python/browser JSON may spell equal numbers as `16.0` versus `16`. The earlier
cross-host semantic hash normalizes integral numbers. Same-source pre/post hashes
remain identical without that normalization; the live recheck above reports its
unmodified numeric comparisons explicitly.

### Proposed acceptance coverage

1. Retain minimum/default window cases and report initial visibility separately
   from ordinary-wheel and precision accessibility. Initial visibility is a UX
   contract that must be justified explicitly, rather than inferred from an SSOT
   invariant or from the fact that a scrollable form contains offscreen controls.
   Keep the current failure visible while reviewing that contract; no existing
   assertion is changed by this investigation.
2. Read native target, frame, viewport and controls from one statistics snapshot.
   Read browser rectangles together after size readiness; keep CSS and physical
   units explicit. This removes measurement-order ambiguity without enlarging the
   accepted geometry.
3. Extend browser coverage to all four sides of the complete box and hint. Keep
   input-rectangle results as a separate measurement. The present implementation
   must continue failing cases where stable geometry is outside those bounds.
4. Cover the specific mixed-epoch inline-font calculation using directly recorded
   operands and the editor's declared scaling policy. Do not require generic
   round-trip equality of automatic ranges, tick placement or layout choices.
   Record unchanged-text input intervention as diagnosis, not as an automatic
   repair in the acceptance test.
5. Keep high-DPI and missing-geometry failures visible. Require backing agreement
   for DPR transitions without demanding an unrelated CSS resize event. Investigate
   opening failures before treating their bounds combinations as validated.

No failing size is removed, no new 845px minimum is proposed, and no timeout or
pixel tolerance is increased by these measurements.

## Implementation and acceptance tests after measurement

The browser inline editor now calculates typography from document width and
current CSS width. It never uses an asynchronously resized backing surface as
the document-unit denominator. Textarea sizing precedes final placement, and the
complete bordered box, including its shortcut hint, is constrained to the canvas.
The hint stays on one line with an accessible full-text tooltip. Completing a
surface resize also updates the inline editor. DPR-only transitions use the same
resize path; the existing animation loop checks the DPR scalar without measuring
layout on unchanged frames. This does not depend on CSS resize or media-query
events being emitted.

The native form remains scrollable, with common typography first. At short form
heights, wheel increments are scaled down so an ordinary wheel step does not skip
the interval in which a text field fits. Selection still resets the form to its
top. Initial visibility of every row is not the contract for a scrollable form;
accessibility and actual editing are tested at the existing default and minimum
window sizes.

`test_inline_editor_resize_uses_current_units_and_applies_real_edits` runs against
the installed release wheel at DPR 1 and 2. A test-only barrier holds the existing
host queue while CSS grows, guaranteeing the scheduling order that exposed the
font defect. A read-only operand trace confirms that the real position callback
ran before the queued backing resize. No input event repairs the layout before
the assertion. On the unchanged `a1e79a8` wheel, this test fails with the measured
font `65.3617` instead of the authored `16` at document CSS width 960.

The regression also covers DPR-only transitions, shrinking and growing, multiline
and wrapped scientific text, all four sides of the complete box, retained draft
and focus, and real pointer/keyboard application and cancellation. It exports the
renderer's actual configuration and series through a read-only test hook; the
public cached snapshot alone is not used as proof of live renderer state. The
authored annotation stays unchanged before application, and the complete Python
document equals the live renderer document after application. No global automatic
layout or image round-trip equality is asserted.

The original browser test now waits for independently defined size readiness and
reads all rectangles atomically. It retains its existing IME, formatting and
apply behavior checks. The native overlay test now scrolls with ordinary wheel
input, verifies that navigation preserves the document and revision, and performs
real text edits at 1312×744 and 900×520. The browser overlay test also applies a
property edit and verifies ownership. Existing time budgets and the 1px geometry
tolerance are unchanged. Failures remain failures; neither bounds-based waiting
nor retry-to-pass is introduced.

These targeted contracts do not validate every matrix combination above. In
particular, the two high-font annotation-opening failures remain unexplained;
physical monitor transitions and physical GPU behavior were not tested.

### Why the earlier CI passed

The green run at `1989fdc` ([39536972697](https://github.com/shim9610/figgy-python/actions/runs/39536972697))
predates the typography reorder at `45de028`. The subsequent full run at
`cf51594` ([39547728840](https://github.com/shim9610/figgy-python/actions/runs/39547728840))
failed with 464 passes and two failures. The observation-only run at `a1e79a8`
([39553435513](https://github.com/shim9610/figgy-python/actions/runs/39553435513))
also failed its native gate; it did not execute the later full suite. The newer
failing revision did not receive a successful full-suite result.

The old browser assertion checked only the textarea's horizontal bounds, after
waiting for focus that was already present. It did not check the computed font,
vertical containment, complete box/hint, queued growth or DPR-only transitions.
It could also compare two different layout epochs through separate Playwright
reads. Saving a screenshot in these cases did not compare it with a visual
baseline. Passing that assertion therefore did not establish correct typography
or full containment. The new regression rejects the original implementation
before accepting the fix; CI runs it before the existing priority and full suites.

### Local verification of the corrected release wheel

[Validation manifest and compressed evidence](evidence/layout-validity-20261021/implementation-validation/manifest.json)
retain baseline installed-asset hashes, the failing assertion and queued operands,
corrected installed-asset hashes, live-document observations and JUnit results.

- The unchanged baseline wheel fails the finalized regression at
  `assert 65.3617 == 16` (15.07 seconds).
- Both new DPR regressions pass on the corrected wheel (31.14 seconds total).
- The existing Cartesian and radial inline-edit cases and native/browser overlay
  edit cases all pass on that same corrected wheel (four cases, 99.95 seconds).
  There are no skips in these six UI cases.
- Workflow/assets preflight passes all 117 cases. Locked Rust compilation,
  formatting, JavaScript syntax, Python compilation and release packaging pass.
  The no-display full suite passes 386 cases and skips 82 UI-dependent cases;
  that run does not establish full UI coverage.

These are local results, separate from the subsequent GitHub Actions run.
