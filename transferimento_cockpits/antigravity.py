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
    remove_entries_by_email,
    timestamp_slug,
    to_mutable_list,
    upsert_by_id,
    write_json,
)


def inspect_accounts(base_dir: Path, emails: list[str] | None = None) -> list[dict[str, Any]]:
    accounts_index = read_json_or_default(base_dir / "accounts.json", {"version": "2.0", "accounts": []})
    codex_index = read_json_or_default(base_dir / "codex_accounts.json", {"version": "1.0", "accounts": []})
    fingerprints_index = read_json_or_default(base_dir / "fingerprints.json", {"fingerprints": []})

    accounts = to_mutable_list(accounts_index.get("accounts"))
    codex_accounts = to_mutable_list(codex_index.get("accounts"))
    fingerprints = to_mutable_list(fingerprints_index.get("fingerprints"))

    all_emails = [item["email"] for item in accounts if item.get("email")]
    for item in codex_accounts:
        email = item.get("email")
        if email and email not in all_emails:
            all_emails.append(email)
    target_emails = emails or all_emails
    rows: list[dict[str, Any]] = []
    for email in target_emails:
        regular = find_by_email(accounts, email)
        codex = find_by_email(codex_accounts, email)
        fingerprint_id = None
        has_account_file = False

        if regular:
            account_path = base_dir / "accounts" / f"{regular['id']}.json"
            has_account_file = account_path.exists()
            if has_account_file:
                account_file = read_json_or_default(account_path, None)
                fingerprint_id = account_file.get("fingerprint_id") if account_file else None

        if fingerprint_id is None:
            for fingerprint in fingerprints:
                if str(fingerprint.get("name", "")).lower() == email.lower():
                    fingerprint_id = fingerprint.get("id")
                    break

        has_codex_file = False
        if codex:
            codex_path = base_dir / "codex_accounts" / f"{codex['id']}.json"
            has_codex_file = codex_path.exists()

        rows.append(
            {
                "email": email,
                "account_id": regular.get("id") if regular else None,
                "codex_account_id": codex.get("id") if codex else None,
                "has_cockpit_index": regular is not None or codex is not None,
                "fingerprint_id": fingerprint_id,
                "has_account_file": has_account_file,
                "has_codex_file": has_codex_file,
            }
        )
    return rows


def export_accounts(base_dir: Path, emails: list[str], output_path: Path) -> OperationResult:
    accounts_index = read_json_or_default(base_dir / "accounts.json", {"version": "2.0", "accounts": []})
    codex_index = read_json_or_default(base_dir / "codex_accounts.json", {"version": "1.0", "accounts": []})
    fingerprints_index = read_json_or_default(base_dir / "fingerprints.json", {"fingerprints": []})

    accounts = to_mutable_list(accounts_index.get("accounts"))
    codex_accounts = to_mutable_list(codex_index.get("accounts"))
    fingerprints = to_mutable_list(fingerprints_index.get("fingerprints"))

    selected_emails: list[str] = []
    seen: set[str] = set()
    for email in emails:
        key = email.lower()
        if key not in seen:
            seen.add(key)
            selected_emails.append(email)

    regular_accounts: list[dict[str, Any]] = []
    codex_payloads: list[dict[str, Any]] = []
    warnings: list[str] = []

    for email in selected_emails:
        regular = find_by_email(accounts, email)
        codex = find_by_email(codex_accounts, email)
        if not regular and not codex:
            warnings.append(f"Email not found in accounts.json or codex_accounts.json: {email}")
            continue

        if regular:
            account_file_path = base_dir / "accounts" / f"{regular['id']}.json"
            if not account_file_path.exists():
                warnings.append(f"Missing account payload file for {email} at {account_file_path}")
            else:
                account_file = read_json_or_default(account_file_path, None)
                fingerprint = None
                fingerprint_id = account_file.get("fingerprint_id") if account_file else None
                if fingerprint_id:
                    fingerprint = find_by_id(fingerprints, fingerprint_id)
                    if not fingerprint:
                        warnings.append(f"Missing fingerprint entry {fingerprint_id} for {email}")
                regular_accounts.append({"index": regular, "file": account_file, "fingerprint": fingerprint})

        if codex:
            codex_file_path = base_dir / "codex_accounts" / f"{codex['id']}.json"
            if not codex_file_path.exists():
                warnings.append(f"Missing codex payload file for {email} at {codex_file_path}")
            else:
                codex_payloads.append({"index": codex, "file": read_json_or_default(codex_file_path, None)})

    package = {
        "version": 1,
        "package_type": "antigravity-account-migration",
        "created_at": now_iso(),
        "source_base_dir": str(base_dir),
        "selected_emails": selected_emails,
        "regular_accounts": regular_accounts,
        "codex_accounts": codex_payloads,
        "warnings": warnings,
    }
    write_json(output_path, package)
    details = [
        f"Package: {output_path}",
        f"Selected emails: {len(selected_emails)}",
        f"Regular accounts exported: {len(regular_accounts)}",
        f"Codex accounts exported: {len(codex_payloads)}",
    ]
    details.extend(f"Warning: {warning}" for warning in warnings)
    return OperationResult("Antigravity export completed.", details, output_path)


