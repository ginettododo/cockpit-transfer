#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$APP_DIR"

if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$APP_DIR" >/dev/null 2>&1 || true
fi

chmod +x ./*.command ./*.sh ./macos_launchers/*.command >/dev/null 2>&1 || true

find_python() {
  for candidate in python3 python; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    if "$candidate" -c "import sys" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "Python 3 not found or not usable."
  echo "On macOS please install Python.org or manually use an available interpreter."
  exit 1
fi

exec "$PYTHON_BIN" -m cockpit_transfer export-fast "$@"
