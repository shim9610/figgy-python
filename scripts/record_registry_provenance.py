"""Verify published Rust sources before recording browser/native provenance."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tomllib
from urllib.request import urlopen

from check_assets import NATIVE_PACKAGES, host_patch_record, native_registry_packages


def verify_archive(data, name, package, upstream, revision):
    if hashlib.sha256(data).hexdigest() != package["checksum"]:
        raise ValueError("Published archive checksum differs from Cargo.lock: " + name)
    prefix = name + "-" + package["version"] + "/"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = {}
        for member in archive.getmembers():
            if not member.isfile():
                continue
            if not member.name.startswith(prefix) or member.name in members:
                raise ValueError("Unexpected or duplicate registry archive path: " + member.name)
            members[member.name] = member

        def read(relative):
            member = members.get(prefix + relative)
            if member is None:
                raise ValueError("Missing registry source: " + relative)
            return archive.extractfile(member).read()

        vcs = json.loads(read(".cargo_vcs_info.json"))
        path = NATIVE_PACKAGES[name]
        if (vcs.get("git", {}).get("sha1") != revision
                or vcs.get("git", {}).get("dirty", False)
                or vcs.get("path_in_vcs") != path):
            raise ValueError("Published archive and WASM must use the same clean upstream revision: " + name)
        source = upstream / path
        if read("Cargo.toml.orig") != (source / "Cargo.toml").read_bytes():
            raise ValueError("Published manifest differs from WASM source: " + name)
        distributed = {entry[len(prefix):] for entry in members if entry.startswith(prefix + "src/")}
        expected = {entry.relative_to(source).as_posix() for entry in (source / "src").rglob("*") if entry.is_file()}
        if distributed != expected:
            raise ValueError("Published source inventory differs from WASM source: " + name)
        for relative in sorted(distributed):
            if read(relative) != (source / relative).read_bytes():
                raise ValueError("Published source differs from WASM checkout: " + name + "/" + relative)
    return dict(package, upstream_revision=revision, path_in_vcs=path)


def verify_registry_sources(root, upstream, revision):
    actual = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if actual != revision:
        raise ValueError("WASM checkout is not at the requested upstream revision")
    # Include staged edits; never attest a patched tree merely because HEAD matches.
    subprocess.run(["git", "-C", str(upstream), "diff", "--quiet", "HEAD", "--"], check=True)
    patch = host_patch_record(root)
    records = {}
    for name, package in native_registry_packages(root).items():
        url = "https://static.crates.io/crates/{0}/{0}-{1}.crate".format(name, package["version"])
        with urlopen(url, timeout=60) as response:
            data = response.read()
        records[name] = verify_archive(data, name, package, upstream, revision)
    web = tomllib.loads((upstream / "crates/web/Cargo.toml").read_text())
    return {
        "upstream_repository": "https://github.com/shim9610/figgy",
        "upstream_revision": revision,
        "renderer_version": records["figgy-renderer"]["version"],
        "web_package_version": web["package"]["version"],
        "native_packages": records,
        "wasm_host_patch": patch,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("revision")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    metadata = verify_registry_sources(args.root, args.upstream, args.revision)
    args.output.write_text(json.dumps(metadata, indent=2) + "\n")
