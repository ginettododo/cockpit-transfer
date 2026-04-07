from __future__ import annotations

import stat
import shutil
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

from .common import OperationResult, TransferError, ensure_dir, read_json_or_default, slugify, timestamp_slug


IMPORT_BUNDLE_SCRIPT = """from __future__ import annotations

import argparse
from pathlib import Path

from cockpit_transfer.multi_transfer import import_products


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", default="transfer-package.json")
    parser.add_argument("--codex-set-current-email", default="")
    parser.add_argument("--codex-activate-email", default="")
    parser.add_argument("--gemini-activate-email", default="")
    parser.add_argument("--overwrite-existing-email", action="store_true")
    parser.add_argument("--force-stop-processes", action="store_true")
    args = parser.parse_args()

    package_path = Path(args.package).resolve()
    result = import_products(
        package_path,
        Path.home() / ".antigravity_cockpit",
        Path.home() / ".codex",
        Path.home() / ".gemini",
        overwrite_existing_email=args.overwrite_existing_email,
        codex_set_current_email=args.codex_set_current_email or None,
        codex_activate_email=args.codex_activate_email or None,
        gemini_activate_email=args.gemini_activate_email or None,
        force_stop_processes=args.force_stop_processes,
    )

    print(result.summary)
    for line in result.details:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

UNIX_LAUNCHER_TEMPLATE = """#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$APP_DIR"

