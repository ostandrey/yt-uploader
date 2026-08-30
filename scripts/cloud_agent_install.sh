#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the Coin Wire uploader.
# Creates a local virtualenv and installs pinned Python dependencies.
# System packages (python3, ffmpeg, DejaVu/Liberation fonts) come from the base image.
set -euo pipefail

cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"

# Ensure the venv module is available (Debian/Ubuntu ships it separately).
if ! "$PY" -m venv --help >/dev/null 2>&1 || ! "$PY" -c "import ensurepip" >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    PYVER="$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    sudo apt-get update -qq
    sudo apt-get install -y -qq "python${PYVER}-venv" || sudo apt-get install -y -qq python3-venv
  fi
fi

# A stale Windows virtualenv (Scripts/*.exe) may be committed/checked out; replace it.
if [ -e .venv ] && [ ! -x .venv/bin/python ]; then
  echo "Removing non-Linux .venv"
  rm -rf .venv
fi

if [ ! -x .venv/bin/python ]; then
  echo "Creating virtualenv at .venv"
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
# Test runner (not a production dependency, but needed for the dev test suite).
pip install pytest

# Runtime data directories (mirrors the Dockerfile layout).
mkdir -p \
  data/storage/coin_wire/videos \
  data/storage/coin_wire/renders \
  data/assets/broll_library \
  tokens

echo "Install complete."
