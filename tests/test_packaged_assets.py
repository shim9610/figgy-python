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
