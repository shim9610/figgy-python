"""Verify the exact upstream asset bytes without importing the extension."""
import hashlib
import json
import re
from pathlib import Path
import sys


def check_assets(assets):
    assets = Path(assets)
    provenance = json.loads((assets / "provenance.json").read_text())
    for name, record in provenance["assets"].items():
        path = assets / name
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != record["sha256"] or len(data) != record["bytes"]:
            hint = " Check Git line-ending conversion (CRLF)." if name.endswith(".js") and b"\r\n" in data else ""
            raise ValueError(
                "Asset integrity failed for %s: expected sha256=%s, bytes=%s; "
                "actual sha256=%s, bytes=%s.%s"
                % (path, record["sha256"], record["bytes"], actual, len(data), hint)
            )


REGISTRY_SOURCE = "registry+https://github.com/rust-lang/crates.io-index"
NATIVE_PACKAGES = {"figgy-renderer": "crates/renderer", "figgy-model": "crates/model"}
HOST_PATCH = "scripts/wasm-host.patch"
HOST_PATCH_FILES = {"crates/web/src/lib.rs", "crates/web/src/bounded.rs"}


def host_patch_record(root):
    """Allow only additive changes to the two unpublished WASM bridge files."""
    import subprocess
    import tempfile
    path = Path(root) / HOST_PATCH
    data = path.read_bytes()
    if b"\r" in data or any(line.startswith((b"old mode ", b"new mode ", b"new file ",
            b"deleted file ", b"rename ", b"copy ", b"GIT binary patch")) for line in data.splitlines()):
        raise ValueError("WASM host patch must contain only LF text additions to existing bridge files")
    # git apply filters paths when cwd is a subdirectory of a surrounding
    # checkout (including pytest's repository-local --basetemp). Parse in an
    # isolated repository root; this also works when TMPDIR is inside a checkout.
    with tempfile.TemporaryDirectory(prefix="figgy-patch-check-") as isolated:
        subprocess.run(["git", "init", "-q", isolated], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = subprocess.run(["git", "apply", "--numstat", "-z"], cwd=isolated,
                                input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError("WASM host patch is not a valid Git patch")
    entries = [entry.split("\t", 2) for entry in result.stdout.decode().split("\0") if entry]
    if (len(entries) != len(HOST_PATCH_FILES) or any(len(entry) != 3 or not entry[0].isdigit()
            or int(entry[0]) == 0 or entry[1] != "0" for entry in entries)
            or {entry[2] for entry in entries} != HOST_PATCH_FILES):
        raise ValueError("WASM host patch may only add code to the two unpublished bridge files")
    return {"path": HOST_PATCH, "sha256": hashlib.sha256(data).hexdigest(),
            "files": sorted(HOST_PATCH_FILES)}


def native_registry_packages(root):
    # Source/release tooling uses Python 3.12. Keep this lazy: installed-wheel
    # hash checks import this module on supported Python 3.8 installations.
    import tomllib
    root = Path(root)
    cargo = tomllib.loads((root / "Cargo.toml").read_text())
    lock = tomllib.loads((root / "Cargo.lock").read_text())
    for overrides in cargo.get("patch", {}).values():
        for alias, value in overrides.items():
            if alias in NATIVE_PACKAGES or isinstance(value, dict) and value.get("package") in NATIVE_PACKAGES:
                raise ValueError("Native renderer/model registry sources must not have patch overrides")
    for name in cargo.get("replace", {}):
        if name.split(":")[0] in NATIVE_PACKAGES:
            raise ValueError("Native renderer/model registry sources must not have replace overrides")
    packages = {}
    for name in NATIVE_PACKAGES:
        matches = [entry for entry in lock["package"] if entry["name"] == name]
        if len(matches) != 1:
            raise ValueError("Expected exactly one native registry package: " + name)
        package = matches[0]
        if package.get("source") != REGISTRY_SOURCE or not re.fullmatch(r"[0-9a-f]{64}", package.get("checksum", "")):
            raise ValueError("Native registry source/checksum is invalid: " + name)
        packages[name] = {key: package[key] for key in ("version", "source", "checksum")}
    dependency = cargo.get("dependencies", {}).get("renderer", {})
    if (not isinstance(dependency, dict) or dependency.get("package") != "figgy-renderer"
            or dependency.get("version") != "=" + packages["figgy-renderer"]["version"]
            or any(key in dependency for key in ("git", "path", "registry"))):
        raise ValueError("Native renderer dependency must exactly pin its crates.io lockfile version")
    return packages


def check_renderer_revision(root):
    root = Path(root)
    provenance = json.loads((root / "python/figgyplot/assets/provenance.json").read_text())
    revision = provenance["upstream_revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("WASM upstream revision must be a full Git commit")
    records = provenance.get("native_packages", {})
    if set(records) != set(NATIVE_PACKAGES):
        raise ValueError("WASM provenance must record both native registry packages")
    for name, package in native_registry_packages(root).items():
        record = records[name]
        if any(record.get(key) != value for key, value in package.items()):
            raise ValueError("Native registry lockfile and WASM provenance differ: " + name)
        if record.get("upstream_revision") != revision or record.get("path_in_vcs") != NATIVE_PACKAGES[name]:
            raise ValueError("Native registry packages and WASM must use the same upstream revision: " + name)
    if provenance.get("renderer_version") != records["figgy-renderer"]["version"]:
        raise ValueError("WASM renderer version differs from native registry provenance")
    script = (root / "scripts/build-wasm.sh").read_text()
    found = re.search(r'^revision=([0-9a-f]+)$', script, re.MULTILINE)
    if not found or found.group(1) != revision:
        raise ValueError("WASM rebuild script and asset provenance must pin the same upstream revision")
    if provenance.get("wasm_host_patch") != host_patch_record(root):
        raise ValueError("WASM host patch and asset provenance differ; rebuild the packaged assets")


if __name__ == "__main__":
    assets = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "python/figgyplot/assets"
    check_assets(assets)
    check_renderer_revision(Path(__file__).resolve().parents[1])
    print("Upstream JS/WASM asset hashes and sizes passed: %s" % assets)
