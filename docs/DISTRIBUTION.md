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

Publication is pending. The GitHub repository remains `shim9610/figgy-python`.
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

## Manual CI only

[The wheel workflow](../.github/workflows/wheels.yml) has only `workflow_dispatch`.
There are no push, pull-request, tag, release or scheduled triggers. Adding the
configuration does not run it. No PyPI upload job is enabled.

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
Automatic triggers and publication remain disabled.

## Release gates

- [ ] Confirm ownership/registration of `figgyplot` on PyPI/TestPyPI.
- [ ] Run the manual workflow and review all configured wheel results.
- [ ] Verify Windows/macOS and ARM64 window creation, DPI, editing, close/reopen
      and PNG export on actual target hosts.
- [ ] Verify browser editing in actual JupyterLab after installation.
- [ ] Install matching artifacts on clean hosts without Rust and ensure `pip`
      selects wheels rather than silently falling back to source builds.
- [ ] Configure a separately reviewed manual publication job/Trusted Publisher,
      exercise TestPyPI, then publish an immutable release version.

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
this change. Actionlint, shell syntax and manual-only matrix expansion checks
passed; no GitHub workflow was dispatched. PyPI publication remains pending.

The final software-GPU validation covers **82 distinct tests** in split execution:
76 non-desktop tests passed in the full invocation (including actual JupyterLab
and the browser fallback editor), and all six final X11 desktop tests passed
under Openbox (77.60 s). An earlier radial input failure depended on reused window
placement/unchanged cursor positions across tests; the X11 input harness now puts
its expanding inspector on-screen and delivers actual motion before clicking.
No production picking/rendering workaround was added for that host condition.
