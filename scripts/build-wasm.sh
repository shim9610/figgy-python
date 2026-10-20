#!/usr/bin/env bash
# Rebuild the public web host plus the recorded, bridge-only completion patch.
set -euo pipefail
revision=3a0a6a33be14f2ff4dab1475d4fcec9eafa1ee04
repo_root=$(cd "$(dirname "$0")/.." && pwd)
wasm_source=${FIGGY_WASM_SOURCE:-${TMPDIR:-/tmp}/figgy-web-kernel-$revision}
if ! git -C "$wasm_source" rev-parse --git-dir >/dev/null 2>&1; then
    git clone https://github.com/shim9610/figgy.git "$wasm_source"
fi
if [ "$(git -C "$wasm_source" rev-parse HEAD)" != "$revision" ]; then
    git -C "$wasm_source" checkout --detach "$revision"
fi
registry_provenance=$(mktemp)
build_source=$(mktemp -d)
trap 'rm -f "$registry_provenance"; rm -rf "$build_source"' EXIT
# Verify the actual published archives and source bytes before compiling WASM.
python "$repo_root/scripts/record_registry_provenance.py" \
    "$repo_root" "$wasm_source" "$revision" "$registry_provenance"
# Never patch the verified checkout. Archive only tracked release files, then
# apply the validated bridge-only patch in a disposable build directory.
git -C "$wasm_source" archive "$revision" | tar -x -C "$build_source"
# Establish a repository root even when TMPDIR is inside another checkout;
# git apply otherwise silently filters paths outside that parent's subdirectory.
git -C "$build_source" init -q
git -C "$build_source" apply --check "$repo_root/scripts/wasm-host.patch"
git -C "$build_source" apply "$repo_root/scripts/wasm-host.patch"
rustup target add wasm32-unknown-unknown
# Must match the pinned upstream Cargo.lock, independent of native Cargo.lock.
if [ "$(wasm-bindgen --version 2>/dev/null || true)" != "wasm-bindgen 0.2.129" ]; then
    cargo install wasm-bindgen-cli --version 0.2.129 --locked
fi
cargo build --manifest-path "$build_source/crates/web/Cargo.toml" --target wasm32-unknown-unknown --release --locked
wasm_target=${CARGO_TARGET_DIR:-$build_source/target}
wasm-bindgen "$wasm_target/wasm32-unknown-unknown/release/figgy.wasm" \
    --target web --out-dir "$repo_root/python/figgyplot/assets" --out-name figgy
chmod 644 "$repo_root"/python/figgyplot/assets/*
python - "$repo_root/python/figgyplot/assets" "$registry_provenance" <<'PYPROVENANCE'
import hashlib,json,pathlib,sys
assets=pathlib.Path(sys.argv[1])
data=json.loads(pathlib.Path(sys.argv[2]).read_text())
data.update(wasm_bindgen_version='0.2.129',assets={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in assets.iterdir() if p.suffix in ('.js','.wasm')})
(assets/'provenance.json').write_text(json.dumps(data,indent=2)+'\n')
PYPROVENANCE