find_python() {
  for candidate in python3 python; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    if "$candidate" -c "import sys" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "Python 3 non trovato oppure non utilizzabile."
  echo "Su macOS installa Python.org o esegui manualmente con un interprete gia disponibile."
  exit 1
fi

exec "$PYTHON_BIN" __COMMAND__ "$@"
"""

MAC_RECOVERY_LAUNCHER_TEMPLATE = """#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$APP_DIR"

if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$APP_DIR" >/dev/null 2>&1 || true
fi

chmod +x ./*.command ./*.sh >/dev/null 2>&1 || true

find_python() {
  for candidate in python3 python; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    if "$candidate" -c "import sys" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "Python 3 non trovato oppure non utilizzabile."
  echo "Installa Python da python.org e riprova."
  exit 1
fi

exec "$PYTHON_BIN" __COMMAND__ "$@"
"""


def create_bundle(
    package_path: Path,
    output_dir: Path,
    codex_set_current_email: str | None = None,
    codex_activate_email: str | None = None,
    gemini_activate_email: str | None = None,
) -> OperationResult:
    package = read_json_or_default(package_path, None)
    if not package:
        raise ValueError(f"Invalid package: {package_path}")

    package_type = package.get("package_type", "")
    report = package.get("report") or {}
    ensure_dir(output_dir)
    target_package = output_dir / "transfer-package.json"
    if package_path.resolve() != target_package.resolve():
        shutil.copy2(package_path, target_package)

    source_pkg_dir = Path(__file__).resolve().parent
    target_pkg_dir = output_dir / "cockpit_transfer"
    if target_pkg_dir.exists():
        shutil.rmtree(target_pkg_dir)
    shutil.copytree(source_pkg_dir, target_pkg_dir)

    (output_dir / "import_bundle.py").write_text(IMPORT_BUNDLE_SCRIPT, encoding="utf-8")

    if package_type == "antigravity-account-migration":
        (output_dir / "1-import-antigravity-accounts.bat").write_text(
            _make_batch("python import_bundle.py --package transfer-package.json"),
            encoding="utf-8",
        )
        _write_unix_launcher(output_dir / "1-import-antigravity-accounts.command", "import_bundle.py --package transfer-package.json")
        _write_unix_launcher(output_dir / "1-import-antigravity-accounts.sh", "import_bundle.py --package transfer-package.json")
        _write_mac_recovery_launcher(output_dir / "0-mac-fix-permissions-and-import.command", "import_bundle.py --package transfer-package.json")
        readme_lines = [
            "This folder is ready to copy to the destination PC.",
            "",
            "Windows:",
            "1. Close Antigravity.",
            "2. Run 1-import-antigravity-accounts.bat.",
            "",
            "macOS / Linux:",
            "1. Close Antigravity.",
            "2. Preferred on macOS: run ./0-mac-fix-permissions-and-import.command",
            "3. Alternative: run ./1-import-antigravity-accounts.command or ./1-import-antigravity-accounts.sh.",
            "",
            "This package contains live credentials. Treat it like a password.",
        ]
    elif package_type == "codex-account-migration":
        base_command = "python import_bundle.py --package transfer-package.json"
        if codex_set_current_email:
            base_command += f' --codex-set-current-email "{codex_set_current_email}"'
        (output_dir / "1-import-into-cockpit-tools.bat").write_text(_make_batch(base_command), encoding="utf-8")
        _write_unix_launcher(output_dir / "1-import-into-cockpit-tools.command", _strip_python_prefix(base_command))
        _write_unix_launcher(output_dir / "1-import-into-cockpit-tools.sh", _strip_python_prefix(base_command))
        _write_mac_recovery_launcher(output_dir / "0-mac-fix-permissions-and-import.command", _strip_python_prefix(base_command))
        readme_lines = [
            "This folder is ready to copy to the destination PC.",
            "",
            "Windows:",
            "1. Close Cockpit Tools.",
            "2. Run 1-import-into-cockpit-tools.bat.",
            "",
            "macOS / Linux:",
            "1. Close Cockpit Tools.",
            "2. Preferred on macOS: run ./0-mac-fix-permissions-and-import.command",
            "3. Alternative: run ./1-import-into-cockpit-tools.command or ./1-import-into-cockpit-tools.sh.",
        ]
        if codex_activate_email:
            activate_command = base_command + f' --codex-activate-email "{codex_activate_email}" --force-stop-processes'
            (output_dir / "2-import-and-activate-codex.bat").write_text(_make_batch(activate_command), encoding="utf-8")
            _write_unix_launcher(output_dir / "2-import-and-activate-codex.command", _strip_python_prefix(activate_command))
            _write_unix_launcher(output_dir / "2-import-and-activate-codex.sh", _strip_python_prefix(activate_command))
            readme_lines.append("Windows: if you want the same email active in Codex desktop too, run 2-import-and-activate-codex.bat.")
            readme_lines.append("macOS / Linux: if you want the same email active locally too, run ./2-import-and-activate-codex.command or ./2-import-and-activate-codex.sh.")
        readme_lines.extend(["", "This package contains live credentials. Treat it like a password."])
    elif package_type == "gemini-account-migration":
        base_command = "python import_bundle.py --package transfer-package.json"
        (output_dir / "1-import-gemini-into-cockpit-tools.bat").write_text(_make_batch(base_command), encoding="utf-8")
        _write_unix_launcher(output_dir / "1-import-gemini-into-cockpit-tools.command", _strip_python_prefix(base_command))
        _write_unix_launcher(output_dir / "1-import-gemini-into-cockpit-tools.sh", _strip_python_prefix(base_command))
        _write_mac_recovery_launcher(output_dir / "0-mac-fix-permissions-and-import.command", _strip_python_prefix(base_command))
        readme_lines = [
            "This folder is ready to copy to the destination PC.",
            "",
            "Windows:",
            "1. Close Cockpit Tools.",
            "2. Run 1-import-gemini-into-cockpit-tools.bat.",
            "",
            "macOS / Linux:",
            "1. Close Cockpit Tools.",
            "2. Preferred on macOS: run ./0-mac-fix-permissions-and-import.command",
            "3. Alternative: run ./1-import-gemini-into-cockpit-tools.command or ./1-import-gemini-into-cockpit-tools.sh.",
        ]
        if gemini_activate_email:
            activate_command = base_command + f' --gemini-activate-email "{gemini_activate_email}"'
            (output_dir / "2-import-and-activate-gemini.bat").write_text(_make_batch(activate_command), encoding="utf-8")
            _write_unix_launcher(output_dir / "2-import-and-activate-gemini.command", _strip_python_prefix(activate_command))
            _write_unix_launcher(output_dir / "2-import-and-activate-gemini.sh", _strip_python_prefix(activate_command))
            readme_lines.append("Windows: if you want the same email active in Gemini local too, run 2-import-and-activate-gemini.bat.")
            readme_lines.append("macOS / Linux: if you want the same email active locally too, run ./2-import-and-activate-gemini.command or ./2-import-and-activate-gemini.sh.")
        readme_lines.extend(["", "This package contains live credentials. Treat it like a password."])
    elif package_type == "multi-cockpit-transfer":
        base_command = "python import_bundle.py --package transfer-package.json"
        if codex_set_current_email:
            base_command += f' --codex-set-current-email "{codex_set_current_email}"'
        (output_dir / "1-import-selected-products.bat").write_text(_make_batch(base_command), encoding="utf-8")
        _write_unix_launcher(output_dir / "1-import-selected-products.command", _strip_python_prefix(base_command))
        _write_unix_launcher(output_dir / "1-import-selected-products.sh", _strip_python_prefix(base_command))
        _write_mac_recovery_launcher(output_dir / "0-mac-fix-permissions-and-import.command", _strip_python_prefix(base_command))
        readme_lines = [
            "This folder is ready to copy to the destination PC.",
            "",
            "Windows:",
            "1. Close Cockpit Tools and Antigravity if they are open.",
            "2. Run 1-import-selected-products.bat.",
            "",
            "macOS / Linux:",
            "1. Close Cockpit Tools and Antigravity if they are open.",
            "2. Preferred on macOS: run ./0-mac-fix-permissions-and-import.command",
            "3. Alternative: run ./1-import-selected-products.command or ./1-import-selected-products.sh.",
        ]
        if codex_activate_email or gemini_activate_email:
            activate_command = base_command
            if codex_activate_email:
                activate_command += f' --codex-activate-email "{codex_activate_email}" --force-stop-processes'
            if gemini_activate_email:
                activate_command += f' --gemini-activate-email "{gemini_activate_email}"'
            (output_dir / "2-import-and-activate-local-profiles.bat").write_text(_make_batch(activate_command), encoding="utf-8")
            _write_unix_launcher(output_dir / "2-import-and-activate-local-profiles.command", _strip_python_prefix(activate_command))
            _write_unix_launcher(output_dir / "2-import-and-activate-local-profiles.sh", _strip_python_prefix(activate_command))
            readme_lines.append("Windows: if you also want local profiles activated, run 2-import-and-activate-local-profiles.bat.")
            readme_lines.append("macOS / Linux: if you also want local profiles activated, run ./2-import-and-activate-local-profiles.command or ./2-import-and-activate-local-profiles.sh.")
        readme_lines.extend(["", "This package contains live credentials. Treat it like a password."])
    else:
        raise ValueError(f"Unsupported package type for bundle: {package_type}")

    summary_lines = ["EXPORT SUMMARY", ""]
    if package_type == "multi-cockpit-transfer" and report:
        for product in package.get("products", []):
            product_report = report.get(product, {})
            summary_lines.append(
                f"{product}: found {product_report.get('found_count', 0)} / {product_report.get('selected_count', 0)}, missing {product_report.get('missing_count', 0)}"
            )
            missing = product_report.get("missing_emails") or []
            if missing:
                summary_lines.append(f"Missing: {', '.join(missing)}")
            summary_lines.append("")
    (output_dir / "EXPORT_SUMMARY.txt").write_text("\n".join(summary_lines).strip() + "\n", encoding="utf-8")

    (output_dir / "README.txt").write_text("\n".join(readme_lines), encoding="utf-8")
    details = [
        f"Bundle folder: {output_dir}",
        f"Package copied as: {target_package}",
        f"Bundle type: {package_type}",
    ]
    return OperationResult("Transfer bundle created.", details, output_dir)


def create_bundle_zip(
    package_path: Path,
    archive_path: Path,
    codex_set_current_email: str | None = None,
    codex_activate_email: str | None = None,
    gemini_activate_email: str | None = None,
) -> OperationResult:
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp) / "bundle"
        bundle_result = create_bundle(
            package_path,
            temp_dir,
            codex_set_current_email=codex_set_current_email,
            codex_activate_email=codex_activate_email,
            gemini_activate_email=gemini_activate_email,
        )
        ensure_dir(archive_path.parent)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in temp_dir.rglob("*"):
                if path.is_file():
                    _write_zip_entry(zf, path, path.relative_to(temp_dir))
    details = [f"ZIP: {archive_path}", *bundle_result.details]
    return OperationResult("ZIP trasferibile creato.", details, archive_path)


def extract_zip_to_temp(zip_path: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp_dir = tempfile.TemporaryDirectory()
    root = Path(temp_dir.name)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            relative_path = _normalize_zip_member_name(info.filename)
            if relative_path is None:
                continue
            target_path = root.joinpath(*relative_path.parts)
            ensure_dir(target_path.parent)
            if info.is_dir():
                ensure_dir(target_path)
                continue
            with zf.open(info, "r") as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)
    return temp_dir, _locate_transfer_package(root, zip_path)


def default_bundle_dir(base_dir: Path, product: str, emails: list[str]) -> Path:
    slug = "__".join(slugify(email) for email in emails) or product
    return base_dir / f"{product}-transfer-{slug}-{timestamp_slug()}"


def _make_batch(command: str) -> str:
    py_command = command[7:] if command.startswith("python ") else command
    return (
        "@echo off\n"
        "setlocal\n"
        "set SCRIPT_DIR=%~dp0\n"
        "pushd \"%SCRIPT_DIR%\"\n"
        "where py >nul 2>nul\n"
        "if %ERRORLEVEL%==0 (\n"
        f"  py -3 {py_command}\n"
        ") else (\n"
        f"  {command}\n"
        ")\n"
        "echo.\n"
        "pause\n"
        "popd\n"
    )


def _strip_python_prefix(command: str) -> str:
    return command[7:] if command.startswith("python ") else command


def _write_unix_launcher(path: Path, command: str) -> None:
    content = UNIX_LAUNCHER_TEMPLATE.replace("__COMMAND__", command)
    path.write_text(content, encoding="utf-8", newline="\n")
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_mac_recovery_launcher(path: Path, command: str) -> None:
    content = MAC_RECOVERY_LAUNCHER_TEMPLATE.replace("__COMMAND__", command)
    path.write_text(content, encoding="utf-8", newline="\n")
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_zip_entry(zf: zipfile.ZipFile, source_path: Path, archive_name: Path) -> None:
    info = zipfile.ZipInfo.from_file(source_path, arcname=str(archive_name).replace("\\", "/"))
    info.compress_type = zipfile.ZIP_DEFLATED

    if source_path.suffix.lower() in {".command", ".sh"}:
        info.create_system = 3
        info.external_attr = ((stat.S_IFREG | 0o755) << 16)

    with source_path.open("rb") as handle:
        zf.writestr(info, handle.read())


def _normalize_zip_member_name(name: str) -> PurePosixPath | None:
    normalized = PurePosixPath(str(name).replace("\\", "/"))
    parts = [part for part in normalized.parts if part not in ("", ".")]
    if not parts:
        return None
    if parts[0].endswith(":") or parts[0].startswith("/"):
        raise TransferError(f"ZIP entry non supportata: {name}")
    if any(part == ".." for part in parts):
        raise TransferError(f"ZIP entry non sicura: {name}")
    if parts[0] == "__MACOSX":
        return None
    if parts[-1] == ".DS_Store" or parts[-1].startswith("._"):
        return None
    return PurePosixPath(*parts)


def _locate_transfer_package(root: Path, zip_path: Path) -> Path:
    candidates = [
        path
        for path in root.rglob("transfer-package.json")
        if path.is_file() and "__MACOSX" not in path.parts
    ]
    if not candidates:
        raise TransferError(f"Lo ZIP non contiene transfer-package.json: {zip_path}")
    return min(candidates, key=lambda path: (len(path.relative_to(root).parts), str(path).lower()))
