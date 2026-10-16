# figgyplot distribution and compatibility

The PyPI distribution and Python import name are both `figgyplot`:

```sh
pip install figgyplot
pip install 'figgyplot[notebook]'
```

```python
import figgyplot as plt
# A matplotlib-like subset is also available:
import figgyplot.pyplot as pyplot
```

Version 0.2.1 is published; this source tree prepares 0.3.0 (registry status
checked 2026-10-16). The GitHub repository remains `shim9610/figgy-python`.
No `figgy` compatibility package is shipped: that name belongs to an unrelated
PyPI package. Existing source users should change `import figgy` to
`import figgyplot as figgy`, or update their aliases. New Copy Python exports
reference `figgyplot` when they need to import text helpers.

## Configured wheel coverage

| Platform / architecture | CPython | Compatibility target |
| --- | --- | --- |
| Linux glibc x86_64 / ARM64 | 3.8–3.15, 3.14t / 3.15t | manylinux_2_28 (glibc 2.28+) |
| Linux musl x86_64 / ARM64 | 3.9–3.15, 3.14t / 3.15t | musllinux_1_2 (musl 1.2+) |
| Windows x86_64 | 3.8–3.15, 3.14t / 3.15t | native MSVC wheel |
| Windows ARM64 | 3.12–3.15, 3.14t / 3.15t | native ARM64 MSVC wheel |
| macOS Intel | 3.8–3.15, 3.14t / 3.15t | extension deployment target 10.15 |
| macOS Apple Silicon | 3.8–3.15, 3.14t / 3.15t | extension deployment target 11.0 |

These are **74 configured wheel combinations**, not a claim that all runners or
hardware have been verified. NumPy's published Windows ARM64 wheels start at
Python 3.12. Current musllinux images no longer provide Python 3.8. macOS's actual
minimum also depends on the selected Python/NumPy distribution and graphics driver.
32-bit targets, PyPy, GraalPy and mobile native hosts are not in this release matrix.
Browser WASM remains a separate packaged renderer; the Python extension is native.

Core bindings use PyO3/NumPy Rust crates 0.29, CPython 3.8–3.15 and NumPy 1.24+.
`Requires-Python` is bounded to `>=3.8,<3.16`; Python 3.8 resolves NumPy 1.24.4,
while newer interpreters resolve compatible NumPy versions. Python 3.8's
`str.removeprefix` gap is handled without changing chart semantics. Optional
GPU benchmark dependencies have their own, newer interpreter requirements.

The `t` variants support installation in free-threaded interpreters. The native
extension explicitly declares `gil_used = true` to preserve its current Python/
NumPy thread guarantees; importing it can enable the interpreter GIL and emit
Python's corresponding warning. These wheels do not promise GIL-free execution.
Native GPU waits/rendering continue to release the GIL where implemented.
PyO3 0.29 does not support Python 3.13t, so that variant is excluded.

## Build and runtime boundaries

A compatible wheel contains the native extension, JS/WASM, CSS and font notices.
Installing it needs no Rust compiler or WASM build. If no matching wheel exists,
source builds require Rust 1.99+, a C/C++ toolchain and access to Cargo dependencies.
The upstream renderer requires Rust 1.99; its sources are not vendored or modified.

Native rendering still needs a supported driver and desktop display for windows.
Importing the package and creating a browser-backend document do not require a
kernel GPU. Jupyter requires a WebGPU browser over HTTPS/localhost and the notebook
extra; frontend/server and kernel dependencies must be available in their own
remote-kernel environments. Compilation of GPU shaders occurs on the actual
runtime GPU, independently of wheel installation.

Native input remains f32/f64 with the existing hi/lo staging path. This packaging
update does not introduce downsampling, streaming, automatic eviction or permanent
native CPU copies of source arrays.

## Manual wheel builds and publication

[The wheel workflow](../.github/workflows/wheels.yml) accepts `workflow_dispatch`
and reuse through `workflow_call` from the manual publication workflow.
That wheel workflow has no push, pull-request, tag, release or scheduled triggers.
The separate `pr-tests.yml` workflow runs automatically for pull requests,
including native/X11 and real Jupyter/WebGPU interaction checks.
[Manual TestPyPI publication](PUBLISHING.md) builds
and validates the full distribution set before upload and installation checks.
Manual production PyPI promotion reuses the exact successful TestPyPI artifacts;
see the separate `pypi` publisher/environment and run-ID setup in that guide.

Each combination builds an interpreter-specific wheel, performs strict metadata
checks, installs only binary distributions in a fresh venv and verifies imports,
NumPy/model operations and local notebook assets without requiring a GPU. The
Linux functional job tests the installed portable CPython 3.12 wheel under Xvfb
and software Vulkan. Physical Windows/macOS/ARM64 GPU behavior needs separate tests.

