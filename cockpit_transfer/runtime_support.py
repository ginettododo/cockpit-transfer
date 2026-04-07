from __future__ import annotations

from datetime import datetime
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .app_state import load_app_state, save_app_state
from .common import slugify

FAST_PRODUCTS = ["codex", "gemini", "antigravity"]


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def state_path() -> Path:
    return project_root() / "app_state.json"


def default_downloads_dir() -> Path:
    downloads = Path.home() / "Downloads"
    return downloads if downloads.exists() else Path.home() / "Desktop"


def latest_zip_in_dir(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    candidates = [path for path in directory.glob("*.zip") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name.lower()))


def load_runtime_state() -> dict[str, Any]:
    return load_app_state(state_path(), str(default_downloads_dir()))


def save_runtime_state(state: dict[str, Any]) -> None:
    save_app_state(state_path(), state)


def default_cockpit_dir() -> Path:
    return Path.home() / ".antigravity_cockpit"


def default_codex_dir() -> Path:
    return Path.home() / ".codex"


def default_gemini_dir() -> Path:
    return Path.home() / ".gemini"


def cockpit_launch_candidates() -> list[Path]:
    candidates: list[Path] = []
    if sys.platform.startswith("win"):
        local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates.extend(
            [
                local_appdata / "Programs" / "Antigravity" / "Antigravity.exe",
                Path.home() / "Desktop" / "Cockpit Tools.lnk",
            ]
        )
    elif sys.platform == "darwin":
        candidates.extend(
            [
                Path("/Applications/Antigravity.app"),
                Path.home() / "Applications" / "Antigravity.app",
                Path("/Applications/Cockpit Tools.app"),
                Path.home() / "Applications" / "Cockpit Tools.app",
            ]
        )
    return candidates


def stop_cockpit_processes_for_restart() -> None:
    if sys.platform.startswith("win"):
        script = "Stop-Process -Name Antigravity,Codex,codex,cockpit-tools -Force -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, check=False)
        return

    subprocess.run(["pkill", "-x", "Antigravity"], capture_output=True, text=True, check=False)
    subprocess.run(["pkill", "-x", "Codex"], capture_output=True, text=True, check=False)
    subprocess.run(["pkill", "-x", "codex"], capture_output=True, text=True, check=False)
    subprocess.run(["pkill", "-x", "cockpit-tools"], capture_output=True, text=True, check=False)


def restart_cockpit_if_possible() -> str | None:
    try:
        stop_cockpit_processes_for_restart()
        for candidate in cockpit_launch_candidates():
            if not candidate.exists():
                continue
            if sys.platform.startswith("win"):
                os.startfile(str(candidate))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(candidate)])
            else:
                subprocess.Popen([str(candidate)])
            return str(candidate)
    except Exception:
        return None
    return None


def default_zip_name(products: list[str], emails: list[str]) -> str:
    joined_products = "+".join(products)
    email_slug = "__".join(slugify(email) for email in emails[:3])
    if len(emails) > 3:
        email_slug += f"__plus{len(emails) - 3}"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"transfer-{joined_products}-{email_slug}-{stamp}.zip"
