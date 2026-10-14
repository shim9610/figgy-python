"""Verify successful TestPyPI provenance and immutable files before PyPI upload."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib

import yaml

from prepare_release import expected_artifacts, package_files, validate_sdist, validate_wheel
from packaging.utils import parse_wheel_filename


def validate_run(run, pages, repository, commit, expected_installs):
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
    if len(uploads) != 1 or uploads[0].get("conclusion") != "success":
        raise ValueError("Source run must contain a successful TestPyPI upload, not a PyPI promotion")
    installs = [j for j in jobs if j["name"].startswith("TestPyPI install /")]
    if (len(installs) != len(expected_installs)
            or {j["name"] for j in installs} != set(expected_installs)
            or any(j.get("conclusion") != "success" for j in installs)):
        raise ValueError("Every expected TestPyPI index installation must succeed before promotion")


def validate_files(root, directory, manifest, commit, run_id):
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    if (manifest.get("name") != "figgyplot" or manifest.get("version") != project["version"]
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
            validate_wheel(path, expected_tag, project["version"], project["requires-python"], source_files)
            seen.add(expected_tag)
        else:
            validate_sdist(path, project["version"], project["requires-python"], source_files)
            sdists += 1
    if seen != expected or sdists != 1:
        raise ValueError("Incomplete promotion wheel/sdist coverage")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        raise SystemExit("Usage: check_promotion.py RUN.json JOB_PAGES.json FILES MANIFEST.json TEST_RUN_ID")
    root = Path(__file__).resolve().parents[1]
    run = json.loads(Path(sys.argv[1]).read_text())
    pages = json.loads(Path(sys.argv[2]).read_text())
    run_id = sys.argv[5]
    if str(run.get("id")) != run_id:
        raise ValueError("Fetched run ID differs from requested TestPyPI source")
    workflow = yaml.load((root / ".github/workflows/publish.yml").read_text(), Loader=yaml.BaseLoader)
    matrix = workflow["jobs"]["install"]["strategy"]["matrix"]["include"]
    expected_installs = {"TestPyPI install / %s / Python %s" % (row["runner"], row["python"]) for row in matrix}
    validate_run(run, pages, os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"], expected_installs)
    manifest = json.loads(Path(sys.argv[4]).read_text())
    validate_files(root, Path(sys.argv[3]), manifest, os.environ["GITHUB_SHA"], run_id)
    print("Verified successful TestPyPI run, nine index installs and all 75 immutable distribution files")
