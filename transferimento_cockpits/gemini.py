from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    OperationResult,
    TransferError,
    backup_if_exists,
    ensure_dir,
    find_by_email,
    find_by_id,
    now_iso,
    read_json_or_default,
    slugify,
    timestamp_slug,
    to_mutable_list,
    upsert_by_id,
    write_json,
)


def inspect_accounts(cockpit_base_dir: Path, gemini_base_dir: Path, emails: list[str] | None = None) -> list[dict[str, Any]]:
    gemini_index = read_json_or_default(cockpit_base_dir / "gemini_accounts.json", {"version": "1.0", "accounts": []})
    gemini_accounts = to_mutable_list(gemini_index.get("accounts"))
    google_accounts = read_json_or_default(gemini_base_dir / "google_accounts.json", {"active": None, "old": []})
    active_email = google_accounts.get("active")

    all_emails = [item["email"] for item in gemini_accounts if item.get("email")]
    if active_email and active_email not in all_emails:
        all_emails.append(active_email)

    target_emails = emails or all_emails
    rows: list[dict[str, Any]] = []
    for email in target_emails:
        entry = find_by_email(gemini_accounts, email)
        payload_exists = False
        if entry:
            payload_exists = (cockpit_base_dir / "gemini_accounts" / f"{entry['id']}.json").exists()
        rows.append(
            {
                "email": email,
                "gemini_account_id": entry.get("id") if entry else None,
                "has_cockpit_index": entry is not None,
                "has_cockpit_payload": payload_exists,
                "is_active_gemini_profile": bool(active_email and active_email.lower() == email.lower()),
            }
        )
    return rows


def export_accounts(cockpit_base_dir: Path, gemini_base_dir: Path, emails: list[str], output_path: Path) -> OperationResult:
    gemini_index = read_json_or_default(cockpit_base_dir / "gemini_accounts.json", {"version": "1.0", "accounts": []})
    gemini_accounts = to_mutable_list(gemini_index.get("accounts"))
    google_accounts = read_json_or_default(gemini_base_dir / "google_accounts.json", {"active": None, "old": []})
    active_email = google_accounts.get("active")
    oauth_creds = read_json_or_default(gemini_base_dir / "oauth_creds.json", None)

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
        entry = find_by_email(gemini_accounts, email)
        if not entry:
            warnings.append(f"Email not found in gemini_accounts.json: {email}")
            continue

        payload_path = cockpit_base_dir / "gemini_accounts" / f"{entry['id']}.json"
        if not payload_path.exists():
            warnings.append(f"Missing gemini payload file for {email} at {payload_path}")
        else:
            payload = read_json_or_default(payload_path, None)
            cockpit_payloads.append({"index": entry, "file": payload})

            if active_email and active_email.lower() == email.lower():
                raw = payload.get("gemini_auth_raw") if payload else None
                if not raw:
                    raw = {
                        "access_token": payload.get("access_token"),
                        "refresh_token": payload.get("refresh_token"),
                        "id_token": payload.get("id_token"),
                        "token_type": payload.get("token_type"),
                        "scope": payload.get("scope"),
                        "expiry_date": payload.get("expiry_date"),
                        "email": payload.get("email"),
                        "sub": payload.get("auth_id"),
                    }
                active_profiles.append(
                    {
                        "email": email,
                        "google_accounts": {
                            "active": email,
                            "old": [item for item in to_mutable_list(google_accounts.get("old")) if item and str(item).lower() != email.lower()],
                        },
                        "oauth_creds": raw or oauth_creds,
                    }
                )

    package = {
        "version": 1,
        "package_type": "gemini-account-migration",
        "created_at": now_iso(),
        "source_cockpit_dir": str(cockpit_base_dir),
        "source_gemini_dir": str(gemini_base_dir),
        "selected_emails": selected_emails,
        "cockpit_gemini_accounts": cockpit_payloads,
        "active_profiles": active_profiles,
        "warnings": warnings,
    }
    write_json(output_path, package)
    details = [
        f"Package: {output_path}",
        f"Selected emails: {len(selected_emails)}",
        f"Cockpit Gemini accounts exported: {len(cockpit_payloads)}",
        f"Active .gemini profiles exported: {len(active_profiles)}",
    ]
    details.extend(f"Warning: {warning}" for warning in warnings)
    return OperationResult("Gemini export completed.", details, output_path)


