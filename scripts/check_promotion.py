"""Verify successful TestPyPI provenance and immutable files before PyPI upload."""
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import re
import tomllib

import yaml

from prepare_release import expected_artifacts, package_files, validate_sdist, validate_wheel
from packaging.utils import parse_wheel_filename


def validate_run(run, pages, repository, commit, expected_installs, require_installs=True):
    if (run.get("repository", {}).get("full_name") != repository
            or run.get("head_repository", {}).get("full_name") != repository
            or run.get("path") != ".github/workflows/publish.yml"
            or run.get("event") != "workflow_dispatch"
            or run.get("head_branch") != "main"):
        raise ValueError("Promotion source must be this repository's manual publication on main")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("TestPyPI run must have completed successfully")
    if run.get("head_sha") != commit:
        raise ValueError("TestPyPI run must test this exact main commit; run TestPyPI again for changed sources")
    jobs = [job for page in pages for job in page["jobs"]]
    uploads = [j for j in jobs if j["name"] == "Upload to TestPyPI"]
    rechecks = [j for j in jobs if j["name"] == "Verify existing TestPyPI files"]
    uploaded = len(uploads) == 1 and uploads[0].get("conclusion") == "success"
    rechecked = not uploads and len(rechecks) == 1 and rechecks[0].get("conclusion") == "success"
    if not uploaded and not rechecked:
        raise ValueError("Source run must contain a successful TestPyPI upload, not a PyPI promotion")
    installs = [j for j in jobs if j["name"].startswith("TestPyPI install /")]
    if (require_installs or rechecked) and (len(installs) != len(expected_installs)
            or {j["name"] for j in installs} != set(expected_installs)
            or any(j.get("conclusion") != "success" for j in installs)):
        raise ValueError("Every expected TestPyPI index installation must succeed before promotion")
    return uploaded


# These files control verification/publishing, not the package's runtime/build
# inputs. Repairs here can verify existing immutable releases without re-upload.
RELEASE_ONLY_FILES = frozenset({
    ".github/workflows/publish.yml", "scripts/check_promotion.py",
    "scripts/check_testpypi.py", "scripts/ci-preflight.sh",
    "tests/test_release.py", "docs/PUBLISHING.md",
})


def validate_source(root, tested_commit, current_commit):
    for commit in (tested_commit, current_commit):
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Expected a complete Git commit SHA")
    if tested_commit == current_commit:
        return
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", tested_commit, current_commit], cwd=root)
    if ancestor.returncode:
        raise ValueError("Tested package commit must be an ancestor of this main commit")
    changed = subprocess.check_output(["git", "diff", "--name-only", "-z", tested_commit, current_commit], cwd=root)
    paths = {p.decode("utf8", errors="surrogateescape") for p in changed.split(b"\0") if p}
    unexpected = paths - RELEASE_ONLY_FILES
    if unexpected:
        raise ValueError("Package inputs changed since TestPyPI: " + ", ".join(sorted(unexpected)))


def validate_files(root, directory, manifest, commit, run_id):
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    version = tomllib.loads((root / "Cargo.toml").read_text())["package"]["version"]
    if (manifest.get("name") != "figgyplot" or manifest.get("version") != version
            or manifest.get("commit") != commit or str(manifest.get("run_id")) != str(run_id)):
        raise ValueError("Release manifest must match this version, commit and successful TestPyPI run")
    paths = list(directory.iterdir())
    if any(not p.is_file() for p in paths) or {p.name for p in paths} != set(manifest["files"]):
        raise ValueError("Promotion files differ from the complete release manifest")
    expected = set(expected_artifacts(root).values())
    if len(paths) != len(expected) + 1:
        raise ValueError("Promotion must include every configured wheel and one sdist")
    source_files = package_files(root)
    seen = set()
    sdists = 0
    for path in paths:
        record = manifest["files"][path.name]
        if path.stat().st_size != record["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Promotion file differs from TestPyPI build SHA-256: " + path.name)
        if path.name.endswith(".whl"):
            tags = parse_wheel_filename(path.name)[3]
            matches = {(t.interpreter, t.abi, t.platform) for t in tags} & expected
            if len(matches) != 1 or matches & seen:
                raise ValueError("Duplicate or unexpected promotion wheel platform/ABI")
            expected_tag = next(iter(matches))
            validate_wheel(path, expected_tag, version, project["requires-python"], source_files)
            seen.add(expected_tag)
        else:
            validate_sdist(path, version, project["requires-python"], source_files)
            sdists += 1
    if seen != expected or sdists != 1:
        raise ValueError("Incomplete promotion wheel/sdist coverage")


if __name__ == "__main__":
    if len(sys.argv) not in (6, 7):
        raise SystemExit("Usage: check_promotion.py RUN.json JOB_PAGES.json FILES MANIFEST.json TEST_RUN_ID [pypi|verify-testpypi]")
    root = Path(__file__).resolve().parents[1]
    run = json.loads(Path(sys.argv[1]).read_text())
    pages = json.loads(Path(sys.argv[2]).read_text())
    run_id = sys.argv[5]
    mode = sys.argv[6] if len(sys.argv) == 7 else "pypi"
    if mode not in ("pypi", "verify-testpypi"):
        raise ValueError("Expected pypi or verify-testpypi")
    if str(run.get("id")) != run_id:
        raise ValueError("Fetched run ID differs from requested TestPyPI source")
    workflow = yaml.load((root / ".github/workflows/publish.yml").read_text(), Loader=yaml.BaseLoader)
    matrix = workflow["jobs"]["install"]["strategy"]["matrix"]["include"]
    expected_installs = {"TestPyPI install / %s / Python %s" % (row["runner"], row["python"]) for row in matrix}
    # The selected run's identity is checked separately from the original
    # package commit: release-only repairs may have a newer workflow SHA.
    uploaded = validate_run(run, pages, os.environ["GITHUB_REPOSITORY"], run["head_sha"], expected_installs,
                            require_installs=mode == "pypi")
    manifest = json.loads(Path(sys.argv[4]).read_text())
    if uploaded:
        if manifest.get("commit") != run["head_sha"] or str(manifest.get("run_id")) != run_id:
            raise ValueError("Original upload must match its build commit and run ID")
    elif str(manifest.get("verified_run_id")) != run_id:
        raise ValueError("Recheck manifest must identify this successful verification run")
    validate_source(root, run["head_sha"], os.environ["GITHUB_SHA"])
    validate_source(root, manifest["commit"], os.environ["GITHUB_SHA"])
    validate_files(root, Path(sys.argv[3]), manifest, manifest["commit"], manifest["run_id"])
    if mode == "verify-testpypi":
        # Keep the original build commit, run ID and file hashes unchanged.
        # Production requires this recheck run to complete all nine installs.
        manifest["verified_run_id"] = os.environ["GITHUB_RUN_ID"]
        Path(sys.argv[4]).write_text(json.dumps(manifest, indent=2) + "\n")
        print("Verified existing TestPyPI files; index installation checks must now run")
    else:
        print("Verified successful TestPyPI run, nine index installs and all 75 immutable distribution files")
