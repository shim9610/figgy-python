# Layout failure observation

Baseline: `cf515942e32779579d80830689f36cc431741664`, Actions run
[39547728840](https://github.com/shim9610/figgy-python/actions/runs/39547728840).
The full suite reported 464 passes and two failures. This instrumentation
changes neither layout behavior nor the existing assertion thresholds or waits.

## Browser inline editor

The original sequential Playwright measurements reported an input at x=1054,
width=290 and a canvas at x=389, width=511. Focus was already present before
resizing, so the focus condition does not establish that resizing has completed.
These facts alone do not distinguish a stale measurement from a layout defect.

`inline-layout-probe.json` preserves the original two measurements, their Python
monotonic timestamps and their original assertion result. Only after these reads,
the probe takes atomic DOM snapshots immediately, after 100 ms and after another
400 ms. Each includes viewport dimensions, canvas backing dimensions, ancestor
rectangles, computed CSS, focus, host statistics and GPU completion information.
The resize-event listener records time and viewport dimensions without reading
layout. There are no added waits before the original measurements.

A failed sequential comparison followed by valid atomic bounds is evidence of
different layout epochs being compared. Persistent invalid atomic bounds are
evidence of a real layout problem. A passing instrumented run alone proves
neither explanation for the previous failure.

## Native overlay title inspector

The original failure selected the correct overlay title, but its text control
was at y=702.125, height=20.125, outside the viewport y=464, height=158.
That establishes the visibility failure, not why it occurred.

With `FIGGY_LAYOUT_PROBE=1`, the native inspector retains the last 64 layouts:
egui frame/time, target/context, context-change scroll-reset request, actual
scroll offset, content size, viewport, clipping rectangle, control rectangles
and scale. These observations do not scroll, focus, repaint or commit settings.
The ring is exposed through the existing native window statistics.

`native-layout-probe.json` records initial, pre-drag, post-drag and finally states.
Only after the original assertion has executed does cleanup pump three further
event batches to determine whether the condition persists. A screenshot is saved
even on assertion failure. Native inspector rectangles in the ring are egui
points; top-level native control rectangles are physical pixels.

## CI collection

The two exact failing cases run before the previous priority gate and full suite.
Original failures still fail CI; there is no retry-to-pass or assertion removal.
The existing always-upload step preserves JSON, screenshots, logs and JUnit XML
under the `pr-linux-integration-results` artifact, including failed cases.
