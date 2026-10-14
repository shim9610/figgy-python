"""Verify the exact upstream asset bytes without importing the extension."""
import hashlib
import json
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


if __name__ == "__main__":
    assets = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "python/figgyplot/assets"
    check_assets(assets)
    print("Upstream JS/WASM asset hashes and sizes passed: %s" % assets)
