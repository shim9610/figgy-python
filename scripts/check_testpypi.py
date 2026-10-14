"""Download from the selected release index, verify bytes, then test pip install.

Dependencies must already be installed from PyPI. No --extra-index-url, source
build or index fallback is allowed. Import/model/assets are checked separately.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename

INDEXES = {"testpypi": "https://test.pypi.org/simple/", "pypi": "https://pypi.org/simple/"}


def verify_download(path, manifest, version):
    if manifest["name"] != "figgyplot" or manifest["version"] != version:
        raise ValueError("Release manifest name/version differs from the requested release")
    record = manifest["files"].get(path.name)
    if record is None:
        raise ValueError("Index returned a file absent from this build: " + path.name)
    name, wheel_version, _, tags = parse_wheel_filename(path.name)
    if name != "figgyplot" or str(wheel_version) != version or not tags.intersection(sys_tags()):
        raise ValueError("Downloaded wheel does not match this interpreter/platform")
    data = path.read_bytes()
    if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("Index file differs from this build's SHA-256: " + path.name)


def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: check_testpypi.py MANIFEST.json EXACT_VERSION [testpypi|pypi]")
    manifest = json.loads(Path(sys.argv[1]).read_text())
    version = sys.argv[2]
    target = sys.argv[3] if len(sys.argv) == 4 else "testpypi"
    if target not in INDEXES:
        raise ValueError("Index must be testpypi or pypi")
    index = INDEXES[target]
    if manifest["name"] != "figgyplot" or manifest["version"] != version:
        raise ValueError("Release manifest does not match requested version")
    with tempfile.TemporaryDirectory(prefix="figgyplot-testpypi-") as directory:
        destination = Path(directory)
        for attempt in range(6):
            completed = subprocess.run([
                sys.executable, "-m", "pip", "--isolated", "download", "--no-cache-dir",
                "--only-binary=:all:", "--no-deps", "--index-url", index,
                "--dest", directory, "figgyplot==" + version,
            ])
            if completed.returncode == 0:
                break
            if attempt == 5:
                raise SystemExit("%s download failed after six attempts; inspect index/upload logs." % target)
            # Only index propagation/network errors retry; integrity failures never do.
            time.sleep(10)
        wheels = list(destination.glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("Expected exactly one downloaded binary wheel")
        verify_download(wheels[0], manifest, version)
        # Exercise the public index installation command in this fresh environment.
        subprocess.run([sys.executable, "-m", "pip", "--isolated", "install", "--no-cache-dir",
                        "--index-url", index, "--no-deps", "--only-binary=:all:",
                        "figgyplot==" + version], check=True)
        # Check the installed files against the already verified wheel, including native code.
        import importlib.metadata
        import zipfile
        installed = importlib.metadata.distribution("figgyplot")
        package_root = Path(installed.locate_file("figgyplot")).resolve()
        with zipfile.ZipFile(wheels[0]) as wheel:
            for name in wheel.namelist():
                if name.startswith("figgyplot/") and not name.endswith("/"):
                    installed_path = Path(installed.locate_file(name)).resolve()
                    try:
                        installed_path.relative_to(package_root)
                    except ValueError:
                        raise ValueError("Wheel member escapes installed package: " + name) from None
                    if installed_path.read_bytes() != wheel.read(name):
                        raise ValueError("Installed package differs from verified wheel: " + name)
        print("%s index download/install matches release SHA-256: %s" % (target, wheels[0].name))


if __name__ == "__main__":
    main()
