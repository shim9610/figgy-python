"""Release integrity regressions without a GPU, upload token or network."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import tarfile
import zipfile

import pytest

pytest.importorskip("tomllib", reason="Release tooling runs on Python 3.12")
pytest.importorskip("yaml")
pytest.importorskip("packaging")
ROOT = Path(__file__).resolve().parents[1]
release = runpy.run_path(str(ROOT / "scripts/prepare_release.py"))
download = runpy.run_path(str(ROOT / "scripts/check_testpypi.py"))


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


@pytest.mark.parametrize("corrupt", [False, True])
def test_download_uses_isolated_test_index_and_never_installs_bad_bytes(inputs, monkeypatch, corrupt):
    manifest = release["prepare"](*inputs)
    wheel = next(inputs[2].glob("*cp312*manylinux*.whl"))
    tag = next(iter(release["parse_wheel_filename"](wheel.name)[3]))
    monkeypatch.setitem(download["main"].__globals__, "sys_tags", lambda: iter([tag]))
    monkeypatch.setattr(download["main"].__globals__["sys"], "argv", ["check_testpypi.py", str(inputs[3]), "0.2.0"])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "download" in command:
            assert "--isolated" in command and "--no-deps" in command
            assert "--only-binary=:all:" in command and "--no-cache-dir" in command
            assert "--extra-index-url" not in command
            assert command[command.index("--index-url") + 1] == "https://test.pypi.org/simple/"
            # Simulate index propagation: two download errors, then one wheel.
            if len(calls) < 3:
                return subprocess.CompletedProcess(command, 1)
            destination = Path(command[command.index("--dest") + 1]) / wheel.name
            destination.write_bytes(wheel.read_bytes() + (b"changed" if corrupt else b""))
        else:
            assert "install" in command and "--no-deps" in command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(download["main"].__globals__["subprocess"], "run", run)
    monkeypatch.setattr(download["main"].__globals__["time"], "sleep", lambda seconds: None)
    if corrupt:
        with pytest.raises(ValueError, match="SHA-256"):
            download["main"]()
        assert len(calls) == 3
    else:
        download["main"]()
        assert len(calls) == 4
