#!/usr/bin/env bash
# Runtime packages for the pinned ubuntu-24.04 CI image. Do not depend on its
# rotating mirrorlists or unrelated vendor repositories (for example .NET).
set -euo pipefail

runtime_sources=$(mktemp --suffix=.sources)
trap 'rm -f "$runtime_sources"' EXIT
cat > "$runtime_sources" <<'SOURCES'
Types: deb
URIs: https://archive.ubuntu.com/ubuntu/
Suites: noble noble-updates noble-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: https://security.ubuntu.com/ubuntu/
Suites: noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
SOURCES

apt_sources=(-o "Dir::Etc::sourcelist=$runtime_sources" -o 'Dir::Etc::sourceparts=-')
sudo apt-get "${apt_sources[@]}" update
sudo apt-get "${apt_sources[@]}" install -y \
  git mesa-vulkan-drivers libvulkan1 libxkbcommon0 libxkbcommon-x11-0 \
  xvfb xdotool xclip openbox wmctrl fonts-noto-cjk