Linux builds execute inside the selected manylinux/musllinux image. Normal and
free-threaded image interpreters are selected explicitly; the glibc image installs
an older portable Python 3.8 only when needed. CI compiles the extension inside the glibc 2.28 environment. Local validation
also builds with Zig's glibc 2.28 sysroot and checks ELF symbol requirements and
actual import/model execution on AlmaLinux 8. Neither path relabels a wheel that
requires newer glibc.
The musl builds disable Rust's default static CRT to produce an importable cdylib.

Both Linux builds and binary-only installation checks run in the same matrix
image and architecture. In particular, a musllinux wheel is installed inside
musllinux rather than on the Ubuntu glibc runner. Windows/macOS installation
checks run directly on their native runners. A prerequisite job validates the
workflow against the actual `maturin-action@v1` input metadata and exercises
regressions before starting any of the 74 wheel builds.

### First manual run failures and repair (2026-10-14)

[Run 38560470018](https://github.com/shim9610/figgy-python/actions/runs/38560470018)
used commit `820bd7f`. All 24 failed Linux job logs were inspected:

- The input `before-script` is unsupported; the action only reads
  `before-script-linux`. The preparation script was ignored, leaving
  `/usr/local/bin/python3.x` absent. Ten musl jobs reported an invalid interpreter.
- The action already adds `--manylinux` from its `manylinux` input. Also passing
  its alias `--compatibility` supplied two platform tags. Fourteen glibc jobs
  reported `Expected only one platform tag but found 2`.
- The following installation step would have tried to load musllinux artifacts
  on Ubuntu. It now runs in the same explicit container image as the build.

The source distribution succeeded. The other 50 wheel jobs and the functional
job were cancelled; Windows/macOS builds did not reach a verified result.
No renderer or plotting API change is required for these workflow errors.

Repair validation covers actionlint, shell syntax, all 74 matrix expansions,
seven workflow regressions, ten actual interpreter/ABI selections on AlmaLinux 8,
and failures for a wrong free-threaded ABI, unsupported selector and absent musl
interpreter. The duplicate-tag error was reproduced directly with maturin 1.15.0.
Three x86_64 manylinux wheels (3.8, 3.12, 3.15t) were rebuilt on AlmaLinux 8 with
Zig's glibc 2.28 sysroot, using the repaired single-tag/interpreter arguments.
Binary-only fresh installs, strict Twine checks, imports, NumPy/model operations
and packaged JS/WASM checks passed. Python 3.8 exercised the portable-interpreter
fallback; local 3.15t is `3.15.0rc3`, and importing the extension enables the GIL
as documented. The previously built, unchanged Python 3.12 musllinux wheel also
passed strict metadata and binary-only installation/model/assets checks on Alpine.
These are GPU-free checks, not new UI/hardware validation or a full Actions run.

The next [run 38563497232](https://github.com/shim9610/figgy-python/actions/runs/38563497232),
using `7a7a107`, stopped in preflight with ShellCheck `SC2016`; no wheels were
built. The nested single-quoted `bash -c` command intentionally deferred variable
expansion but triggered the runner's ShellCheck. Earlier local actionlint runs
had silently omitted ShellCheck because it was absent from PATH. Preflight now
installs both actionlint and ShellCheck explicitly, and Xvfb receives its child
script through a quoted heredoc. The complete preflight command sequence passed
in a fresh repository with both tools, alongside the seven regressions. Actual
Xvfb/child-shell execution also verified success and propagation of a nonzero
child exit code. These checks do not mark the skipped platform builds as passed.

[Run 38564193205](https://github.com/shim9610/figgy-python/actions/runs/38564193205),
using `0c11307`, passed preflight and multiple Linux/macOS builds. Its inspected
Windows x86_64/ARM64 failures occurred after successful build and installation:
Git's `core.autocrlf=true` converted the upstream `figgy.js` from 151,571 LF bytes
to 155,281 CRLF bytes, breaking its recorded SHA-256. `.gitattributes` now disables
text conversion for the content-addressed asset directory. Hashes are checked
unchanged; mismatches report the file, expected/actual hashes and sizes, and a
CRLF hint when applicable. A GPU-free source check and Windows-style Git checkout
regressions run before wheel builds. The full preflight passed eleven tests in a
fresh repository; an actual maturin sdist from a Windows-style checkout preserved
both asset hashes and passed strict metadata validation. An installed Linux wheel
also passed the revised smoke checker. The corrected Windows wheel jobs still
require a new Actions run; the free-threaded GIL warning is expected and unrelated
to the asset failure. These checks do not claim Windows GPU/UI validation.

The next run at `03996da` successfully built and smoke-tested **all 74 wheel
combinations** and the sdist. Its final Linux UI job exposed a missing
`libxkbcommon-x11.so.0` on the runner. This is a dynamically loaded X11 runtime
dependency; offscreen GPU rendering and import can succeed without it. The X11
jobs now install `libxkbcommon0`/`libxkbcommon-x11-0`, probe the libraries before
winit initialization, and allocate a 1600×1000 Xvfb screen for expanded editors.
See [repository setup](REPOSITORY_SETUP.md) for the staged PR/CodeQL workflows and
the distinction between executed software-GPU tests and pending GitHub runs.

To test the repair in GitHub, choose **Run workflow** on **main** after pulling
the fix. **Re-run jobs** retains that run's original commit and workflow.
Wheel builds and publication remain manual; PR validation runs automatically.

## Release gates and version-specific evidence

Completed 0.2.1 build/install checks below are historical evidence. Version 0.3.0
must build and verify its own 74 wheels and sdist, then pass both indices'
installation checks. Its native and WASM renderer sources remain pinned together
as described in [publishing](PUBLISHING.md#versions-and-coordinated-release-order).

- [x] Confirm Trusted Publishing works for `figgyplot` on PyPI/TestPyPI.
- [x] Run the manual workflow and review all 74 configured wheel results (0.2.1).
- [ ] Verify Windows/macOS and ARM64 window creation, DPI, editing, close/reopen
      and PNG export on actual target hosts.
- [x] Verify native/X11 and actual JupyterLab editing for the 0.3.0 PR on Linux
      software GPUs: [246-test run at 07b3786](https://github.com/shim9610/figgy-python/actions/runs/38886971056).
- [ ] Install matching artifacts on clean hosts without Rust and ensure `pip`
      selects wheels rather than silently falling back to source builds.
- [x] Prepare the manual TestPyPI workflow with OIDC and installation checks.
- [x] Execute TestPyPI 0.2.0 publication and its nine post-upload installation checks.
- [x] Register the production [Trusted Publisher](PUBLISHING.md), validate the
      0.2.1 preview and promote its verified artifacts to PyPI.

Local build/installation results for this change are recorded in
[the packaging report](../reports/figgyplot-packaging.json). Configured targets
and executed verification are reported separately. Existing renderer benchmarks
are retained under their originally measured package/source versions.

## Executed checks (2026-10-14)

- Built and strictly checked four x86_64 `manylinux_2_28` wheels (3.8, 3.12,
  3.15 and 3.15t), one 3.12 `musllinux_1_2` wheel and the source distribution.
  No legacy `figgy/` package is present; metadata URLs, fonts and local WASM/JS
  are included. All four glibc binaries require at most GLIBC_2.28.
- Actual glibc 2.28 (AlmaLinux 8) import/model/assets passed using Python 3.8.20
  and NumPy 1.24.4. Alpine's binary-only install/import/model/assets passed with
  Python 3.12.15 and NumPy 2.5.4. These container checks do not initialize GPUs.
- Python 3.8.20 passed 48 model/render/notebook/code-generation tests. Local
  3.15.0rc3 and 3.15.0rc3 free-threaded each passed 54 tests, including shared
  GPU/context concurrency. The free-threaded import enables the GIL as declared.
- The portable Python 3.12 wheel was tested on software Vulkan and actual
  headed JupyterLab/Chromium WebGPU. Browser binary upload, in-browser editing,
  kernel revision sync, readable clipboard code and PNG exports passed.
- Python 3.8 compatibility testing found eagerly loop-bound notebook events;
  one-shot notification waiters now use their active request loops and recover
  across separate `asyncio.run` calls. Native/radial clipboard imports now use
  `figgyplot._codegen`; browser checks compare actual copied code to `to_code()`.

Windows/macOS/ARM64 configurations are prepared but have not been executed by
the original local packaging checks. Subsequent 0.2.1 GitHub runs built all
74 platform/interpreter wheels and passed nine clean installation jobs on each
index. This establishes build/install compatibility, not actual hardware GPU
window or browser verification on every target.

The final software-GPU validation covers **82 distinct tests** in split execution:
76 non-desktop tests passed in the full invocation (including actual JupyterLab
and the browser fallback editor), and all six final X11 desktop tests passed
under Openbox (77.60 s). An earlier radial input failure depended on reused window
placement/unchanged cursor positions across tests; the X11 input harness now puts
its expanding inspector on-screen and delivers actual motion before clicking.
No production picking/rendering workaround was added for that host condition.

## Publication status

Version **0.2.1** is published on [PyPI](https://pypi.org/project/figgyplot/0.2.1/).
The [production workflow](https://github.com/shim9610/figgy-python/actions/runs/38620599251)
succeeded after the [complete TestPyPI recheck](https://github.com/shim9610/figgy-python/actions/runs/38618489720).
All 74 wheels and one sdist were uploaded; all nine production-index installation
jobs passed. Install with `python -m pip install figgyplot`, or
`python -m pip install 'figgyplot[notebook]'` for Jupyter.

Version **0.3.0** is prepared: figgy-renderer 0.17.0, the fixes reported against
0.2.1, and the corrected installation instructions first prepared as 0.2.2 (never
uploaded). It adds native/Jupyter editing parity, bounded-chart constructors,
selected histogram values, numeric label controls and paired-axis convenience
edits. It has not been uploaded as of 2026-10-16; it needs its own full wheel and
index installation checks. Passing PR tests does not publish a package.
