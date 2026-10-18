#!/usr/bin/env bash
# Reproduce cloud prerequisites without root or changes to tracked source files.
set -euo pipefail
cd /workspace/DCSMissionGeneratorJamesIronDemonAnvil
export PIP_CACHE_DIR=/workspace/.cache/pip
export IRONANVIL_CACHE_DIR=/workspace/.cache/ironanvil
python -m venv /workspace/.venvs/ironanvil
/workspace/.venvs/ironanvil/bin/python -m pip install -r requirements-dev.txt
/workspace/.venvs/ironanvil/bin/python -m pip check

# Apt verifies Release signatures and package hashes with the image's Debian
# archive keyring. Extract packages locally instead of installing system-wide.
cloud_tools=/workspace/.cloud-tools
mkdir -p "$cloud_tools/apt/lists/partial" "$cloud_tools/apt/cache/archives/partial" \
         "$cloud_tools/apt/empty" "$cloud_tools/debs"
cat > "$cloud_tools/apt/sources.list" <<'EOF'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
EOF
cat > "$cloud_tools/apt/apt.conf" <<'EOF'
Dir::Etc::parts "/workspace/.cloud-tools/apt/empty";
Dir::Etc::main "/workspace/.cloud-tools/apt/empty-main";
Dir::Etc::sourcelist "/workspace/.cloud-tools/apt/sources.list";
Dir::Etc::sourceparts "/workspace/.cloud-tools/apt/empty";
Dir::State::lists "/workspace/.cloud-tools/apt/lists";
Dir::Cache "/workspace/.cloud-tools/apt/cache";
Dir::Log "/workspace/.cloud-tools/apt";
APT::Sandbox::User "agent";
Acquire::Languages "none";
EOF
export APT_CONFIG="$cloud_tools/apt/apt.conf"
/usr/bin/apt-get update
(
  cd "$cloud_tools/debs"
  /usr/bin/apt-get download xvfb/trixie lua5.1/trixie
  if ! command -v xauth >/dev/null; then /usr/bin/apt-get download xauth/trixie; fi
  for package in ./*.deb; do dpkg-deb -x "$package" "$cloud_tools"; done
)
export PATH="$cloud_tools/usr/bin:$PATH"
/workspace/.venvs/ironanvil/bin/python -m ironanvil doctor
xvfb-run -a /workspace/.venvs/ironanvil/bin/python -m pytest -q
