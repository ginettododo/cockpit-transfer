#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$APP_DIR"

if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$APP_DIR" >/dev/null 2>&1 || true
fi

chmod +x ./*.command ./*.sh ./macos_launchers/*.command >/dev/null 2>&1 || true

find_uv() {
  for candidate in "$HOME/.local/bin/uv" uv; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

find_python() {
  for candidate in python3 python; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if [ $# -eq 0 ]; then
  echo "INFO: Searching for latest ZIP in Downloads for import..."
fi

UV_BIN="$(find_uv || true)"
if [ -n "$UV_BIN" ]; then
  echo "Importing with uv (automatic Python 3.12+)..."
  exec "$UV_BIN" run --python 3.12 -m cockpit_transfer import-fast "$@"
fi

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: Python 3.11+ not found."
  echo "It is recommended to use 'uv' or download Python 3.12."
  exit 1
fi

exec "$PYTHON_BIN" -m cockpit_transfer import-fast "$@"
