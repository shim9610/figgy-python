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


def check_renderer_revision(root):
    root = Path(root)
    revision = json.loads((root / "python/figgyplot/assets/provenance.json").read_text())["upstream_revision"]
    cargo = (root / "Cargo.toml").read_text()
    for package in ("figgy-renderer", "figgy-model"):
        found = re.search(r'^' + package + r'\s*=.*?rev\s*=\s*"([0-9a-f]+)"', cargo, re.MULTILINE)
        if not found or found.group(1) != revision:
            raise ValueError(f"Native {package} and browser WASM must pin the same upstream revision")
    script = (root / "scripts/build-wasm.sh").read_text()
    found = re.search(r'^revision=([0-9a-f]+)$', script, re.MULTILINE)
    if not found or found.group(1) != revision:
        raise ValueError("WASM rebuild script and asset provenance must pin the same upstream revision")


if __name__ == "__main__":
    assets = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "python/figgyplot/assets"
    check_assets(assets)
    check_renderer_revision(Path(__file__).resolve().parents[1])
    print("Upstream JS/WASM asset hashes and sizes passed: %s" % assets)