def import_accounts(
    cockpit_base_dir: Path,
    gemini_base_dir: Path,
    package_path: Path,
    overwrite_existing_email: bool = False,
    activate_email: str | None = None,
) -> OperationResult:
    package = read_json_or_default(package_path, None)
    if not package:
        raise TransferError(f"Package file is empty or invalid: {package_path}")
    if package.get("version") != 1 or package.get("package_type") != "gemini-account-migration":
        raise TransferError(f"Unsupported package format in {package_path}")

    ensure_dir(cockpit_base_dir)
    ensure_dir(cockpit_base_dir / "gemini_accounts")

    backup_root = cockpit_base_dir / f"gemini-migration-backup-import-{timestamp_slug()}"
    ensure_dir(backup_root)
    gemini_index_path = cockpit_base_dir / "gemini_accounts.json"
    backup_if_exists(gemini_index_path, backup_root)

    gemini_index = read_json_or_default(gemini_index_path, {"version": "1.0", "accounts": []})
    gemini_accounts = to_mutable_list(gemini_index.get("accounts"))

    imported: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for entry in package.get("cockpit_gemini_accounts", []):
        email = str(entry["index"]["email"])
        existing = find_by_email(gemini_accounts, email)
        if existing and not overwrite_existing_email:
            skipped.append(email)
            continue

        if overwrite_existing_email:
            kept = []
            for item in gemini_accounts:
                if item and str(item.get("email", "")).lower() == email.lower():
                    payload_path = cockpit_base_dir / "gemini_accounts" / f"{item['id']}.json"
                    backup_if_exists(payload_path, backup_root)
                    if payload_path.exists():
                        payload_path.unlink()
                else:
                    kept.append(item)
            gemini_accounts[:] = kept

        conflict = find_by_id(gemini_accounts, entry["index"]["id"])
        if conflict and str(conflict.get("email", "")).lower() != email.lower():
            raise TransferError(
                f"Id conflict in gemini_accounts.json for id {entry['index']['id']}: existing email {conflict.get('email')}, incoming email {email}"
            )

        payload_path = cockpit_base_dir / "gemini_accounts" / f"{entry['index']['id']}.json"
        backup_if_exists(payload_path, backup_root)
        write_json(payload_path, entry["file"])
        result = upsert_by_id(gemini_accounts, entry["index"])
        (imported if result == "added" else updated).append(email)

    gemini_index["accounts"] = gemini_accounts
    write_json(gemini_index_path, gemini_index)

    gemini_backup_root: Path | None = None
    if activate_email:
        profile_entry = next((item for item in package.get("active_profiles", []) if str(item.get("email", "")).lower() == activate_email.lower()), None)
        if not profile_entry:
            raise TransferError(f"The package does not contain an active .gemini profile for {activate_email}")

        gemini_backup_root = gemini_base_dir.parent / ".gemini-profile-backups" / f"{slugify(activate_email)}-{timestamp_slug()}"
        ensure_dir(gemini_backup_root)
        ensure_dir(gemini_base_dir)

        for name in ("google_accounts.json", "oauth_creds.json"):
            backup_if_exists(gemini_base_dir / name, gemini_backup_root)

        google_accounts = profile_entry["google_accounts"]
        existing_google = read_json_or_default(gemini_base_dir / "google_accounts.json", {"active": None, "old": []})
        previous_active = existing_google.get("active")
        old_emails = [item for item in to_mutable_list(existing_google.get("old")) if item]
        if previous_active and str(previous_active).lower() != activate_email.lower() and previous_active not in old_emails:
            old_emails.append(previous_active)
        new_old = [item for item in old_emails if str(item).lower() != activate_email.lower()]

        write_json(gemini_base_dir / "google_accounts.json", {"active": activate_email, "old": new_old})
        write_json(gemini_base_dir / "oauth_creds.json", profile_entry["oauth_creds"])

    details = [
        f"Cockpit backup root: {backup_root}",
        f"Imported emails: {len(imported)}",
        f"Updated emails: {len(updated)}",
        f"Skipped emails: {len(skipped)}",
    ]
    if activate_email and gemini_backup_root:
        details.append(f"Activated .gemini profile email: {activate_email}")
        details.append(f".gemini backup root: {gemini_backup_root}")
    details.extend(f"Skipped duplicate email: {email}" for email in skipped)
    return OperationResult("Gemini import completed.", details, backup_root)
