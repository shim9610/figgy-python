"""Download the release only from TestPyPI, verify its bytes, then install it.

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


def verify_download(path, manifest, version):
    if manifest["name"] != "figgyplot" or manifest["version"] != version:
        raise ValueError("Release manifest name/version differs from the requested release")
    record = manifest["files"].get(path.name)
    if record is None:
        raise ValueError("TestPyPI returned a file absent from this build: " + path.name)
    name, wheel_version, _, tags = parse_wheel_filename(path.name)
    if name != "figgyplot" or str(wheel_version) != version or not tags.intersection(sys_tags()):
        raise ValueError("Downloaded wheel does not match this interpreter/platform")
    data = path.read_bytes()
    if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("TestPyPI file differs from this build's SHA-256: " + path.name)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: check_testpypi.py MANIFEST.json EXACT_VERSION")
    manifest = json.loads(Path(sys.argv[1]).read_text())
    version = sys.argv[2]
    if manifest["name"] != "figgyplot" or manifest["version"] != version:
        raise ValueError("Release manifest does not match requested version")
    with tempfile.TemporaryDirectory(prefix="figgyplot-testpypi-") as directory:
        destination = Path(directory)
        for attempt in range(6):
            completed = subprocess.run([
                sys.executable, "-m", "pip", "--isolated", "download", "--no-cache-dir",
                "--only-binary=:all:", "--no-deps", "--index-url", "https://test.pypi.org/simple/",
                "--dest", directory, "figgyplot==" + version,
            ])
            if completed.returncode == 0:
                break
            if attempt == 5:
                raise SystemExit("TestPyPI download failed after six attempts; inspect index/upload logs.")
            # Only index propagation/network errors retry; integrity failures never do.
            time.sleep(10)
        wheels = list(destination.glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("Expected exactly one downloaded binary wheel")
        verify_download(wheels[0], manifest, version)
        subprocess.run([sys.executable, "-m", "pip", "--isolated", "install", "--no-deps", str(wheels[0])], check=True)
        print("TestPyPI download/install matches release SHA-256: " + wheels[0].name)


if __name__ == "__main__":
    main()
