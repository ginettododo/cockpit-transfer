from __future__ import annotations

import argparse
from pathlib import Path

from .bundle import create_bundle, default_bundle_dir
from .fast_ops import export_fast, import_fast
from .multi_transfer import SUPPORTED_PRODUCTS, export_products, import_products, inspect_products


def _default_output_root() -> Path:
    downloads = Path.home() / "Downloads"
    return downloads if downloads.exists() else Path.home() / "Desktop"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="transferimento-cockpits")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--products", nargs="+", choices=SUPPORTED_PRODUCTS, required=True)
    inspect_parser.add_argument("--emails", nargs="*", default=[])
    inspect_parser.add_argument("--cockpit-dir", default=str(Path.home() / ".antigravity_cockpit"))
    inspect_parser.add_argument("--codex-dir", default=str(Path.home() / ".codex"))
    inspect_parser.add_argument("--gemini-dir", default=str(Path.home() / ".gemini"))

    export_parser = sub.add_parser("export")
    export_parser.add_argument("--products", nargs="+", choices=SUPPORTED_PRODUCTS, required=True)
    export_parser.add_argument("--emails", nargs="+", required=True)
    export_parser.add_argument("--out", required=True)
    export_parser.add_argument("--cockpit-dir", default=str(Path.home() / ".antigravity_cockpit"))
    export_parser.add_argument("--codex-dir", default=str(Path.home() / ".codex"))
    export_parser.add_argument("--gemini-dir", default=str(Path.home() / ".gemini"))

    import_parser = sub.add_parser("import-package")
    import_parser.add_argument("--package", required=True)
    import_parser.add_argument("--cockpit-dir", default=str(Path.home() / ".antigravity_cockpit"))
    import_parser.add_argument("--codex-dir", default=str(Path.home() / ".codex"))
    import_parser.add_argument("--gemini-dir", default=str(Path.home() / ".gemini"))
    import_parser.add_argument("--overwrite-existing-email", action="store_true")
    import_parser.add_argument("--codex-set-current-email", default="")
    import_parser.add_argument("--codex-activate-email", default="")
    import_parser.add_argument("--gemini-activate-email", default="")
    import_parser.add_argument("--force-stop-processes", action="store_true")
    import_parser.add_argument("--skip-process-check", action="store_true")

    bundle_parser = sub.add_parser("bundle")
    bundle_parser.add_argument("--products", nargs="+", choices=SUPPORTED_PRODUCTS, required=True)
    bundle_parser.add_argument("--emails", nargs="+", required=True)
    bundle_parser.add_argument("--output-dir", default="")
    bundle_parser.add_argument("--cockpit-dir", default=str(Path.home() / ".antigravity_cockpit"))
    bundle_parser.add_argument("--codex-dir", default=str(Path.home() / ".codex"))
    bundle_parser.add_argument("--gemini-dir", default=str(Path.home() / ".gemini"))
    bundle_parser.add_argument("--codex-set-current-email", default="")
    bundle_parser.add_argument("--codex-activate-email", default="")
    bundle_parser.add_argument("--gemini-activate-email", default="")

    export_fast_parser = sub.add_parser("export-fast")
    export_fast_parser.add_argument("--output-dir", default="")
    export_fast_parser.add_argument("--cockpit-dir", default=str(Path.home() / ".antigravity_cockpit"))
    export_fast_parser.add_argument("--codex-dir", default=str(Path.home() / ".codex"))
    export_fast_parser.add_argument("--gemini-dir", default=str(Path.home() / ".gemini"))
    export_fast_parser.add_argument("--dry-run", action="store_true")

    import_fast_parser = sub.add_parser("import-fast")
    import_fast_parser.add_argument("--package", default="")
    import_fast_parser.add_argument("--cockpit-dir", default=str(Path.home() / ".antigravity_cockpit"))
    import_fast_parser.add_argument("--codex-dir", default=str(Path.home() / ".codex"))
    import_fast_parser.add_argument("--gemini-dir", default=str(Path.home() / ".gemini"))
    import_fast_parser.add_argument("--overwrite-existing-email", action="store_true")
    import_fast_parser.add_argument("--force-stop-processes", action="store_true")
    import_fast_parser.add_argument("--no-restart-cockpit", action="store_true")
    import_fast_parser.add_argument("--dry-run", action="store_true")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cockpit_dir = Path(args.cockpit_dir)
    codex_dir = Path(args.codex_dir)
    gemini_dir = Path(args.gemini_dir)

    if args.command == "inspect":
        rows_by_product = inspect_products(args.products, cockpit_dir, codex_dir, gemini_dir, args.emails or None)
        for product, rows in rows_by_product.items():
            print(f"[{product}]")
            for row in rows:
                print(row)
        return 0

    if args.command == "export":
        result = export_products(args.products, args.emails, cockpit_dir, codex_dir, gemini_dir, Path(args.out))
        _print_result(result)
        return 0

    if args.command == "import-package":
        result = import_products(
            Path(args.package),
            cockpit_dir,
            codex_dir,
            gemini_dir,
            overwrite_existing_email=args.overwrite_existing_email,
            codex_set_current_email=args.codex_set_current_email or None,
            codex_activate_email=args.codex_activate_email or None,
            gemini_activate_email=args.gemini_activate_email or None,
            force_stop_processes=args.force_stop_processes,
            skip_process_check=args.skip_process_check,
        )
        _print_result(result)
        return 0

    if args.command == "bundle":
        output_dir = Path(args.output_dir) if args.output_dir else default_bundle_dir(_default_output_root(), "+".join(args.products), args.emails)
        package_path = output_dir / "transfer-package.json"
        export_result = export_products(args.products, args.emails, cockpit_dir, codex_dir, gemini_dir, package_path)
        bundle_result = create_bundle(
            package_path,
            output_dir,
            codex_set_current_email=args.codex_set_current_email or None,
            codex_activate_email=args.codex_activate_email or None,
            gemini_activate_email=args.gemini_activate_email or None,
        )
        _print_result(export_result)
        _print_result(bundle_result)
        return 0

    if args.command == "export-fast":
        result = export_fast(
            output_dir=Path(args.output_dir) if args.output_dir else None,
            cockpit_dir=cockpit_dir,
            codex_dir=codex_dir,
            gemini_dir=gemini_dir,
            dry_run=args.dry_run,
        )
        _print_result(result)
        return 0

    if args.command == "import-fast":
        overwrite_existing_email = True if args.overwrite_existing_email else None
        force_stop_processes = True if args.force_stop_processes else None
        result = import_fast(
            package_path=Path(args.package) if args.package else None,
            cockpit_dir=cockpit_dir,
            codex_dir=codex_dir,
            gemini_dir=gemini_dir,
            overwrite_existing_email=overwrite_existing_email,
            force_stop_processes=force_stop_processes,
            restart_cockpit=not args.no_restart_cockpit,
            dry_run=args.dry_run,
        )
        _print_result(result)
        return 0

    return 1


def _print_result(result) -> None:
    print(result.summary)
    for line in result.details:
        print(line)
