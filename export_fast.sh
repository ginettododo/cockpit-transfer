#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$APP_DIR"

# 'uv' permette di far girare l'export con la versione corretta di Python (>= 3.11)
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
    # Cockpit richiede Python 3.11+
    if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

UV_BIN="$(find_uv || true)"
if [ -n "$UV_BIN" ]; then
  echo "Esportazione rapida con uv (Python 3.12+ automatico)..."
  exec "$UV_BIN" run --python 3.12 -m transferimento_cockpits export-fast "$@"
fi

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERRORE: Python 3.11+ non trovato."
  echo "Si consiglia di usare 'uv' o scaricare Python 3.12 da python.org"
  exit 1
fi

exec "$PYTHON_BIN" -m transferimento_cockpits export-fast "$@"
