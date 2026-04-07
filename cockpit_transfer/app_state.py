from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ensure_dir, read_json_or_default, write_json

DEFAULT_EXPORT_PRODUCTS = {"codex": True, "gemini": True, "antigravity": True}
DEFAULT_INSPECT_PRODUCTS = {"codex": True, "gemini": False, "antigravity": False}


def default_app_state(default_output_dir: str) -> dict[str, Any]:
    return {
        "export_products": [name for name, enabled in DEFAULT_EXPORT_PRODUCTS.items() if enabled],
        "inspect_products": [name for name, enabled in DEFAULT_INSPECT_PRODUCTS.items() if enabled],
        "last_emails": [],
        "output_dir": default_output_dir,
        "last_package_path": "",
        "overwrite_existing_email": False,
        "force_stop_processes": True,
        "codex_set_current_email": "",
        "codex_activate_email": "",
        "gemini_activate_email": "",
    }


def load_app_state(path: Path, default_output_dir: str) -> dict[str, Any]:
    state = default_app_state(default_output_dir)
    raw = read_json_or_default(path, {})
    if not isinstance(raw, dict):
        return state

    state.update(raw)
    output_dir = Path(str(state.get("output_dir", default_output_dir)))
    if not output_dir.exists():
        state["output_dir"] = default_output_dir

    package_path = str(state.get("last_package_path", "")).strip()
    if package_path and not Path(package_path).exists():
        state["last_package_path"] = ""

    for key in ("export_products", "inspect_products", "last_emails"):
        value = state.get(key)
        if not isinstance(value, list):
            state[key] = []

    return state


def save_app_state(path: Path, state: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    write_json(path, state)
