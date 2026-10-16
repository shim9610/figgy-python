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


if __name__ == "__main__":
    assets = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "python/figgyplot/assets"
    check_assets(assets)
    check_renderer_revision(Path(__file__).resolve().parents[1])
    print("Upstream JS/WASM asset hashes and sizes passed: %s" % assets)
