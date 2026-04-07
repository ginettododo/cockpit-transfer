#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$APP_DIR"

# Cerchiamo 'uv' per garantire compatibilità con Python 3.11+
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
    # Requisito minimo per Cockpit Tools: 3.11
    if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if [ $# -eq 0 ]; then
  echo "INFO: Nessun file specificato. Cercherò l'ultimo ZIP scaricato in Downloads..."
fi

UV_BIN="$(find_uv || true)"
if [ -n "$UV_BIN" ]; then
  echo "Importazione tramite uv (Python 3.12+)..."
  exec "$UV_BIN" run --python 3.12 -m transferimento_cockpits import-fast "$@"
fi

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERRORE: Python 3.11+ non trovato."
  echo "Scarica 'uv' o Python 3.12 per poter procedere."
  exit 1
fi

exec "$PYTHON_BIN" -m transferimento_cockpits import-fast "$@"
