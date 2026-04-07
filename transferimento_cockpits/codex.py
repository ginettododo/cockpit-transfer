from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .common import (
    OperationResult,
    TransferError,
    backup_if_exists,
    decode_jwt_payload,
    ensure_dir,
    find_by_email,
    find_by_id,
    now_iso,
    read_binary_payload,
    read_json_or_default,
    remove_entries_by_email,
    slugify,
    timestamp_slug,
    to_mutable_list,
    upsert_by_id,
    write_binary_payload,
    write_json,
)

TARGET_PROCESS_NAMES = {"Codex", "codex", "cockpit-tools"}


def get_active_codex_email(base_dir: Path) -> str | None:
    auth = read_json_or_default(base_dir / "auth.json", None)
    tokens = auth.get("tokens") if auth else None
    id_token = tokens.get("id_token") if tokens else None
    if not id_token:
        return None
    payload = decode_jwt_payload(id_token)
    email = payload.get("email")
    return str(email) if email else None


def inspect_accounts(cockpit_base_dir: Path, codex_base_dir: Path, emails: list[str] | None = None) -> list[dict[str, Any]]:
    codex_index = read_json_or_default(cockpit_base_dir / "codex_accounts.json", {"version": "1.0", "accounts": [], "current_account_id": None})
    codex_accounts = to_mutable_list(codex_index.get("accounts"))
    active_email = get_active_codex_email(codex_base_dir)

    all_emails = [item["email"] for item in codex_accounts if item.get("email")]
    if active_email and active_email not in all_emails:
        all_emails.append(active_email)

    target_emails = emails or all_emails
    rows: list[dict[str, Any]] = []
    for email in target_emails:
        entry = find_by_email(codex_accounts, email)
        payload_exists = False
        if entry:
            payload_exists = (cockpit_base_dir / "codex_accounts" / f"{entry['id']}.json").exists()
        rows.append(
            {
                "email": email,
                "codex_account_id": entry.get("id") if entry else None,
                "has_cockpit_index": entry is not None,
                "has_cockpit_payload": payload_exists,
                "is_current_in_cockpit": bool(entry and codex_index.get("current_account_id") == entry.get("id")),
                "is_active_codex_profile": bool(active_email and active_email.lower() == email.lower()),
            }
        )
    return rows


def export_accounts(cockpit_base_dir: Path, codex_base_dir: Path, emails: list[str], output_path: Path) -> OperationResult:
    codex_index = read_json_or_default(cockpit_base_dir / "codex_accounts.json", {"version": "1.0", "accounts": [], "current_account_id": None})
    codex_accounts = to_mutable_list(codex_index.get("accounts"))
    active_email = get_active_codex_email(codex_base_dir)

    selected_emails: list[str] = []
    seen: set[str] = set()
    for email in emails:
        key = email.lower()
        if key not in seen:
            seen.add(key)
            selected_emails.append(email)

    cockpit_payloads: list[dict[str, Any]] = []
    active_profiles: list[dict[str, Any]] = []
    warnings: list[str] = []

    for email in selected_emails:
        entry = find_by_email(codex_accounts, email)
        if not entry:
            warnings.append(f"Email not found in codex_accounts.json: {email}")
            continue

        payload_path = cockpit_base_dir / "codex_accounts" / f"{entry['id']}.json"
        if not payload_path.exists():
            warnings.append(f"Missing codex payload file for {email} at {payload_path}")
        else:
            cockpit_payloads.append({"index": entry, "file": read_json_or_default(payload_path, None)})

        if active_email and active_email.lower() == email.lower():
            files: list[dict[str, str]] = []
            for name in ("auth.json", "config.toml", "cap_sid", "version.json"):
                path = codex_base_dir / name
                if path.exists():
                    files.append(read_binary_payload(path, name))
                else:
                    warnings.append(f"Active .codex profile is missing file: {name}")
            active_profiles.append({"email": email, "files": files})

    package = {
        "version": 1,
        "package_type": "codex-account-migration",
        "created_at": now_iso(),
        "source_host": os.environ.get("COMPUTERNAME", ""),
        "source_cockpit_dir": str(cockpit_base_dir),
        "source_codex_dir": str(codex_base_dir),
        "selected_emails": selected_emails,
        "cockpit_codex_accounts": cockpit_payloads,
        "active_profiles": active_profiles,
        "warnings": warnings,
    }
    write_json(output_path, package)
    details = [
        f"Package: {output_path}",
        f"Selected emails: {len(selected_emails)}",
        f"Cockpit Codex accounts exported: {len(cockpit_payloads)}",
        f"Active .codex profiles exported: {len(active_profiles)}",
    ]
    details.extend(f"Warning: {warning}" for warning in warnings)
    return OperationResult("Codex export completed.", details, output_path)


def _running_target_processes() -> list[str]:
    if sys.platform.startswith("win"):
        script = (
            "Get-Process -ErrorAction SilentlyContinue | "
            "Where-Object { @('Codex','codex','cockpit-tools') -contains $_.ProcessName } | "
            "ForEach-Object { '{0} (PID {1})' -f $_.ProcessName, $_.Id }"
        )
        result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    result = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []

    matches: list[str] = []
    allowed = {name.lower() for name in TARGET_PROCESS_NAMES}
    for line in result.stdout.splitlines():
        raw = line.strip()
        if not raw:
            continue
        parts = raw.split(None, 1)
        if len(parts) != 2:
            continue
        pid, command = parts
        process_name = Path(command).name
        if process_name.lower() in allowed:
            matches.append(f"{process_name} (PID {pid})")
    return matches


