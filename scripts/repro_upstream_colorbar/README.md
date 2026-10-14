Reproduction for https://github.com/shim9610/figgy/issues/6.

This directly calls the published renderer's CPU decoration raster. No Python,
GPU/device/queue, readback or concurrent calls are involved. It deliberately
supplies a malformed layout that the upstream validator currently accepts.

Build separately, then run with an **external test watchdog** (Linux example):

```sh
cargo build --release --manifest-path scripts/repro_upstream_colorbar/Cargo.toml
timeout 5s scripts/repro_upstream_colorbar/target/release/figgy-colorbar-repro
```

Expected current output: validation `Ok(())`, a 320×240 chart with computed data
area height 4294967295, then CPU raster work that the watchdog stops. This is
billions of colorbar bands, not a GPU deadlock. Do not run without a watchdog.
Production figgy-python rejects the negative title margin before committing it.
