#!/usr/bin/env bash
set -euo pipefail
cd /workspace
mkdir -p /workspace/.figgy-tools
export RUSTUP_HOME=/workspace/.figgy-tools/rustup
export CARGO_HOME=/workspace/.figgy-tools/cargo
export UV_CACHE_DIR=/workspace/.figgy-tools/uv-cache
export PIP_CACHE_DIR=/workspace/.figgy-tools/pip-cache
export XDG_CACHE_HOME=/workspace/.figgy-tools/cache
export MESA_SHADER_CACHE_DIR=/workspace/.figgy-tools/mesa-shader-cache
export PATH="$CARGO_HOME/bin:$PATH"
if ! command -v rustup >/dev/null; then
  curl --fail --silent --show-error --proto '=https' --tlsv1.2 https://sh.rustup.rs -o /workspace/.figgy-tools/rustup-init.sh
  sh /workspace/.figgy-tools/rustup-init.sh -y --no-modify-path --profile minimal --default-toolchain 1.99.0
fi
rustup toolchain install 1.99.0 --profile minimal --no-self-update
rustup default 1.99.0
if [ ! -x /workspace/.figgy-tools/venv/bin/python ]; then
  uv venv /workspace/.figgy-tools/venv --python python3.12
fi
uv pip install --python /workspace/.figgy-tools/venv/bin/python pip==26.2.1 maturin==1.15.0 pytest==9.1.1 build==1.6.1 twine==7.0.0
mkdir -p /workspace/.figgy-tools/apt/empty /workspace/.figgy-tools/apt/lists/partial /workspace/.figgy-tools/apt/cache/archives/partial /workspace/.figgy-tools/mesa
cat > /workspace/.figgy-tools/apt/sources.list <<'TXT'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
TXT
cat > /workspace/.figgy-tools/apt/apt.conf <<'CONF'
Dir::Etc::main "-";
Dir::Etc::parts "/workspace/.figgy-tools/apt/empty";
Dir::Etc::sourcelist "/workspace/.figgy-tools/apt/sources.list";
Dir::Etc::sourceparts "-";
Dir::State::lists "/workspace/.figgy-tools/apt/lists";
Dir::Cache "/workspace/.figgy-tools/apt/cache";
#clear APT::Update::Post-Invoke;
#clear APT::Update::Post-Invoke-Success;
CONF
export APT_CONFIG=/workspace/.figgy-tools/apt/apt.conf
/usr/bin/apt-get update
cd /workspace/.figgy-tools/mesa
/usr/bin/apt-get download mesa-vulkan-drivers
for package in mesa-vulkan-drivers_*.deb; do dpkg-deb -x "$package" root; done
/workspace/.figgy-tools/venv/bin/python - <<'PY'
import json,pathlib
base=pathlib.Path('/workspace/.figgy-tools')
p=base/'mesa/root/usr/share/vulkan/icd.d/lvp_icd.json'
c=json.loads(p.read_text())
c['ICD']['library_path']=str(base/'mesa/root/usr/lib/x86_64-linux-gnu/libvulkan_lvp.so')
(base/'mesa/lvp_icd.json').write_text(json.dumps(c))
PY
mkdir -p /workspace/.figgy-tools/xdg-runtime
chmod 700 /workspace/.figgy-tools/xdg-runtime
cat > /workspace/.figgy-tools/activate.sh <<'ACTIVATE'
export RUSTUP_HOME=/workspace/.figgy-tools/rustup
export CARGO_HOME=/workspace/.figgy-tools/cargo
export UV_CACHE_DIR=/workspace/.figgy-tools/uv-cache
export PIP_CACHE_DIR=/workspace/.figgy-tools/pip-cache
export XDG_CACHE_HOME=/workspace/.figgy-tools/cache
export MESA_SHADER_CACHE_DIR=/workspace/.figgy-tools/mesa-shader-cache
export CARGO_TARGET_DIR=/workspace/.figgy-tools/target
export CARGO_BUILD_JOBS=4
export PATH=/workspace/.figgy-tools/cargo/bin:$PATH
. /workspace/.figgy-tools/venv/bin/activate
export VK_DRIVER_FILES=/workspace/.figgy-tools/mesa/lvp_icd.json
export WGPU_BACKEND=vulkan
export XDG_RUNTIME_DIR=/workspace/.figgy-tools/xdg-runtime
ACTIVATE
. /workspace/.figgy-tools/activate.sh
cd /workspace/figgy-python
rustc --version
python --version
maturin --version
# The selected repository is currently empty. Do not generate application code,
# dependency manifests, or lockfiles during onboarding.
