# Manual TestPyPI and PyPI publication

The workflow file is **`.github/workflows/publish.yml`**, named
**Publish figgyplot (manual only)**. Choose `target=testpypi` to build and test a
preview, then `target=pypi` to promote that successful run's exact files to the
production index. `target=verify-testpypi` checks an already uploaded release
without rebuilding or uploading it. The default is TestPyPI. There are no automatic push, PR, tag
or release publication triggers. No API token or password needs to be added to GitHub.

## Trusted Publisher setup

The 0.2.1 publication already verified the TestPyPI and PyPI publishers below.
Retain those registrations for subsequent releases; this setup is needed only when configuring
or repairing a publisher.

On [TestPyPI's publishing page](https://test.pypi.org/manage/account/publishing/),
use the GitHub tab:

| Field | Exact value |
| --- | --- |
| TestPyPI Project Name | `figgyplot` |
| Owner | `shim9610` |
| Repository name | `figgy-python` |
| Workflow name | **`publish.yml`** (just the filename) |
| Environment name | **`testpypi`** |

Register a **separate** publisher on
[production PyPI](https://pypi.org/manage/account/publishing/) with the same
project/owner/repository/workflow fields, but environment **`pypi`**.
Click **Add** there as well; merely filling in the form does not register it.

Click **Add**. The workflow filename and environment must match exactly;
`workflow.yml` is only the form's example and is not this repository's filename.
The pending publisher creates the project when the first upload succeeds.
See the [official Trusted Publisher guide](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

In GitHub **Settings → Environments → New environment**, create **`testpypi`**
and **`pypi`**.
Under deployment branches/tags, select **Selected branches and tags** and allow
the **`main` branch**. Required reviewers are optional; configuring one introduces
an approval step before the upload. The workflow also rejects dispatches from
other branches before building. This does not change main's branch protection.

## Versions and coordinated release order

| Component | Working tree version | Published version verified 2026-10-21 |
| --- | --- | --- |
| `figgy-model` | 0.12.1 | 0.12.1 |
| `figgy-renderer` | 0.18.1 | 0.18.1 |
| `figgyplot` | 0.4.0 | 0.3.0 |
| `figgy` WASM wrapper | 0.15.1 | Not a crates.io package (`publish = false`) |

Model 0.12.1 and renderer 0.18.1 were published on 2026-10-21. Python 0.3.0 was published on
2026-10-16 with renderer 0.17.0/model 0.11.0, as verified from its PyPI sdist.
This tree targets Python 0.4.0; its artifacts still require the complete
TestPyPI build and installation gates before production promotion. Do not upload
the changed source as 0.3.0. For future coordinated releases,
publish the model before the renderer, then the Python package. Each package
has its own version; the WASM wrapper's 0.15.1 is not the renderer version.
The native extension consumes crates.io packages with versions and checksums
pinned in `Cargo.lock`. The bundled WASM uses their upstream release revision
`f3f569c4c0e32d3d0682632444b6fe7ce84cba8d`, recorded in
`scripts/build-wasm.sh` and `python/figgyplot/assets/provenance.json`.

When updating the renderer, update the registry dependency and lockfile, then
rebuild WASM from the matching clean release checkout. The rebuild verifies the
downloaded `.crate` checksums, `.cargo_vcs_info.json` source revision and Rust
sources before recording provenance. Offline preflight checks that the native
versions/checksums and WASM revision remain paired; Git/path overrides fail this
gate. The build then applies `scripts/wasm-host.patch` to a disposable copy of
the web host. This additive binding patch exposes non-borrowing GPU completion and renderer
annotation preparation without waiting for display completion;
it does not change renderer/model sources. Provenance records its hash, and
preflight rejects a mismatched patch or changes outside the two web host files.
Do not edit provenance by hand to bypass a source mismatch.
Python source builds fetch the Rust dependencies from crates.io; compatible
wheels contain the compiled extension and need neither Git nor Cargo to install.

## Run publication

1. Set the intended version in `Cargo.toml` (`[package] version`), the single version
   source. `pyproject.toml` keeps `dynamic = ["version"]` and `figgyplot.__version__`
   comes from the extension, so neither holds a version of its own. Keep the
   exact renderer version and registry `Cargo.lock` entries paired with the
   packaged WASM provenance. Publishing a new Rust version does not automatically
   update these pinned dependencies or existing Python installations.
2. Open **Actions → Publish figgyplot (manual only) → Run workflow**.
3. Select **main**, **target `testpypi`** and version **`0.4.0`**, matching the
   source version set in step 1. Leave the run-ID input empty.
4. Run it. This is an actual public TestPyPI upload, not a build-only dry run.

The pipeline runs these gates in order:

- Reuse `wheels.yml` at the same commit: all 74 native wheels, the sdist,
  binary-only installation checks and the Linux software-GPU functional suite.
  `workflow_call` enables this reuse; standalone wheel builds remain manual.
- Require every expected platform/interpreter/ABI artifact, exactly one file per
  artifact, matching package/version/Python requirements and native extensions.
  Inspect wheel tags and compare all packaged Python/JS/CSS/WASM/license files
  with this source checkout. Git attributes keep package text LF on Windows;
  upstream assets remain byte-preserved. Validate the sdist as well.
- Run strict Twine metadata validation; retain the exact 75 distribution files
  and their SHA-256/size manifest as separate artifacts for 30 days.
- Upload those files through PyPA's pinned publishing Action and OIDC, with
  attestations. Only this job has `id-token: write` and the selected environment.
  Build/test jobs have no publishing permission; there is no inherited secret.
- Download actual wheels from **TestPyPI only**, compare each with this run's
  release manifest, execute the public index `pip install` command in a fresh
  environment, compare installed package files (including native code) with the
  verified wheel and check imports, NumPy/model
  operations and packaged JS/WASM. Nine post-upload jobs cover six native
  OS/architecture combinations at Python 3.12 plus Linux 3.8, Linux 3.15t and
  Windows ARM64 3.15t. All 74 combinations, including musl, are already checked
  before publication. Post-upload checks do not repeat native/browser GPU tests.

Dependencies come from normal PyPI first. The package download uses
`--isolated --no-cache-dir --only-binary=:all: --no-deps` with TestPyPI as the
only index. No `--extra-index-url` or silent fallback to a PyPI `figgyplot` is used.
Index propagation/download errors retry at most six times, ten seconds apart;
wrong hashes/versions fail immediately. This changes no production GPU waits.

## Promote the successful preview to PyPI

1. Wait for the **entire** TestPyPI run to finish successfully, including all
   nine index installation jobs. Copy its numeric ID from the run URL.
2. Run `publish.yml` again on **main**, select **target `pypi`**, the same version
   and that **testpypi-run-id**.
3. The workflow requires the same repository, workflow, package inputs, version,
   successful TestPyPI upload/recheck and all expected successful installation jobs.
   A PR test run, failed run, production-only run, changed package inputs or missing
   installation is rejected.
4. It downloads the original release files/manifest, verifies every hash,
   packaged source/asset and all 74 wheel combinations plus one sdist, and
   uploads **without rebuilding** through the `pypi` environment.
5. Nine jobs download from production **PyPI only** and repeat the byte-level
   and import/model/assets installation checks.

Keep package inputs unchanged until promotion. Only the exact publishing
workflow, release-verification scripts/tests and this release guide may change;
the verifier checks Git ancestry and the complete diff against a narrow allowlist.
Changes to Rust/Python code, Cargo inputs, pyproject, the package description,
Git attributes or wheel-build configuration require a new tested release.
The old `0.2.0` run cannot promote `0.2.1` sources. Artifacts expire after 30 days. Do not upload twice
under one version or use `skip-existing` to conceal mixed builds.

## Verify an already uploaded preview

The following records the completed 0.2.1 recovery. For a new release such as
0.3.0, use its own upload/verification run ID; old IDs cannot authorize it.

If a successful upload's installation jobs were skipped, do **not** rebuild and
upload the same version. Run the workflow on **main** with:

- **target:** `verify-testpypi`
- **version:** the uploaded version (`0.2.1` in this historical example)
- **testpypi-run-id:** the original upload's numeric ID, **`38605305486`** for the
  first 0.2.1 upload (from its `/actions/runs/38605305486` URL, not the label `#2`).

This path verifies the original immutable files/manifest and runs all nine
real index installation jobs without an upload or rebuild. It retains the
original build commit, run ID and file hashes, adding only the verification run
ID to the manifest. After the whole recheck succeeds, select `target=pypi` and
enter **the new recheck run ID**, not the original incomplete-verification ID.
PyPI promotion still rejects missing/failed/skipped installation jobs.

The original 0.2.1 TestPyPI run `38605305486` uploaded successfully but its
installation matrix was skipped because the downstream job's implicit
`success()` considered a deliberately skipped ancestor. The installation job
now explicitly uses `always()`, cancellation handling and success of the selected
preparation/upload branch. The failed PyPI run `38612755099` had an empty source
run-ID input and stopped in the gate; it made no production upload.

An authorized maintainer dispatches the workflow through GitHub Actions or an
authenticated GitHub CLI. OIDC supplies the registry identity; no PyPI API key
needs to be placed in the repository.

The free-threaded wheels may enable the GIL on import, as declared by the native
extension. That warning is expected. Native/browser GPU behavior still depends
on the target driver/browser; successful installation is not hardware certification.

## Failure and rerun behavior

A failed build or validation prevents any upload. If upload succeeds but an
installation check fails, the files are already public; examine the installation
log and rerun only the failed jobs. There is no rollback of a published version.

`skip-existing` is deliberately false: a new build must not silently mix with
another build under the same version. If an upload partially succeeds, inspect
which files exist before recovery. A fresh complete release should use a new
version in `Cargo.toml`. Re-running the entire publication against an
already uploaded version fails instead of replacing immutable files. Artifact
retention is temporary; archive verified release files/manifest if needed later.

For OIDC errors, check the five fields above and the job's environment. Adding a
PyPI publisher instead of a TestPyPI publisher will not authorize TestPyPI.
Production PyPI publication uses its own publisher/environment and the explicit
`target=pypi` promotion path; the default selection remains TestPyPI.

## Validation performed for this change

The workflow, ShellCheck, reusable-build contract and release regressions are
checked locally. Existing real glibc/musl wheels and a newly built sdist are
inspected with the release validator; no filenames or binary tags are repaired.
Local tests cannot prove GitHub OIDC issuance or TestPyPI upload/index behavior.
Those require the configured publisher and an actual workflow execution.

The [first complete TestPyPI publication run](https://github.com/shim9610/figgy-python/actions/runs/38590006371)
at `35200d1` subsequently succeeded, including all build gates, upload and the
nine post-upload installation jobs. That run published `0.2.0`.
During that initial 0.2.0 release session, a fresh-venv installation from TestPyPI
was blocked with HTTP 403 by that environment's network proxy. It was not
reported as a successful local index install; the actual nine GitHub index
installation results are the remote evidence. The [0.2.1 recovery run](https://github.com/shim9610/figgy-python/actions/runs/38618489720)
subsequently passed all nine TestPyPI installation jobs. The
[0.2.1 production run](https://github.com/shim9610/figgy-python/actions/runs/38620599251)
completed successfully, publishing all 74 wheels and one sdist to PyPI and
passing all nine production-index installation jobs. PyPI's public JSON metadata
also confirms version 0.2.1 with 75 distribution files.

The published 0.3.0 release uses figgy-renderer 0.17.0 and includes the fixes
reported against 0.2.1; it also carries the installation instructions prepared
as 0.2.2, which was never uploaded. The renderer 0.18 migration targets Python
0.4.0 and needs its own TestPyPI build/upload and installation
checks before promotion. Follow the coordinated version order above while
retaining the native/WASM source pins.
Future description changes are package metadata: committing `PYPI_README.md`
does not replace the uploaded release's description. Publish a new version to
include an updated description; this documentation change does not upload one.
