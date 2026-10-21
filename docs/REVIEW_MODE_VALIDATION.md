# Review mode validation

This records local validation of the unreleased #18 implementation. Required
GitHub checks still run on the draft PR's exact commit.

## Final wheel

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
UI-enabled invocation passed **633 tests in 2460.86 seconds**. The final wheel was
then rebuilt and the 46 review cases, four existing layout probes and preflight
checks above were rerun. This is not a claim that the final wheel completed a
second full-suite invocation locally. The draft PR's CI supplies that check.

No thresholds, gesture assertions, pixel tolerances or CI time limits were relaxed.
The notebook harness now accepts an explicit expected initial view count and
requires every such view to reach Ready within the existing startup budget.
