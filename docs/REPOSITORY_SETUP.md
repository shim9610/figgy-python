# Repository security and CI rollout

The security policy, code of conduct, contributing guide, issue forms and PR
template are maintained in this repository. The security/moderation contact is
**ssy9610@gmail.com**. The repository description and security feature switches
are GitHub administration settings; committing these files does not enable them.

## Owner settings

With an already authenticated GitHub CLI identity that administers this repo:

```sh
bash scripts/configure-github-security.sh shim9610/figgy-python
```

The script sets the description and enables private vulnerability reporting,
Dependabot alerts, secret scanning and secret push protection. It checks the active
identity's admin access before writing and reports applied settings. It does not
modify branch protection. It may stop partway if a setting is unavailable; inspect
the reported response and remaining UI switches. No token is stored in the repo.

These writes could not be executed in the Codex cloud session: the connected
GitHub tools provide no repository-administration write operation, and the CLI's
GitHub API access is blocked by the environment network policy. The connected
repository metadata reports admin access, so this is a tool/network limitation,
not a claim that the repository owner lacks permission.

Equivalent UI locations are **Settings → Advanced Security** (or **Code security**
on some layouts): private vulnerability reporting, Dependabot alerts, secret
scanning and push protection. Enable the dependency graph if prompted.
Security advisories were already enabled in the supplied overview. For code
scanning, use the prepared advanced CodeQL workflow rather than enabling a second
default workflow that duplicates it.

`.github/dependabot.yml` prepares GitHub Actions, pip and Cargo update policies.
Regular version-update PRs are paused with `open-pull-requests-limit: 0`. After
PR CI is stable, change those limits to `3` if regular updates are wanted. Alerts
and security-update PRs have separate GitHub settings. Renderer/wgpu/egui/winit
updates must be coordinated in a compatibility PR; they are ignored by automatic
Cargo updates.

## Workflow state and activation

All executable Actions are pinned to reviewed commit SHAs. JavaScript Actions
use Node 24 releases; shell-only Rust setup is also pinned. The pinned maturin
commit is used for both its input-metadata checkout and the actual build.

| Workflow | Initial trigger | Scope |
| --- | --- | --- |
| Build figgyplot wheels | Manual only | 74 platform/Python/ABI wheels, sdist and Linux functional verification |
| PR tests | Manual until stabilization | Workflow/assets preflight; installed Linux native wheel, X11 editor and real JupyterLab/browser WebGPU tests |
| CodeQL | Manual until first successful scan | Python, Rust and JavaScript security-extended queries, no build; generated upstream assets excluded |

Run **PR tests → Run workflow** on the desired branch. Its integration job builds
and installs that checkout's wheel, loads local assets, uses Mesa lavapipe for
native rendering and Chromium's SwiftShader for browser WebGPU, and saves JUnit
results/test artifacts for five days. Missing software drivers or Chromium fail
explicitly. UI/GPU checks are software-GPU checks, not hardware certification.
The outer CI job timeout does not change production GPU wait behavior.
The X11 jobs install and probe `libxkbcommon0`, `libxkbcommon-x11-0`, the X11
library and Vulkan loader before creating the winit event loop, and use a
1600×1000 Xvfb display so expanded inspectors stay on screen.

After the wheel run and the first PR test run pass, activate the commented
`pull_request` block in `.github/workflows/pr-tests.yml`. Enable `merge_group`
too if using GitHub's merge queue. Do not add path filters to required workflows:
otherwise some PRs can wait forever for checks that were never scheduled.

Run **CodeQL → Run workflow** once on `main`. After its three language scans
successfully upload results, activate its commented PR/main-push triggers and
optional weekly schedule. CodeQL execution/upload has not been verified merely
by preparing or linting its workflow. Regular wheel builds remain manual.

Fork PR tests use `contents: read`, do not publish packages and do not use
`pull_request_target`. CodeQL grants `security-events: write` only to its analysis
job. Required test workflows have no path filters and fixed check names.

## Main branch protection

Once the PR workflow has registered successful runs, select these check names
in the `main` ruleset/branch protection:

- **PR / Workflow and assets**
- **PR / Linux integration**

Require pull requests and passing checks before merging. Decide whether to
require the branch to be up to date or use the merge queue. Approval requirements
are a separate choice: a PR author cannot approve their own PR, which matters for
a repository with one maintainer. Add CodeQL checks only after their actual scans
are verified and their event coverage matches the chosen merge workflow.

No main-branch protection, automatic merge or PyPI publication is configured by
this change. New GitHub executions are needed to verify the newly pinned Actions
and PR/CodeQL workflow behavior; local test results are reported separately.

## Executed validation for this preparation

- The previous manual run at `03996da` built and checked all 74 configured wheels
  and the sdist. Its final Linux functional job failed when the runner lacked
  `libxkbcommon-x11.so.0`; that first winit initialization panic caused the later
  event-loop/resource test failures. The dependency and early loader probe are
  now explicit in both X11 workflows.
- The local installed-wheel suite passed **93 tests in 146.71 s**, including
  actual native surface/input editing and real headed JupyterLab/Chromium
  WebGPU with kernel synchronization. This uses Mesa/SwiftShader software GPUs.
- The prepared workflows passed actionlint with ShellCheck, actual pinned Action
  input-metadata validation, manual-trigger/permission checks and eleven
  preflight regressions. Rust formatting and shell syntax checks passed.
- A fresh Ubuntu 24.04 container passed 90 distinct tests in split execution:
  88 in the full run and the two Git-checkout cases after installing Git.
  Three browser/Jupyter cases skipped in that container are covered by the
  separate local suite. CodeQL scans/uploads and administration switches remain
  unexecuted.

The above run does not verify the newly pinned Actions remotely. Keep automatic
events disabled until the next manual run confirms the final workflow behavior.