def _stop_target_processes() -> None:
    if sys.platform.startswith("win"):
        script = "Stop-Process -Name Codex,codex,cockpit-tools -Force -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, check=False)
        return

    pkill = shutil.which("pkill")
    if not pkill:
        return
    for name in TARGET_PROCESS_NAMES:
        subprocess.run([pkill, "-x", name], capture_output=True, text=True, check=False)


def import_accounts(
    cockpit_base_dir: Path,
    codex_base_dir: Path,
    package_path: Path,
    overwrite_existing_email: bool = False,
    set_current_email: str | None = None,
    activate_email: str | None = None,
    force_stop_processes: bool = False,
    skip_process_check: bool = False,
) -> OperationResult:
    package = read_json_or_default(package_path, None)
    if not package:
        raise TransferError(f"Package file is empty or invalid: {package_path}")
    if package.get("version") != 1 or package.get("package_type") != "codex-account-migration":
        raise TransferError(f"Unsupported package format in {package_path}")

    ensure_dir(cockpit_base_dir)
    ensure_dir(cockpit_base_dir / "codex_accounts")

    backup_root = cockpit_base_dir / f"codex-migration-backup-import-{timestamp_slug()}"
    ensure_dir(backup_root)

    codex_index_path = cockpit_base_dir / "codex_accounts.json"
    codex_instances_path = cockpit_base_dir / "codex_instances.json"
    backup_if_exists(codex_index_path, backup_root)
    backup_if_exists(codex_instances_path, backup_root)

    codex_index = read_json_or_default(codex_index_path, {"version": "1.0", "accounts": [], "current_account_id": None})
    codex_instances = read_json_or_default(
        codex_instances_path,
        {"instances": [], "defaultSettings": {"bindAccountId": None, "extraArgs": "", "followLocalAccount": False, "lastPid": None}},
    )

    codex_accounts = to_mutable_list(codex_index.get("accounts"))
    imported: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for entry in package.get("cockpit_codex_accounts", []):
        email = str(entry["index"]["email"])
        existing = find_by_email(codex_accounts, email)
        if existing and not overwrite_existing_email:
            skipped.append(email)
            continue

        if overwrite_existing_email:
            for item in remove_entries_by_email(codex_accounts, email):
                payload_path = cockpit_base_dir / "codex_accounts" / f"{item['id']}.json"
                backup_if_exists(payload_path, backup_root)
                if payload_path.exists():
                    payload_path.unlink()

        conflict = find_by_id(codex_accounts, entry["index"]["id"])
        if conflict and str(conflict.get("email", "")).lower() != email.lower():
            raise TransferError(
                f"Id conflict in codex_accounts.json for id {entry['index']['id']}: existing email {conflict.get('email')}, incoming email {email}"
            )

        payload_path = cockpit_base_dir / "codex_accounts" / f"{entry['index']['id']}.json"
        backup_if_exists(payload_path, backup_root)
        write_json(payload_path, entry["file"])
        result = upsert_by_id(codex_accounts, entry["index"])
        (imported if result == "added" else updated).append(email)

    codex_index["accounts"] = codex_accounts

    if set_current_email:
        current_entry = find_by_email(codex_accounts, set_current_email)
        if not current_entry:
            raise TransferError(f"Cannot set current email because it is not present after import: {set_current_email}")
        codex_index["current_account_id"] = current_entry["id"]
        default_settings = codex_instances.setdefault("defaultSettings", {})
        default_settings["bindAccountId"] = current_entry["id"]

    write_json(codex_index_path, codex_index)
    if set_current_email:
        write_json(codex_instances_path, codex_instances)

    codex_backup_root: Path | None = None
    if activate_email:
        profile_entry = next((item for item in package.get("active_profiles", []) if str(item.get("email", "")).lower() == activate_email.lower()), None)
        if not profile_entry:
            raise TransferError(f"The package does not contain an active .codex profile for {activate_email}")

        if not skip_process_check:
            running = _running_target_processes()
            if running and force_stop_processes:
                _stop_target_processes()
                running = _running_target_processes()
            if running:
                raise TransferError(
                    "Close Codex/Cockpit Tools completely before activating the .codex profile. Still running: " + ", ".join(running)
                )

        codex_backup_root = codex_base_dir.parent / ".codex-profile-backups" / f"{slugify(activate_email)}-{timestamp_slug()}"
        ensure_dir(codex_backup_root / ".codex-before")
        ensure_dir(codex_base_dir)

        for payload in profile_entry.get("files", []):
            target_path = codex_base_dir / payload["relative_path"]
            if target_path.exists():
                ensure_dir((codex_backup_root / ".codex-before" / payload["relative_path"]).parent)
                shutil.copy2(target_path, codex_backup_root / ".codex-before" / payload["relative_path"])
            write_binary_payload(codex_base_dir, payload)

    details = [
        f"Cockpit backup root: {backup_root}",
        f"Imported emails: {len(imported)}",
        f"Updated emails: {len(updated)}",
        f"Skipped emails: {len(skipped)}",
    ]
    if set_current_email:
        details.append(f"Set current Cockpit Tools email: {set_current_email}")
    if activate_email and codex_backup_root:
        details.append(f"Activated .codex profile email: {activate_email}")
        details.append(f".codex backup root: {codex_backup_root}")
    details.extend(f"Skipped duplicate email: {email}" for email in skipped)
    return OperationResult("Codex import completed.", details, backup_root)
