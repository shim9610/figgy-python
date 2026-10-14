"""Validate this run's complete distribution set before giving it to the publisher.

Release tooling runs on Python 3.12; runtime installation checks support 3.8+.
Never merges unchecked artifacts or repairs/relabels a wheel.
"""
import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tomllib
import zipfile

from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename
from packaging.tags import parse_tag
from packaging.version import Version
from packaging.specifiers import SpecifierSet
import yaml


PLATFORMS = {
    "linux-x86_64": "manylinux_2_28_x86_64",
    "linux-arm64": "manylinux_2_28_aarch64",
    "linux-musl-x86_64": "musllinux_1_2_x86_64",
    "linux-musl-arm64": "musllinux_1_2_aarch64",
    "windows-x86_64": "win_amd64",
    "windows-arm64": "win_arm64",
    "macos-x86_64": "macosx_10_15_x86_64",
    "macos-arm64": "macosx_11_0_arm64",
}


def expected_artifacts(root):
    workflow = yaml.load((root / ".github/workflows/wheels.yml").read_text(), Loader=yaml.BaseLoader)
    matrix = workflow["jobs"]["wheels"]["strategy"]["matrix"]
    expected = {}
    for platform in matrix["platform"]:
        for python in matrix["python"]:
            if any(e["platform"] == platform and e["python"] == python for e in matrix["exclude"]):
                continue
            interpreter = "cp" + python.rstrip("t").replace(".", "")
            abi = interpreter + ("t" if python.endswith("t") else "")
            expected["wheels-%s-py%s" % (platform, python)] = (interpreter, abi, PLATFORMS[platform])
    return expected


def package_files(root):
    package = root / "python/figgyplot"
    files = {p.relative_to(package).as_posix(): p.read_bytes()
             for p in package.rglob("*") if p.is_file()
             and p.suffix in {".py", ".js", ".css", ".wasm", ".json", ".txt"}
             and "__pycache__" not in p.parts}
    provenance = json.loads(files["assets/provenance.json"])
    for name, record in provenance["assets"].items():
        data = files["assets/" + name]
        if hashlib.sha256(data).hexdigest() != record["sha256"] or len(data) != record["bytes"]:
            raise ValueError("Source asset integrity failed: " + name)
    return files


def validate_metadata(data, version, requires_python):
    metadata = BytesParser().parsebytes(data)
    if metadata["Name"] != "figgyplot" or metadata["Version"] != version:
        raise ValueError("Distribution metadata name/version differs from the source")
    if metadata["Requires-Python"] is None or SpecifierSet(metadata["Requires-Python"]) != SpecifierSet(requires_python):
        raise ValueError("Distribution Requires-Python differs from the source")


def validate_wheel(path, expected, version, requires_python, files):
    name, wheel_version, build, tags = parse_wheel_filename(path.name)
    if name != canonicalize_name("figgyplot") or wheel_version != Version(version) or build:
        raise ValueError("Unexpected wheel name/version/build: " + path.name)
    if not any((t.interpreter, t.abi, t.platform) == expected for t in tags):
        raise ValueError("Wheel platform/ABI differs from artifact: " + path.name)
    # Extra tags must not claim compatibility with another interpreter/ABI.
    if any((t.interpreter, t.abi) != expected[:2] for t in tags):
        raise ValueError("Wheel advertises unexpected interpreter/ABI: " + path.name)
    with zipfile.ZipFile(path) as wheel:
        names = wheel.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate paths in wheel: " + path.name)
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Expected one wheel metadata record")
        validate_metadata(wheel.read(metadata[0]), version, requires_python)
        wheel_info = BytesParser().parsebytes(wheel.read(metadata[0].replace("METADATA", "WHEEL")))
        recorded_tags = set()
        for tag in wheel_info.get_all("Tag", []):
            recorded_tags.update(parse_tag(tag))
        if recorded_tags != tags:
            raise ValueError("Wheel filename tags differ from WHEEL metadata")
        if not any(n.startswith("figgyplot/_native") and n.endswith((".so", ".pyd")) for n in names):
            raise ValueError("Native extension missing from wheel")
        if any(n.startswith("figgy/") for n in names):
            raise ValueError("Legacy figgy namespace must not be distributed")
        for relative, data in files.items():
            if wheel.read("figgyplot/" + relative) != data:
                raise ValueError("Packaged file differs from source: " + relative)


def validate_sdist(path, version, requires_python, files):
    name, sdist_version = parse_sdist_filename(path.name)
    if name != "figgyplot" or sdist_version != Version(version):
        raise ValueError("Unexpected sdist name/version: " + path.name)
    prefix = "figgyplot-" + version + "/"
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate paths in sdist")

        def read(relative):
            member = archive.getmember(prefix + relative)
            if not member.isfile():
                raise ValueError("Expected a regular sdist file: " + relative)
            return archive.extractfile(member).read()

        validate_metadata(read("PKG-INFO"), version, requires_python)
        for relative in ("Cargo.toml", "Cargo.lock", "pyproject.toml", "src/lib.rs"):
            read(relative)
        for relative, data in files.items():
            if read("python/figgyplot/" + relative) != data:
                raise ValueError("Packaged sdist file differs from source: " + relative)


def prepare(root, artifacts, destination, manifest_path):
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    cargo = tomllib.loads((root / "Cargo.toml").read_text())["package"]
    version = project["version"]
    if project["name"] != "figgyplot" or cargo["version"] != version:
        raise ValueError("Source package names/versions must agree")
    expected = expected_artifacts(root)
    actual = {p.name for p in artifacts.iterdir()}
    if actual != set(expected) | {"figgyplot-sdist"}:
        raise ValueError("Incomplete or unexpected release artifacts; missing=%s, extra=%s" % (
            sorted((set(expected) | {"figgyplot-sdist"}) - actual),
            sorted(actual - (set(expected) | {"figgyplot-sdist"}))))
    files = package_files(root)
    distributions = []
    for artifact in sorted(actual):
        paths = list((artifacts / artifact).iterdir())
        if len(paths) != 1 or not paths[0].is_file():
            raise ValueError("Expected exactly one distribution in " + artifact)
        path = paths[0]
        if artifact == "figgyplot-sdist":
            validate_sdist(path, version, project["requires-python"], files)
        else:
            validate_wheel(path, expected[artifact], version, project["requires-python"], files)
        distributions.append(path)
    if len({p.name for p in distributions}) != len(distributions):
        raise ValueError("Duplicate distribution filenames")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Release destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {"name": "figgyplot", "version": version,
                "commit": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID"),
                "files": {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                   "bytes": p.stat().st_size} for p in distributions}}
    for path in distributions:
        shutil.copyfile(path, destination / path.name)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    result = prepare(Path(__file__).resolve().parents[1], args.artifacts, args.destination, args.manifest)
    print("Validated %d distributions for figgyplot %s" % (len(result["files"]), result["version"]))
