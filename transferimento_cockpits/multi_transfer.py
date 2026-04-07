from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from . import antigravity, codex, gemini
from .common import OperationResult, TransferError, now_iso, read_json_or_default, write_json

SUPPORTED_PRODUCTS = ("antigravity", "codex", "gemini")


def _inspect_product(product: str, cockpit_base_dir: Path, codex_base_dir: Path, gemini_base_dir: Path, emails: list[str] | None) -> list[dict[str, Any]]:
    if product == "antigravity":
        return antigravity.inspect_accounts(cockpit_base_dir, emails)
    if product == "codex":
        return codex.inspect_accounts(cockpit_base_dir, codex_base_dir, emails)
    if product == "gemini":
        return gemini.inspect_accounts(cockpit_base_dir, gemini_base_dir, emails)
    raise TransferError(f"Unsupported product: {product}")


def _export_product(
    product: str,
    cockpit_base_dir: Path,
    codex_base_dir: Path,
    gemini_base_dir: Path,
    emails: list[str],
    output_path: Path,
) -> OperationResult:
    if product == "antigravity":
        return antigravity.export_accounts(cockpit_base_dir, emails, output_path)
    if product == "codex":
        return codex.export_accounts(cockpit_base_dir, codex_base_dir, emails, output_path)
    if product == "gemini":
        return gemini.export_accounts(cockpit_base_dir, gemini_base_dir, emails, output_path)
    raise TransferError(f"Unsupported product: {product}")


def _import_product(
    product: str,
    package_path: Path,
    cockpit_base_dir: Path,
    codex_base_dir: Path,
    gemini_base_dir: Path,
    overwrite_existing_email: bool,
    codex_set_current_email: str | None,
    codex_activate_email: str | None,
    gemini_activate_email: str | None,
    force_stop_processes: bool,
    skip_process_check: bool,
) -> OperationResult:
    if product == "antigravity":
        return antigravity.import_accounts(cockpit_base_dir, package_path, overwrite_existing_email)
    if product == "codex":
        return codex.import_accounts(
            cockpit_base_dir,
            codex_base_dir,
            package_path,
            overwrite_existing_email=overwrite_existing_email,
            set_current_email=codex_set_current_email,
            activate_email=codex_activate_email,
            force_stop_processes=force_stop_processes,
            skip_process_check=skip_process_check,
        )
    if product == "gemini":
        return gemini.import_accounts(
            cockpit_base_dir,
            gemini_base_dir,
            package_path,
            overwrite_existing_email=overwrite_existing_email,
            activate_email=gemini_activate_email,
        )
    raise TransferError(f"Unsupported product: {product}")


def _build_export_report(product: str, subpackage: dict[str, Any], selected_emails: list[str]) -> dict[str, Any]:
    selected_lower = {email.lower(): email for email in selected_emails}

    if product == "codex":
        found_emails = [entry["index"]["email"] for entry in subpackage.get("cockpit_codex_accounts", []) if entry.get("index", {}).get("email")]
    elif product == "gemini":
        found_emails = [entry["index"]["email"] for entry in subpackage.get("cockpit_gemini_accounts", []) if entry.get("index", {}).get("email")]
    elif product == "antigravity":
        found_set: dict[str, str] = {}
        for entry in subpackage.get("regular_accounts", []):
            email = entry.get("index", {}).get("email")
            if email:
                found_set[email.lower()] = email
        for entry in subpackage.get("codex_accounts", []):
            email = entry.get("index", {}).get("email")
            if email:
                found_set[email.lower()] = email
        found_emails = list(found_set.values())
    else:
        raise TransferError(f"Unsupported product: {product}")

    found_lower = {email.lower() for email in found_emails}
    missing_emails = [original for lower, original in selected_lower.items() if lower not in found_lower]

    return {
        "product": product,
        "selected_count": len(selected_emails),
        "found_count": len(found_emails),
        "missing_count": len(missing_emails),
        "found_emails": found_emails,
        "missing_emails": missing_emails,
    }