def import_accounts(base_dir: Path, package_path: Path, overwrite_existing_email: bool = False) -> OperationResult:
    package = read_json_or_default(package_path, None)
    if not package:
        raise TransferError(f"Package file is empty or invalid: {package_path}")
    if package.get("version") != 1:
        raise TransferError(f"Unsupported package version: {package.get('version')}")

    ensure_dir(base_dir)
    ensure_dir(base_dir / "accounts")
    ensure_dir(base_dir / "codex_accounts")
    backup_root = base_dir / f"migration-backup-import-{timestamp_slug()}"
    ensure_dir(backup_root)

    accounts_index_path = base_dir / "accounts.json"
    codex_index_path = base_dir / "codex_accounts.json"
    fingerprints_path = base_dir / "fingerprints.json"

    backup_if_exists(accounts_index_path, backup_root)
    backup_if_exists(codex_index_path, backup_root)
    backup_if_exists(fingerprints_path, backup_root)

    accounts_index = read_json_or_default(accounts_index_path, {"version": "2.0", "accounts": [], "current_account_id": None})
    codex_index = read_json_or_default(codex_index_path, {"version": "1.0", "accounts": [], "current_account_id": None})
    fingerprints_index = read_json_or_default(
        fingerprints_path,
        {"original_baseline": None, "current_fingerprint_id": None, "fingerprints": []},
    )

    accounts = to_mutable_list(accounts_index.get("accounts"))
    codex_accounts = to_mutable_list(codex_index.get("accounts"))
    fingerprints = to_mutable_list(fingerprints_index.get("fingerprints"))

    regular_by_email = {entry["index"]["email"].lower(): entry for entry in package.get("regular_accounts", []) if entry.get("index", {}).get("email")}
    codex_by_email = {entry["index"]["email"].lower(): entry for entry in package.get("codex_accounts", []) if entry.get("index", {}).get("email")}

    added: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for email in package.get("selected_emails", []):
        regular_entry = regular_by_email.get(email.lower())
        codex_entry = codex_by_email.get(email.lower())
        existing_regular = find_by_email(accounts, email)
        existing_codex = find_by_email(codex_accounts, email)
        skip_regular = bool(regular_entry and existing_regular and not overwrite_existing_email)
        skip_codex = bool(codex_entry and existing_codex and not overwrite_existing_email)

        if overwrite_existing_email:
            if regular_entry:
                for item in remove_entries_by_email(accounts, email):
                    payload_path = base_dir / "accounts" / f"{item['id']}.json"
                    backup_if_exists(payload_path, backup_root)
                    if payload_path.exists():
                        payload_path.unlink()
                fingerprints[:] = [item for item in fingerprints if str(item.get("name", "")).lower() != email.lower()]
            if codex_entry:
                for item in remove_entries_by_email(codex_accounts, email):
                    payload_path = base_dir / "codex_accounts" / f"{item['id']}.json"
                    backup_if_exists(payload_path, backup_root)
                    if payload_path.exists():
                        payload_path.unlink()

        if regular_entry and not skip_regular:
            conflict = find_by_id(accounts, regular_entry["index"]["id"])
            if conflict and str(conflict.get("email", "")).lower() != email.lower():
                raise TransferError(
                    f"Id conflict in accounts.json for id {regular_entry['index']['id']}: existing email {conflict.get('email')}, incoming email {email}"
                )
            account_file_path = base_dir / "accounts" / f"{regular_entry['index']['id']}.json"
            backup_if_exists(account_file_path, backup_root)
            write_json(account_file_path, regular_entry["file"])
            result = upsert_by_id(accounts, regular_entry["index"])
            (added if result == "added" else updated).append(f"regular:{email}")
            if regular_entry.get("fingerprint"):
                upsert_by_id(fingerprints, regular_entry["fingerprint"])
        elif skip_regular:
            skipped.append(f"regular:{email}")

        if codex_entry and not skip_codex:
            conflict = find_by_id(codex_accounts, codex_entry["index"]["id"])
            if conflict and str(conflict.get("email", "")).lower() != email.lower():
                raise TransferError(
                    f"Id conflict in codex_accounts.json for id {codex_entry['index']['id']}: existing email {conflict.get('email')}, incoming email {email}"
                )
            codex_file_path = base_dir / "codex_accounts" / f"{codex_entry['index']['id']}.json"
            backup_if_exists(codex_file_path, backup_root)
            write_json(codex_file_path, codex_entry["file"])
            result = upsert_by_id(codex_accounts, codex_entry["index"])
            (added if result == "added" else updated).append(f"codex:{email}")
        elif skip_codex:
            skipped.append(f"codex:{email}")

    accounts_index["accounts"] = accounts
    codex_index["accounts"] = codex_accounts
    fingerprints_index["fingerprints"] = fingerprints

    write_json(accounts_index_path, accounts_index)
    write_json(codex_index_path, codex_index)
    write_json(fingerprints_path, fingerprints_index)

    details = [
        f"Backup root: {backup_root}",
        f"Added entries: {len(added)}",
        f"Updated entries: {len(updated)}",
        f"Skipped emails: {len(skipped)}",
    ]
    details.extend(f"Skipped duplicate entry: {entry}" for entry in skipped)
    return OperationResult("Antigravity import completed.", details, backup_root)
