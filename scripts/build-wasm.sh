#!/usr/bin/env bash
# Rebuild packaged assets from the upstream public web host (no source vendoring).
set -euo pipefail
revision=632d1844f184f9e9a230867773ec1885e1557541
repo_root=$(cd "$(dirname "$0")/.." && pwd)
wasm_source=${FIGGY_WASM_SOURCE:-${TMPDIR:-/tmp}/figgy-web-kernel-$revision}
if [ ! -d "$wasm_source/.git" ]; then
    git clone https://github.com/shim9610/figgy.git "$wasm_source"
fi
if [ "$(git -C "$wasm_source" rev-parse HEAD)" != "$revision" ]; then
    git -C "$wasm_source" checkout --detach "$revision"
fi
rustup target add wasm32-unknown-unknown
# Must match the pinned upstream Cargo.lock, independent of native Cargo.lock.
if [ "$(wasm-bindgen --version 2>/dev/null || true)" != "wasm-bindgen 0.2.129" ]; then
    cargo install wasm-bindgen-cli --version 0.2.129 --locked
fi
cargo build --manifest-path "$wasm_source/crates/web/Cargo.toml" --target wasm32-unknown-unknown --release --locked
wasm_target=${CARGO_TARGET_DIR:-$wasm_source/target}
wasm-bindgen "$wasm_target/wasm32-unknown-unknown/release/figgy.wasm" \
    --target web --out-dir "$repo_root/python/figgyplot/assets" --out-name figgy
chmod 644 "$repo_root"/python/figgyplot/assets/*
python - "$repo_root/python/figgyplot/assets" "$revision" <<'PYPROVENANCE'
import hashlib,json,pathlib,sys
assets=pathlib.Path(sys.argv[1])
data={'upstream_repository':'https://github.com/shim9610/figgy','upstream_revision':sys.argv[2],'renderer_version':'0.17.0','web_package_version':'0.14.0','wasm_bindgen_version':'0.2.129','assets':{p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in assets.iterdir() if p.suffix in ('.js','.wasm')}}
(assets/'provenance.json').write_text(json.dumps(data,indent=2)+'\n')
PYPROVENANCE
