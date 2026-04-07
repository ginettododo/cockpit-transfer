from __future__ import annotations

import tempfile
from pathlib import Path

from .bundle import create_bundle_zip, extract_zip_to_temp
from .common import OperationResult, TransferError, read_json_or_default
from .multi_transfer import build_package_preview, export_products, import_products, inspect_products, summarize_unique_emails
from .runtime_support import (
    FAST_PRODUCTS,
    default_cockpit_dir,
    default_codex_dir,
    default_downloads_dir,
    default_gemini_dir,
    default_zip_name,
    latest_zip_in_dir,
    load_runtime_state,
    restart_cockpit_if_possible,
    save_runtime_state,
)


def collect_all_emails(
    cockpit_dir: Path | None = None,
    codex_dir: Path | None = None,
    gemini_dir: Path | None = None,
    products: list[str] | None = None,
) -> list[str]:
    selected_products = list(products or FAST_PRODUCTS)
    rows_by_product = inspect_products(
        selected_products,
        cockpit_dir or default_cockpit_dir(),
        codex_dir or default_codex_dir(),
        gemini_dir or default_gemini_dir(),
        None,
    )
    return [str(row["email"]) for row in summarize_unique_emails(rows_by_product) if row.get("email")]


def export_fast(
    output_dir: Path | None = None,
    cockpit_dir: Path | None = None,
    codex_dir: Path | None = None,
    gemini_dir: Path | None = None,
    dry_run: bool = False,
) -> OperationResult:
    state = load_runtime_state()
    selected_products = list(FAST_PRODUCTS)
    emails = collect_all_emails(cockpit_dir, codex_dir, gemini_dir, selected_products)
    if not emails:
        raise TransferError("Non ho trovato email esportabili sui provider configurati.")

    final_output_dir = Path(output_dir or state.get("output_dir") or default_downloads_dir())
    archive_path = final_output_dir / default_zip_name(selected_products, emails)

    details = [
        f"Provider inclusi: {', '.join(selected_products)}",
        f"Email trovate: {len(emails)}",
        f"ZIP destinazione: {archive_path}",
    ]
    if emails:
        details.append("Prime email: " + ", ".join(emails[:8]) + (f" (+{len(emails) - 8})" if len(emails) > 8 else ""))

    if dry_run:
        return OperationResult("Export rapido simulato.", details, archive_path)

    with tempfile.TemporaryDirectory() as tmp:
        package_path = Path(tmp) / "transfer-package.json"
        export_result = export_products(
            selected_products,
            emails,
            cockpit_dir or default_cockpit_dir(),
            codex_dir or default_codex_dir(),
            gemini_dir or default_gemini_dir(),
            package_path,
        )
        zip_result = create_bundle_zip(package_path, archive_path)

    state["export_products"] = selected_products
    state["last_emails"] = emails
    state["output_dir"] = str(final_output_dir)
    state["last_package_path"] = str(archive_path)
    save_runtime_state(state)

    return OperationResult(
        "Export rapido completato.",
        [*details, *export_result.details, *zip_result.details],
        archive_path,
    )


def resolve_import_fast_package(package_path: Path | None = None) -> Path:
    if package_path:
        return package_path

    state = load_runtime_state()
    latest_download_zip = latest_zip_in_dir(default_downloads_dir())
    if latest_download_zip:
        return latest_download_zip

    saved_package = str(state.get("last_package_path", "")).strip()
    if saved_package:
        saved_path = Path(saved_package)
        if saved_path.exists():
            return saved_path

    raise TransferError("Non trovo ZIP recenti in Downloads e non c'e' un ultimo file valido salvato.")


def import_fast(
    package_path: Path | None = None,
    cockpit_dir: Path | None = None,
    codex_dir: Path | None = None,
    gemini_dir: Path | None = None,
    overwrite_existing_email: bool | None = None,
    force_stop_processes: bool | None = None,
    restart_cockpit: bool = True,
    dry_run: bool = False,
) -> OperationResult:
    state = load_runtime_state()
    selected_package = resolve_import_fast_package(package_path).resolve()
    if not selected_package.exists():
        raise TransferError(f"File non trovato: {selected_package}")

    overwrite = state.get("overwrite_existing_email", False) if overwrite_existing_email is None else overwrite_existing_email
    force_stop = state.get("force_stop_processes", True) if force_stop_processes is None else force_stop_processes
    details = [f"File sorgente: {selected_package}"]

    if dry_run:
        if selected_package.suffix.lower() == ".zip":
            temp_dir, extracted_package = extract_zip_to_temp(selected_package)
            try:
                package_data = read_json_or_default(extracted_package, None)
            finally:
                temp_dir.cleanup()
        else:
            package_data = read_json_or_default(selected_package, None)
        details.extend(build_package_preview(package_data))
        if restart_cockpit:
            details.append("Riavvio Cockpit previsto a fine import.")
        return OperationResult("Import rapido simulato.", details, selected_package)

    if selected_package.suffix.lower() == ".zip":
        temp_dir, extracted_package = extract_zip_to_temp(selected_package)
        try:
            result = import_products(
                extracted_package,
                cockpit_dir or default_cockpit_dir(),
                codex_dir or default_codex_dir(),
                gemini_dir or default_gemini_dir(),
                overwrite_existing_email=bool(overwrite),
                codex_set_current_email=str(state.get("codex_set_current_email", "")).strip() or None,
                codex_activate_email=str(state.get("codex_activate_email", "")).strip() or None,
                gemini_activate_email=str(state.get("gemini_activate_email", "")).strip() or None,
                force_stop_processes=bool(force_stop),
            )
        finally:
            temp_dir.cleanup()
    else:
        result = import_products(
            selected_package,
            cockpit_dir or default_cockpit_dir(),
            codex_dir or default_codex_dir(),
            gemini_dir or default_gemini_dir(),
            overwrite_existing_email=bool(overwrite),
            codex_set_current_email=str(state.get("codex_set_current_email", "")).strip() or None,
            codex_activate_email=str(state.get("codex_activate_email", "")).strip() or None,
            gemini_activate_email=str(state.get("gemini_activate_email", "")).strip() or None,
            force_stop_processes=bool(force_stop),
        )

    if restart_cockpit:
        restart_target = restart_cockpit_if_possible()
        if restart_target:
            details.append(f"Cockpit riavviato automaticamente: {restart_target}")
        else:
            details.append("Riavvio automatico Cockpit non disponibile: launcher non trovato.")

    state["last_package_path"] = str(selected_package)
    save_runtime_state(state)

    return OperationResult("Import rapido completato.", [*details, *result.details], selected_package)
