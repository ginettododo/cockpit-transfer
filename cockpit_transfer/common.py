from __future__ import annotations

import base64
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class TransferError(RuntimeError):
    pass


@dataclass
class OperationResult:
    summary: str
    details: list[str]
    output_path: Path | None = None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    return json.loads(raw)


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def to_mutable_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return list(value)


def find_by_email(items: Iterable[dict[str, Any]], email: str) -> dict[str, Any] | None:
    target = email.lower()
    for item in items:
        if item and str(item.get("email", "")).lower() == target:
            return item
    return None


def find_by_id(items: Iterable[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    for item in items:
        if item and item.get("id") == item_id:
            return item
    return None


def remove_entries_by_email(items: list[dict[str, Any]], email: str) -> list[dict[str, Any]]:
    target = email.lower()
    removed: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for item in items:
        if item and str(item.get("email", "")).lower() == target:
            removed.append(item)
        else:
            kept.append(item)
    items[:] = kept
    return removed


def upsert_by_id(items: list[dict[str, Any]], item: dict[str, Any]) -> str:
    for index, existing in enumerate(items):
        if existing and existing.get("id") == item.get("id"):
            items[index] = item
            return "updated"
    items.append(item)
    return "added"


def backup_if_exists(path: Path, backup_root: Path) -> None:
    if not path.exists():
        return
    ensure_dir(backup_root)
    shutil.copy2(path, backup_root / path.name)


def read_binary_payload(path: Path, relative_path: str) -> dict[str, str]:
    return {
        "relative_path": relative_path,
        "encoding": "base64",
        "content": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def write_binary_payload(base_dir: Path, payload: dict[str, str]) -> Path:
    target_path = base_dir / payload["relative_path"]
    ensure_dir(target_path.parent)
    target_path.write_bytes(base64.b64decode(payload["content"]))
    return target_path


def decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    normalized = parts[1].replace("-", "+").replace("_", "/")
    normalized += "=" * (-len(normalized) % 4)
    try:
        raw = base64.b64decode(normalized.encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise TransferError(f"Unable to decode token payload: {exc}") from exc


def slugify(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in "._-":
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "item"