def inspect_products(
    products: list[str],
    cockpit_base_dir: Path,
    codex_base_dir: Path,
    gemini_base_dir: Path,
    emails: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        result[product] = _inspect_product(product, cockpit_base_dir, codex_base_dir, gemini_base_dir, emails)
    return result


def product_row_is_registered(product: str, row: dict[str, Any]) -> bool:
    if product == "antigravity":
        return bool(row.get("has_cockpit_index")) or bool(row.get("account_id")) or bool(row.get("codex_account_id"))
    return bool(row.get("has_cockpit_index"))


def summarize_unique_emails(rows_by_product: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}

    for product, rows in rows_by_product.items():
        for row in rows:
            email = str(row.get("email", "")).strip()
            if not email:
                continue

            key = email.lower()
            entry = combined.setdefault(
                key,
                {
                    "email": email,
                    "codex_registered": False,
                    "gemini_registered": False,
                    "antigravity_registered": False,
                    "notes": [],
                },
            )

            if product == "codex":
                entry["codex_registered"] = entry["codex_registered"] or product_row_is_registered(product, row)
                if row.get("is_current_in_cockpit"):
                    entry["notes"].append("Codex corrente in Cockpit")
                if row.get("is_active_codex_profile"):
                    entry["notes"].append("Profilo .codex attivo")
            elif product == "gemini":
                entry["gemini_registered"] = entry["gemini_registered"] or product_row_is_registered(product, row)
                if row.get("is_active_gemini_profile"):
                    entry["notes"].append("Profilo .gemini attivo")
            elif product == "antigravity":
                entry["antigravity_registered"] = entry["antigravity_registered"] or product_row_is_registered(product, row)

    rows: list[dict[str, Any]] = []
    for entry in combined.values():
        unique_notes: list[str] = []
        seen_notes: set[str] = set()
        for note in entry["notes"]:
            if note not in seen_notes:
                seen_notes.add(note)
                unique_notes.append(note)
        rows.append(
            {
                "email": entry["email"],
                "codex_registered": bool(entry["codex_registered"]),
                "gemini_registered": bool(entry["gemini_registered"]),
                "antigravity_registered": bool(entry["antigravity_registered"]),
                "registered_count": sum(
                    1
                    for flag in (
                        entry["codex_registered"],
                        entry["gemini_registered"],
                        entry["antigravity_registered"],
                    )
                    if flag
                ),
                "notes": ", ".join(unique_notes),
            }
        )

    rows.sort(key=lambda item: str(item["email"]).lower())
    return rows


def build_package_preview(package: dict[str, Any] | None) -> list[str]:
    if not package:
        return ["Nessuna anteprima disponibile."]

    package_type = str(package.get("package_type", "")).strip() or "sconosciuto"
    products = [str(item) for item in package.get("products", []) if item]
    selected_emails = [str(item) for item in (package.get("emails") or package.get("selected_emails") or []) if item]
    report = package.get("report") or {}

    if not products:
        if package_type == "antigravity-account-migration":
            products = ["antigravity"]
        elif package_type == "codex-account-migration":
            products = ["codex"]
        elif package_type == "gemini-account-migration":
            products = ["gemini"]

    lines = [f"Formato: {package_type}"]
    if products:
        lines.append("Provider: " + ", ".join(product.capitalize() for product in products))
    lines.append(f"Email incluse: {len(selected_emails)}")
    if selected_emails:
        preview_emails = selected_emails[:8]
        extra = len(selected_emails) - len(preview_emails)
        lines.append("Mail: " + ", ".join(preview_emails) + (f" (+{extra})" if extra > 0 else ""))

    if package_type == "multi-cockpit-transfer" and report:
        lines.append("")
        lines.append("Riepilogo provider:")
        for product in products:
            product_report = report.get(product) or {}
            lines.append(
                f"- {product.capitalize()}: trovate {product_report.get('found_count', 0)} su {product_report.get('selected_count', 0)}, mancanti {product_report.get('missing_count', 0)}"
            )
    else:
        active_profiles = package.get("active_profiles") or []
        if active_profiles:
            lines.append(f"Profili locali inclusi: {len(active_profiles)}")

    return lines


def export_products(
    products: list[str],
    emails: list[str],
    cockpit_base_dir: Path,
    codex_base_dir: Path,
    gemini_base_dir: Path,
    output_path: Path,
) -> OperationResult:
    if not products:
        raise TransferError("Select at least one product.")

    export_details: list[str] = []
    payload: dict[str, Any] = {}
    report: dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        for product in products:
            subpackage_path = tmp_root / f"{product}.json"
            result = _export_product(product, cockpit_base_dir, codex_base_dir, gemini_base_dir, emails, subpackage_path)
            subpackage = read_json_or_default(subpackage_path, None)
            payload[product] = subpackage
            report[product] = _build_export_report(product, subpackage, emails)
            export_details.append(f"[{product}] {result.summary}")
            export_details.append(
                f"[{product}] trovate {report[product]['found_count']} email, mancanti {report[product]['missing_count']}"
            )
            if report[product]["missing_emails"]:
                export_details.append(f"[{product}] mancanti: {', '.join(report[product]['missing_emails'])}")
            export_details.extend(f"[{product}] {line}" for line in result.details)

    package = {
        "version": 1,
        "package_type": "multi-cockpit-transfer",
        "created_at": now_iso(),
        "products": products,
        "emails": emails,
        "report": report,
        "payloads": payload,
    }
    write_json(output_path, package)
    return OperationResult("Export multiprodotto completato.", [f"Package: {output_path}", *export_details], output_path)


def import_products(
    package_path: Path,
    cockpit_base_dir: Path,
    codex_base_dir: Path,
    gemini_base_dir: Path,
    overwrite_existing_email: bool = False,
    codex_set_current_email: str | None = None,
    codex_activate_email: str | None = None,
    gemini_activate_email: str | None = None,
    force_stop_processes: bool = False,
    skip_process_check: bool = False,
) -> OperationResult:
    package = read_json_or_default(package_path, None)
    if not package:
        raise TransferError(f"Package file is empty or invalid: {package_path}")

    package_type = package.get("package_type")
    details: list[str] = []

    if package_type == "antigravity-account-migration":
        return _import_product(
            "antigravity",
            package_path,
            cockpit_base_dir,
            codex_base_dir,
            gemini_base_dir,
            overwrite_existing_email,
            codex_set_current_email,
            codex_activate_email,
            gemini_activate_email,
            force_stop_processes,
            skip_process_check,
        )
    if package_type == "codex-account-migration":
        return _import_product(
            "codex",
            package_path,
            cockpit_base_dir,
            codex_base_dir,
            gemini_base_dir,
            overwrite_existing_email,
            codex_set_current_email,
            codex_activate_email,
            gemini_activate_email,
            force_stop_processes,
            skip_process_check,
        )
    if package_type == "gemini-account-migration":
        return _import_product(
            "gemini",
            package_path,
            cockpit_base_dir,
            codex_base_dir,
            gemini_base_dir,
            overwrite_existing_email,
            codex_set_current_email,
            codex_activate_email,
            gemini_activate_email,
            force_stop_processes,
            skip_process_check,
        )
    if package_type != "multi-cockpit-transfer":
        raise TransferError(f"Unsupported package format in {package_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        for product in package.get("products", []):
            payload = package.get("payloads", {}).get(product)
            if not payload:
                continue
            subpackage_path = tmp_root / f"{product}.json"
            write_json(subpackage_path, payload)
            result = _import_product(
                product,
                subpackage_path,
                cockpit_base_dir,
                codex_base_dir,
                gemini_base_dir,
                overwrite_existing_email,
                codex_set_current_email,
                codex_activate_email,
                gemini_activate_email,
                force_stop_processes,
                skip_process_check,
            )
            details.append(f"[{product}] {result.summary}")
            details.extend(f"[{product}] {line}" for line in result.details)

    return OperationResult("Import multiprodotto completato.", details, package_path)
