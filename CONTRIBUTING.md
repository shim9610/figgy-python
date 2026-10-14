# Contributing to figgyplot

Use issues for reproducible bugs and focused feature requests. Security reports
go to [the private reporting channel](SECURITY.md), not public issues.
All participation follows our [code of conduct](CODE_OF_CONDUCT.md).

## Development

The distribution/import is `figgyplot`; the repository is `figgy-python`.
Use CPython 3.8–3.15, Rust 1.99+ and the platform C/C++ toolchain.

```sh
python -m venv .venv
# POSIX:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install 'maturin>=1.15,<2' pytest pillow anywidget
maturin develop --release --locked
python -m pytest -q
```

Native render tests need a supported GPU/driver. Window tests additionally need
a desktop display. Linux input tests use Xvfb, Openbox, xdotool, xclip and wmctrl.
A headless import or skipped UI test does not verify window behavior.

For the real JupyterLab/WebGPU tests, install Playwright, Chromium, JupyterLab,
nbformat and ipykernel; set `FIGGY_TEST_JUPYTER=1`. See
[host validation](docs/HOST_VALIDATION.md) and [CI rollout](docs/REPOSITORY_SETUP.md).
These tests use software GPUs in CI; physical Windows/macOS/ARM64 GPU validation
must be recorded separately.

## Implementation boundaries

- Reuse public APIs from the pinned common Rust renderer. Do not vendor its
  source or implement a replacement chart engine here.
- Preserve current f32 inputs and the hi/lo GPU upload path. Do not add automatic
  downsampling, streaming, chunk mode or eviction.
- Native windows use winit/wgpu surfaces and the shared process GPU context.
  Do not restore per-frame RGBA/PNG transport to the native display path.
- Keep notebook data transfers binary, revisions consistent and browser
  interaction independent of kernel PNG round trips.
- Do not add permanent CPU copies of native source arrays. Document temporary
  notebook-transfer data lifetimes.
- Preserve upstream asset hashes. Rebuild through `scripts/build-wasm.sh` when
  intentionally updating the pinned upstream assets.
- Draw report and benchmark charts with Figgy. Distinguish completed readback
  latency from UI display FPS and input latency.

## Pull requests and verification

Branch from current `main`, keep the change focused and use the PR template.
Describe the final behavior, validation performed and remaining platform limits.
Run tests relevant to the change and `cargo fmt --check`. Avoid tests that merely
repeat the implementation.

[PR tests](.github/workflows/pr-tests.yml) and
[CodeQL](.github/workflows/codeql.yml) are prepared for automatic PR execution,
but remain manual until stabilization. Follow the rollout document to activate
them after the wheel matrix is green. Fork PRs use read-only test permissions;
no publication or privileged `pull_request_target` workflow is used.

Dependency updates should respect the pinned renderer and matching wgpu/egui
versions. Dependabot's regular update PRs are paused initially. No automatic merge
or PyPI publication is configured.

