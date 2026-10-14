"""Release integrity regressions without a GPU, upload token or network."""
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import runpy
import subprocess
import tarfile
from types import SimpleNamespace
import zipfile

import pytest

pytest.importorskip("tomllib", reason="Release tooling runs on Python 3.12")
pytest.importorskip("yaml")
pytest.importorskip("packaging")
ROOT = Path(__file__).resolve().parents[1]
release = runpy.run_path(str(ROOT / "scripts/prepare_release.py"))
download = runpy.run_path(str(ROOT / "scripts/check_testpypi.py"))
with pytest.MonkeyPatch.context() as imports:
    imports.syspath_prepend(str(ROOT / "scripts"))
    promotion = runpy.run_path(str(ROOT / "scripts/check_promotion.py"))


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname="figgyplot"\nversion="0.2.0"\nrequires-python=">=3.8,<3.16"\n')
    (root / "Cargo.toml").write_text('[package]\nname="figgyplot"\nversion="0.2.0"\n')
    workflow = root / ".github/workflows/wheels.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text('jobs:\n  wheels:\n    strategy:\n      matrix:\n        platform: [linux-x86_64, windows-arm64]\n        python: ["3.12", "3.14t"]\n        exclude: []\n')
    assets = root / "python/figgyplot/assets"
    assets.mkdir(parents=True)
    wasm = b"\x00asm-test-fixture"
    (assets / "figgy_bg.wasm").write_bytes(wasm)
    (assets / "provenance.json").write_text(json.dumps({"assets": {"figgy_bg.wasm": {
        "sha256": hashlib.sha256(wasm).hexdigest(), "bytes": len(wasm)}}}))
    (assets.parent / "webgpu.js").write_bytes(b"export const test = true;\n")
    files = release["package_files"](root)
    artifacts = tmp_path / "artifacts"
    for artifact, (interpreter, abi, platform) in release["expected_artifacts"](root).items():
        folder = artifacts / artifact
        folder.mkdir(parents=True)
        path = folder / ("figgyplot-0.2.0-%s-%s-%s.whl" % (interpreter, abi, platform))
        with zipfile.ZipFile(path, "w") as wheel:
            wheel.writestr("figgyplot-0.2.0.dist-info/METADATA", b"Metadata-Version: 2.4\nName: figgyplot\nVersion: 0.2.0\nRequires-Python: >=3.8,<3.16\n")
            wheel.writestr("figgyplot-0.2.0.dist-info/WHEEL", "Wheel-Version: 1.0\nTag: %s-%s-%s\n" % (interpreter, abi, platform))
            wheel.writestr("figgyplot/_native.so", b"synthetic test extension")
            for name, data in files.items():
                wheel.writestr("figgyplot/" + name, data)
    sdist = artifacts / "figgyplot-sdist/figgyplot-0.2.0.tar.gz"
    sdist.parent.mkdir()
    with tarfile.open(sdist, "w:gz") as archive:
        members = {"PKG-INFO": b"Name: figgyplot\nVersion: 0.2.0\nRequires-Python: >=3.8,<3.16\n",
                   **{p: b"source" for p in ("Cargo.toml", "Cargo.lock", "pyproject.toml", "src/lib.rs")},
                   **{"python/figgyplot/" + name: data for name, data in files.items()}}
        for name, data in members.items():
            member = tarfile.TarInfo("figgyplot-0.2.0/" + name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return root, artifacts, tmp_path / "dist", tmp_path / "manifest.json"


def change_wheel(path, member, value):
    with zipfile.ZipFile(path) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    contents[member] = value
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in contents.items():
            archive.writestr(name, data)


def test_real_matrix_requires_all_74_wheels():
    assert len(release["expected_artifacts"](ROOT)) == 74


def test_complete_release_manifest_contains_exact_bytes(inputs, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    manifest = release["prepare"](*inputs)
    assert manifest["commit"] == "a" * 40
    assert len(manifest["files"]) == 5
    for name, record in manifest["files"].items():
        data = (inputs[2] / name).read_bytes()
        assert record == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_maturin_can_reorder_python_specifiers():
    release["validate_metadata"](b"Name: figgyplot\nVersion: 0.2.0\nRequires-Python: <3.16,>=3.8\n", "0.2.0", ">=3.8,<3.16")


def test_missing_wheel_stops_before_staging(inputs):
    path = next(inputs[1].glob("wheels-*/*.whl"))
    path.unlink()
    path.parent.rmdir()
    with pytest.raises(ValueError, match="Incomplete"):
        release["prepare"](*inputs)
    assert not inputs[2].exists()


def test_duplicate_distribution_in_artifact_is_rejected(inputs):
    path = next(inputs[1].glob("wheels-*/*.whl"))
    (path.parent / "another.whl").write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="exactly one"):
        release["prepare"](*inputs)


@pytest.mark.parametrize("member,data,message", [
    ("figgyplot/assets/figgy_bg.wasm", b"broken", "differs from source"),
    ("figgyplot/webgpu.js", b"broken", "differs from source"),
    ("figgyplot-0.2.0.dist-info/METADATA", b"Name: figgyplot\nVersion: 0.1.0\n", "name/version"),
    ("figgyplot-0.2.0.dist-info/WHEEL", b"Tag: cp312-cp312-win_amd64\n", "tags differ"),
])
def test_corrupt_or_mixed_wheel_stops_before_staging(inputs, member, data, message):
    change_wheel(next(inputs[1].glob("wheels-linux-*-py3.12/*.whl")), member, data)
    with pytest.raises(ValueError, match=message):
        release["prepare"](*inputs)
    assert not inputs[2].exists()


def test_wrong_platform_or_abi_in_artifact_is_rejected(inputs):
    path = next(inputs[1].glob("wheels-linux-*-py3.14t/*.whl"))
    path.rename(path.with_name(path.name.replace("cp314t", "cp314")))
    with pytest.raises(ValueError, match="platform/ABI"):
        release["prepare"](*inputs)


def test_sdist_and_wheel_assets_must_match_same_source(inputs):
    root, artifacts, _, _ = inputs
    sdist = next(artifacts.glob("figgyplot-sdist/*"))
    files = release["package_files"](root)
    files["webgpu.js"] = b"wrong source version"
    with pytest.raises(ValueError, match="sdist file differs"):
        release["validate_sdist"](sdist, "0.2.0", ">=3.8,<3.16", files)


def test_index_download_must_match_release_hash(inputs, monkeypatch):
    manifest = release["prepare"](*inputs)
    wheel = next(inputs[2].glob("*cp312*manylinux*.whl"))
    tag = next(iter(release["parse_wheel_filename"](wheel.name)[3]))
    monkeypatch.setitem(download["verify_download"].__globals__, "sys_tags", lambda: iter([tag]))
    download["verify_download"](wheel, manifest, "0.2.0")
    wheel.write_bytes(wheel.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        download["verify_download"](wheel, manifest, "0.2.0")


def test_index_download_cannot_use_another_build(inputs, monkeypatch):
    manifest = release["prepare"](*inputs)
    wheel = next(inputs[2].glob("*.whl"))
    del manifest["files"][wheel.name]
    with pytest.raises(ValueError, match="absent from this build"):
        download["verify_download"](wheel, manifest, "0.2.0")
    with pytest.raises(ValueError, match="requested release"):
        download["verify_download"](wheel, manifest, "0.3.0")


@pytest.mark.parametrize("target", ["testpypi", "pypi"])
@pytest.mark.parametrize("corrupt", [None, "download", "installed"])
def test_download_uses_isolated_index_and_rejects_bad_bytes(inputs, monkeypatch, corrupt, target):
    manifest = release["prepare"](*inputs)
    wheel = next(inputs[2].glob("*cp312*manylinux*.whl"))
    tag = next(iter(release["parse_wheel_filename"](wheel.name)[3]))
    monkeypatch.setitem(download["main"].__globals__, "sys_tags", lambda: iter([tag]))
    monkeypatch.setattr(download["main"].__globals__["sys"], "argv", ["check_testpypi.py", str(inputs[3]), "0.2.0", target])
    installed = inputs[2] / "installed"
    monkeypatch.setattr(importlib.metadata, "distribution", lambda name: SimpleNamespace(locate_file=lambda path: installed / path))
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "download" in command:
            assert "--isolated" in command and "--no-deps" in command
            assert "--only-binary=:all:" in command and "--no-cache-dir" in command
            assert "--extra-index-url" not in command
            assert command[command.index("--index-url") + 1] == download["INDEXES"][target]
            # Simulate index propagation: two download errors, then one wheel.
            if len(calls) < 3:
                return subprocess.CompletedProcess(command, 1)
            destination = Path(command[command.index("--dest") + 1]) / wheel.name
            destination.write_bytes(wheel.read_bytes() + (b"changed" if corrupt == "download" else b""))
        else:
            assert "install" in command and "--no-deps" in command
            assert command[command.index("--index-url") + 1] == download["INDEXES"][target]
            assert "--only-binary=:all:" in command and "figgyplot==0.2.0" in command
            with zipfile.ZipFile(wheel) as archive:
                archive.extractall(installed)
            if corrupt == "installed":
                (installed / "figgyplot/_native.so").write_bytes(b"another build")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(download["main"].__globals__["subprocess"], "run", run)
    monkeypatch.setattr(download["main"].__globals__["time"], "sleep", lambda seconds: None)
    if corrupt:
        with pytest.raises(ValueError, match="SHA-256" if corrupt == "download" else "Installed package differs"):
            download["main"]()
        assert len(calls) == (3 if corrupt == "download" else 4)
    else:
        download["main"]()
        assert len(calls) == 4


@pytest.fixture
def successful_run():
    installs = {"TestPyPI install / platform-%d / Python 3.12" % i for i in range(9)}
    run = {"repository": {"full_name": "shim9610/figgy-python"},
           "head_repository": {"full_name": "shim9610/figgy-python"},
           "path": ".github/workflows/publish.yml", "event": "workflow_dispatch",
           "head_branch": "main", "head_sha": "a" * 40,
           "status": "completed", "conclusion": "success"}
    pages = [{"jobs": [{"name": "Upload to TestPyPI", "conclusion": "success"}]},
             {"jobs": [{"name": name, "conclusion": "success"} for name in sorted(installs)]}]
    return run, pages, "shim9610/figgy-python", "a" * 40, installs


def test_successful_testpypi_run_can_be_promoted(successful_run):
    promotion["validate_run"](*successful_run)


def test_uploaded_release_with_skipped_installs_can_only_enter_recheck(successful_run):
    successful_run[1][1]["jobs"] = []
    assert promotion["validate_run"](*successful_run, require_installs=False)
    with pytest.raises(ValueError, match="installation must succeed"):
        promotion["validate_run"](*successful_run)


def test_completed_recheck_can_be_promoted(successful_run):
    successful_run[1][0]["jobs"][0]["name"] = "Verify existing TestPyPI files"
    assert promotion["validate_run"](*successful_run) is False


def test_recheck_with_skipped_installs_is_not_trusted(successful_run):
    successful_run[1][0]["jobs"][0]["name"] = "Verify existing TestPyPI files"
    successful_run[1][1]["jobs"] = []
    with pytest.raises(ValueError, match="installation must succeed"):
        promotion["validate_run"](*successful_run, require_installs=False)


@pytest.fixture
def package_git(tmp_path):
    paths = [".github/workflows/publish.yml", ".github/workflows/wheels.yml",
             "scripts/check_testpypi.py", "docs/PUBLISHING.md", "src/lib.rs",
             "python/figgyplot/figure.py", "Cargo.toml", "Cargo.lock", "pyproject.toml",
             "PYPI_README.md", ".gitattributes"]
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original\n")

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Release test")
    git("config", "user.email", "release-test@example.invalid")
    git("add", ".")
    git("commit", "-qm", "original package")
    return tmp_path, git, git("rev-parse", "HEAD")


@pytest.mark.parametrize("name", [".github/workflows/publish.yml", "scripts/check_testpypi.py", "docs/PUBLISHING.md"])
def test_release_only_repairs_can_reuse_existing_package(package_git, name):
    root, git, original = package_git
    (root / name).write_text("fixed verification\n")
    git("add", "."); git("commit", "-qm", "release repair")
    promotion["validate_source"](root, original, git("rev-parse", "HEAD"))


@pytest.mark.parametrize("name", ["src/lib.rs", "python/figgyplot/figure.py", "Cargo.toml", "Cargo.lock",
                                  "pyproject.toml", "PYPI_README.md", ".gitattributes", ".github/workflows/wheels.yml"])
def test_package_or_build_changes_cannot_reuse_tested_release(package_git, name):
    root, git, original = package_git
    (root / name).write_text("changed package input\n")
    git("add", "."); git("commit", "-qm", "package changed")
    with pytest.raises(ValueError, match="Package inputs changed"):
        promotion["validate_source"](root, original, git("rev-parse", "HEAD"))


def test_unrelated_history_cannot_reuse_tested_release(package_git):
    root, git, original = package_git
    git("checkout", "--orphan", "another-history")
    git("commit", "-qm", "different history")
    with pytest.raises(ValueError, match="must be an ancestor"):
        promotion["validate_source"](root, original, git("rev-parse", "HEAD"))


@pytest.mark.parametrize("field,value,message", [
    ("head_sha", "b" * 40, "exact main commit"),
    ("head_branch", "unreviewed", "manual publication on main"),
    ("event", "pull_request", "manual publication on main"),
    ("path", ".github/workflows/pr-tests.yml", "manual publication on main"),
    ("conclusion", "failure", "completed successfully"),
    ("status", "in_progress", "completed successfully"),
    ("head_repository", {"full_name": "someone/figgy-python"}, "manual publication on main"),
])
def test_wrong_source_cannot_be_promoted(successful_run, field, value, message):
    successful_run[0][field] = value
    with pytest.raises(ValueError, match=message):
        promotion["validate_run"](*successful_run)


@pytest.mark.parametrize("change", ["failed", "missing", "wrong-platform", "production-run"])
def test_every_real_test_index_install_is_required(successful_run, change):
    _, pages, _, _, _ = successful_run
    if change == "failed": pages[1]["jobs"][0]["conclusion"] = "failure"
    if change == "missing": pages[1]["jobs"].pop()
    if change == "wrong-platform": pages[1]["jobs"][0]["name"] = "TestPyPI install / unexpected / Python 3.12"
    if change == "production-run": pages[0]["jobs"][0]["name"] = "Upload to PyPI"
    with pytest.raises(ValueError, match="installation must succeed|successful TestPyPI upload"):
        promotion["validate_run"](*successful_run)


def test_promotion_uses_exact_verified_files(inputs, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    manifest = release["prepare"](*inputs)
    promotion["validate_files"](inputs[0], inputs[2], manifest, "a" * 40, "123")
    wheel = next(inputs[2].glob("*.whl"))
    wheel.write_bytes(wheel.read_bytes() + b"rebuilt")
    with pytest.raises(ValueError, match="TestPyPI build SHA-256"):
        promotion["validate_files"](inputs[0], inputs[2], manifest, "a" * 40, "123")


@pytest.mark.parametrize("field,value", [("version", "0.3.0"), ("commit", "b" * 40), ("run_id", "456")])
def test_promotion_manifest_must_match_source(inputs, monkeypatch, field, value):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    manifest = release["prepare"](*inputs)
    manifest[field] = value
    with pytest.raises(ValueError, match="manifest must match"):
        promotion["validate_files"](inputs[0], inputs[2], manifest, "a" * 40, "123")
