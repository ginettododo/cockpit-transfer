#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$APP_DIR"

# Proviamo a usare 'uv' se installato, dato che il Python di sistema (3.9.6) è troppo vecchio
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
    # Verifichiamo se la versione è >= 3.11
    if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

UV_BIN="$(find_uv || true)"
if [ -n "$UV_BIN" ]; then
  echo "Uso uv per avviare l'applicazione (Python >= 3.11 automatico)..."
  exec "$UV_BIN" run --python 3.12 main.pyw "$@"
fi

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERRORE: Python 3.11+ non trovato oppure non utilizzabile."
  echo "Il Python di sistema (3.9.6) è troppo vecchio per questa app."
  echo "Soluzione consigliata: installa 'uv' (https://github.com/astral-sh/uv) o scarica Python 3.12 da python.org"
  exit 1
fi

exec "$PYTHON_BIN" main.pyw "$@"
