"""Keep content-addressed web assets intact through Windows-style checkout."""
from pathlib import Path
import runpy
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "python/figgyplot/assets"
check_assets = runpy.run_path(str(ROOT / "scripts/check_assets.py"))["check_assets"]


def test_source_asset_provenance():
    check_assets(ASSETS)


def test_runtime_asset_check_does_not_require_tomllib(monkeypatch):
    import builtins
    original = builtins.__import__

    def without_tomllib(name, *args, **kwargs):
        if name == "tomllib":
            raise ImportError("tomllib is unavailable on Python 3.8")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_tomllib)
    runtime_check = runpy.run_path(str(ROOT / "scripts/check_assets.py"))["check_assets"]
    runtime_check(ASSETS)


def test_crlf_changes_are_rejected_with_asset_diagnostics(tmp_path):
    shutil.copytree(ASSETS, tmp_path / "assets")
    js = tmp_path / "assets/figgy.js"
    js.write_bytes(js.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match=r"figgy\.js: expected sha256=.*actual sha256=.*CRLF"):
        check_assets(tmp_path / "assets")


@pytest.mark.parametrize("with_attributes", [False, True])
def test_git_autocrlf_checkout_preserves_manifest_bytes(tmp_path, with_attributes):
    def git(*args, **kwargs):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)

    git("init", "-q")
    git("config", "core.autocrlf", "true")
    git("config", "core.safecrlf", "false")
    files = {"python/figgyplot/assets/" + p.name: p.read_bytes() for p in ASSETS.iterdir() if p.is_file()}
    sources = [ROOT / "python/figgyplot/__init__.py", ROOT / "python/figgyplot/webgpu.js"]
    files.update({p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sources})
    if with_attributes:
        files[".gitattributes"] = (ROOT / ".gitattributes").read_bytes()
    # Feed raw blobs into the index to preserve the repository's LF bytes;
    # checkout-index then applies the same autocrlf rules as a Windows clone.
    for name, data in files.items():
        blob = git("hash-object", "-w", "--stdin", input=data).stdout.decode().strip()
        git("update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, name))
    git("checkout-index", "--all", "--force")
    checked = tmp_path / "python/figgyplot/assets"
    assert (checked / "figgy_bg.wasm").read_bytes() == (ASSETS / "figgy_bg.wasm").read_bytes()
    if with_attributes:
        check_assets(checked)
        assert (checked / "figgy.js").read_bytes() == (ASSETS / "figgy.js").read_bytes()
        for source in sources:
            assert (tmp_path / source.relative_to(ROOT)).read_bytes() == source.read_bytes()
    else:
        with pytest.raises(ValueError, match=r"figgy\.js.*CRLF"):
            check_assets(checked)


@pytest.fixture
def registry_pairing(tmp_path):
    import json
    revision = "7" * 40
    source = "registry+https://github.com/rust-lang/crates.io-index"
    packages = {
        "figgy-model": {"version": "0.11.0", "source": source, "checksum": "a" * 64,
                        "upstream_revision": revision, "path_in_vcs": "crates/model"},
        "figgy-renderer": {"version": "0.17.0", "source": source, "checksum": "b" * 64,
                           "upstream_revision": revision, "path_in_vcs": "crates/renderer"},
    }
    (tmp_path / "Cargo.toml").write_text(
        '[dependencies]\nrenderer = { package = "figgy-renderer", version = "=0.17.0" }\n')
    lock = "version = 4\n"
    for name, package in packages.items():
        lock += '\n[[package]]\nname = "' + name + '"\n'
        lock += "".join(key + " = " + json.dumps(package[key]) + "\n" for key in ("version", "source", "checksum"))
    (tmp_path / "Cargo.lock").write_text(lock)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/build-wasm.sh").write_text("revision=" + revision + "\n")
    shutil.copyfile(ROOT / "scripts/wasm-host.patch", tmp_path / "scripts/wasm-host.patch")
    patch = runpy.run_path(str(ROOT / "scripts/check_assets.py"))["host_patch_record"](tmp_path)
    assets = tmp_path / "python/figgyplot/assets"
    assets.mkdir(parents=True)
    (assets / "provenance.json").write_text(json.dumps({
        "upstream_revision": revision, "renderer_version": "0.17.0", "native_packages": packages,
        "wasm_host_patch": patch}))
    return tmp_path


def check_pairing(root):
    runpy.run_path(str(ROOT / "scripts/check_assets.py"))["check_renderer_revision"](root)


def test_host_patch_check_does_not_depend_on_callers_git_subdirectory(registry_pairing, monkeypatch):
    monkeypatch.chdir(ROOT / "scripts")
    check_pairing(registry_pairing)


def test_host_patch_inside_another_checkout(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    nested = tmp_path / "ci-results" / "fixture"
    (nested / "scripts").mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/wasm-host.patch", nested / "scripts/wasm-host.patch")
    checker = runpy.run_path(str(ROOT / "scripts/check_assets.py"))["host_patch_record"]
    assert checker(nested) == checker(ROOT)


@pytest.mark.parametrize("change", ["bytes", "missing", "hash", "path", "files"])
def test_host_patch_must_match_built_asset_provenance(registry_pairing, change):
    import json
    check_pairing(registry_pairing)
    path = registry_pairing / "python/figgyplot/assets/provenance.json"
    provenance = json.loads(path.read_text())
    if change == "bytes":
        patch = registry_pairing / "scripts/wasm-host.patch"
        patch.write_text(patch.read_text().replace("Observe completion", "Await completion"))
    elif change == "missing":
        del provenance["wasm_host_patch"]
    elif change == "hash":
        provenance["wasm_host_patch"]["sha256"] = "0" * 64
    elif change == "path":
        provenance["wasm_host_patch"]["path"] = "scripts/another.patch"
    else:
        provenance["wasm_host_patch"]["files"] = ["crates/renderer/src/lib.rs"]
    path.write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="host patch.*provenance"):
        check_pairing(registry_pairing)


@pytest.mark.parametrize("change", ["renderer", "model", "manifest", "mode", "crlf", "deletion", "invalid"])
def test_host_patch_cannot_change_native_sources_or_build_configuration(registry_pairing, change):
    patch = registry_pairing / "scripts/wasm-host.patch"
    data = patch.read_text()
    if change in ("renderer", "model", "manifest"):
        destination = "Cargo.toml" if change == "manifest" else "crates/" + change + "/src/lib.rs"
        data = data.replace("crates/web/src/lib.rs", destination)
    elif change == "mode":
        data = data.replace("--- a/", "old mode 100644\nnew mode 100755\n--- a/", 1)
    elif change == "crlf":
        data = data.replace("\n", "\r\n")
    elif change == "deletion":
        # A syntactically valid patch that removes existing bridge code is
        # outside this deliberately additive host extension's scope.
        data = data.replace("@@ -5756,6 +5756,20 @@", "@@ -5756,6 +5756,19 @@")
        data = data.replace("             Ok(())\n", "-            Ok(())\n", 1)
    else:
        data = "not a patch\n"
    patch.write_bytes(data.encode())
    checker = runpy.run_path(str(ROOT / "scripts/check_assets.py"))["host_patch_record"]
    with pytest.raises(ValueError, match="host patch"):
        checker(registry_pairing)


@pytest.mark.parametrize("package", ["figgy-model", "figgy-renderer"])
@pytest.mark.parametrize("field,value", [
    ("checksum", "c" * 64), ("version", "9.0.0"),
    ("source", "git+https://github.com/shim9610/figgy#" + "7" * 40),
])
def test_registry_lockfile_changes_are_rejected(registry_pairing, package, field, value):
    import json
    check_pairing(registry_pairing)
    path = registry_pairing / "Cargo.lock"
    sections = path.read_text().split("[[package]]")
    for index, section in enumerate(sections):
        if 'name = "' + package + '"' in section:
            import re
            sections[index] = re.sub(r'^' + field + r' = .*$', field + " = " + json.dumps(value), section, flags=re.MULTILINE)
    path.write_text("[[package]]".join(sections))
    with pytest.raises(ValueError, match="registry|pin"):
        check_pairing(registry_pairing)


@pytest.mark.parametrize("change", ["native_revision", "wasm_revision", "script_revision", "path", "renderer_version", "missing", "duplicate"])
def test_registry_pairing_metadata_changes_are_rejected(registry_pairing, change):
    import json
    check_pairing(registry_pairing)
    path = registry_pairing / "python/figgyplot/assets/provenance.json"
    provenance = json.loads(path.read_text())
    if change == "native_revision":
        provenance["native_packages"]["figgy-model"]["upstream_revision"] = "0" * 40
    elif change == "wasm_revision":
        provenance["upstream_revision"] = "0" * 40
    elif change == "script_revision":
        (registry_pairing / "scripts/build-wasm.sh").write_text("revision=" + "0" * 40)
    elif change == "path":
        provenance["native_packages"]["figgy-model"]["path_in_vcs"] = "crates/renderer"
    elif change == "renderer_version":
        provenance["renderer_version"] = "9.0.0"
    elif change == "missing":
        del provenance["native_packages"]["figgy-model"]
    elif change == "duplicate":
        lock = registry_pairing / "Cargo.lock"
        lock.write_text(lock.read_text() + '\n[[package]]\nname = "figgy-model"\nversion = "0.10.0"\n')
    path.write_text(json.dumps(provenance))
    with pytest.raises(ValueError):
        check_pairing(registry_pairing)


@pytest.mark.parametrize("override", [
    '[patch.crates-io]\nfiggy-renderer = { git = "https://github.com/shim9610/figgy", rev = "' + "7" * 40 + '" }',
    '[patch.crates-io]\nmodel_alias = { package = "figgy-model", path = "../model" }',
    '[replace]\n"figgy-model:0.11.0" = { path = "../model" }',
])
def test_registry_overrides_rejected_even_with_unchanged_lock(registry_pairing, override):
    path = registry_pairing / "Cargo.toml"
    path.write_text(path.read_text() + "\n" + override)
    with pytest.raises(ValueError, match="overrides"):
        check_pairing(registry_pairing)


@pytest.mark.parametrize("extra", [', path = "../renderer"', ', git = "https://github.com/shim9610/figgy"', ', registry = "other"'])
def test_direct_nonregistry_renderer_rejected(registry_pairing, extra):
    path = registry_pairing / "Cargo.toml"
    path.write_text(path.read_text().replace('version = "=0.17.0"', 'version = "=0.17.0"' + extra))
    with pytest.raises(ValueError, match="exactly pin"):
        check_pairing(registry_pairing)


@pytest.fixture
def archive_checker(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return runpy.run_path(str(ROOT / "scripts/record_registry_provenance.py"))


@pytest.mark.parametrize("staged", [False, True])
def test_dirty_wasm_checkout_is_rejected_before_download(tmp_path, archive_checker, monkeypatch, staged):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    git("init", "-q")
    git("config", "user.name", "Provenance regression")
    git("config", "user.email", "provenance-test@example.invalid")
    source = tmp_path / "source.rs"
    source.write_text("// original\n")
    git("add", ".")
    git("commit", "-qm", "Source revision")
    revision = git("rev-parse", "HEAD").stdout.strip()
    source.write_text("// locally patched\n")
    if staged:
        git("add", ".")
    verify = archive_checker["verify_registry_sources"]

    def no_network(*args, **kwargs):
        pytest.fail("Dirty source must be rejected before downloading archives")

    monkeypatch.setitem(verify.__globals__, "urlopen", no_network)
    with pytest.raises(subprocess.CalledProcessError):
        verify(tmp_path, tmp_path, revision)


@pytest.mark.parametrize("change", [None, "checksum", "revision", "dirty", "path", "manifest", "source", "inventory"])
def test_published_archive_matches_exact_wasm_source(tmp_path, archive_checker, change):
    import hashlib
    import io
    import json
    import tarfile
    revision = "7" * 40
    source = tmp_path / "crates/model"
    (source / "src").mkdir(parents=True)
    manifest = b'[package]\nname = "figgy-model"\nversion = "0.11.0"\n'
    (source / "Cargo.toml").write_bytes(manifest)
    (source / "src/lib.rs").write_bytes(b"pub fn identity() {}\n")
    vcs = {"git": {"sha1": revision}, "path_in_vcs": "crates/model"}
    if change == "revision": vcs["git"]["sha1"] = "0" * 40
    if change == "dirty": vcs["git"]["dirty"] = True
    if change == "path": vcs["path_in_vcs"] = "crates/renderer"
    files = {".cargo_vcs_info.json": json.dumps(vcs).encode(), "Cargo.toml.orig": manifest,
             "src/lib.rs": (source / "src/lib.rs").read_bytes()}
    if change == "manifest": files["Cargo.toml.orig"] += b"# different\n"
    if change == "source": files["src/lib.rs"] += b"// different\n"
    if change == "inventory": files["src/extra.rs"] = b""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, contents in files.items():
            entry = tarfile.TarInfo("figgy-model-0.11.0/" + name)
            entry.size = len(contents)
            archive.addfile(entry, io.BytesIO(contents))
    data = output.getvalue()
    package = {"version": "0.11.0", "source": "registry+https://github.com/rust-lang/crates.io-index",
               "checksum": hashlib.sha256(data).hexdigest()}
    if change == "checksum": package["checksum"] = "0" * 64
    verify = archive_checker["verify_archive"]
    if change is None:
        record = verify(data, "figgy-model", package, tmp_path, revision)
        assert record["upstream_revision"] == revision
        assert record["checksum"] == package["checksum"]
    else:
        with pytest.raises(ValueError):
            verify(data, "figgy-model", package, tmp_path, revision)
