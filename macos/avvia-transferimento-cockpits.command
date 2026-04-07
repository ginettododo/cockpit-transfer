#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$APP_DIR"

if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$APP_DIR" >/dev/null 2>&1 || true
fi

chmod +x ./*.command ./*.sh ./macos/*.command ./macos/*.sh >/dev/null 2>&1 || true

# Cerchiamo 'uv' se disponibile, per gestire automaticamente l'ambiente Python 3.12+
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

UV_BIN="$(find_uv || true)"
if [ -n "$UV_BIN" ]; then
  echo "Avvio con uv (controllo Python 3.12 automatico)..."
  exec "$UV_BIN" run --python 3.12 main.pyw "$@"
fi

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERRORE: Python 3.11+ non trovato oppure non funzionante."
  echo "Il Python standard di Apple (3.9.6) è troppo vecchio."
  echo "Usa 'uv' o scarica Python 3.12 da python.org per continuare."
  exit 1
fi

exec "$PYTHON_BIN" main.pyw "$@"
