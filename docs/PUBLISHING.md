# Manual TestPyPI publication

The workflow file is **`.github/workflows/publish.yml`**, named
**Publish figgyplot to TestPyPI (manual only)**. It uploads publicly to TestPyPI,
not the production PyPI index. There are no automatic push, PR, tag or release
publication triggers. No API token or password needs to be added to GitHub.

## Complete the pending Trusted Publisher form

On [TestPyPI's publishing page](https://test.pypi.org/manage/account/publishing/),
use the GitHub tab:

| Field | Exact value |
| --- | --- |
| TestPyPI Project Name | `figgyplot` |
| Owner | `shim9610` |
| Repository name | `figgy-python` |
| Workflow name | **`publish.yml`** (just the filename) |
| Environment name | **`testpypi`** |

Click **Add**. The workflow filename and environment must match exactly;
`workflow.yml` is only the form's example and is not this repository's filename.
The pending publisher creates the project when the first upload succeeds.
See the [official Trusted Publisher guide](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

In GitHub **Settings → Environments → New environment**, create **`testpypi`**.
Under deployment branches/tags, select **Selected branches and tags** and allow
the **`main` branch**. Required reviewers are optional; configuring one introduces
an approval step before the upload. The workflow also rejects dispatches from
other branches before building. This does not change main's branch protection.

## Run publication

1. Check that `pyproject.toml` and `Cargo.toml` have the same intended version.
2. Open **Actions → Publish figgyplot to TestPyPI (manual only) → Run workflow**.
3. Select **main** and enter the exact source version (currently **`0.2.0`**).
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
  attestations. Only this job has `id-token: write` and the `testpypi` environment.
  Build/test jobs have no publishing permission; there is no inherited secret.
- Download actual wheels from **TestPyPI only**, compare each with this run's
  release manifest, install without source builds and check imports, NumPy/model
  operations and packaged JS/WASM. Nine post-upload jobs cover six native
  OS/architecture combinations at Python 3.12 plus Linux 3.8, Linux 3.15t and
  Windows ARM64 3.15t. All 74 combinations, including musl, are already checked
  before publication. Post-upload checks do not repeat native/browser GPU tests.

Dependencies come from normal PyPI first. The package download uses
`--isolated --no-cache-dir --only-binary=:all: --no-deps` with TestPyPI as the
only index. No `--extra-index-url` or silent fallback to a PyPI `figgyplot` is used.
Index propagation/download errors retry at most six times, ten seconds apart;
wrong hashes/versions fail immediately. This changes no production GPU waits.

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
version in both source manifests. Re-running the entire publication against an
already uploaded version fails instead of replacing immutable files. Artifact
retention is temporary; archive verified release files/manifest if needed later.

For OIDC errors, check the five fields above and the job's environment. Adding a
PyPI publisher instead of a TestPyPI publisher will not authorize TestPyPI.
Official PyPI publication requires its own account/publisher/environment and a
separate promotion path; this workflow never uploads to production PyPI.

## Validation performed for this change

The workflow, ShellCheck, reusable-build contract and release regressions are
checked locally. Existing real glibc/musl wheels and a newly built sdist are
inspected with the release validator; no filenames or binary tags are repaired.
Local tests cannot prove GitHub OIDC issuance or TestPyPI upload/index behavior.
Those require completing the pending publisher and executing this workflow.
