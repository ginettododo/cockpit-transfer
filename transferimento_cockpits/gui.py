from __future__ import annotations

from datetime import datetime
import tempfile
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .app_state import DEFAULT_EXPORT_PRODUCTS, DEFAULT_INSPECT_PRODUCTS, load_app_state, save_app_state
from .bundle import create_bundle_zip, extract_zip_to_temp
from .common import OperationResult
from .common import read_json_or_default
from .multi_transfer import build_package_preview, import_products, inspect_products, summarize_unique_emails
from .runtime_support import default_downloads_dir, default_zip_name, latest_zip_in_dir, restart_cockpit_if_possible


class TransferApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Transferimento Cockpits")
        self.root.geometry("980x720")
        self.root.minsize(900, 640)
        self.app_dir = Path(__file__).resolve().parent.parent
        self.state_path = self.app_dir / "app_state.json"
        self.state = load_app_state(self.state_path, str(default_downloads_dir()))

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.cockpit_dir_var = tk.StringVar(value=str(Path.home() / ".antigravity_cockpit"))
        self.codex_dir_var = tk.StringVar(value=str(Path.home() / ".codex"))
        self.gemini_dir_var = tk.StringVar(value=str(Path.home() / ".gemini"))
        self.output_dir_var = tk.StringVar(value=str(self.state.get("output_dir", default_downloads_dir())))
        self.package_var = tk.StringVar(value=str(self.state.get("last_package_path", "")))

        self.export_product_vars = {
            "codex": tk.BooleanVar(value="codex" in self.state.get("export_products", [])),
            "gemini": tk.BooleanVar(value="gemini" in self.state.get("export_products", [])),
            "antigravity": tk.BooleanVar(value="antigravity" in self.state.get("export_products", [])),
        }
        self.inspect_product_vars = {
            "codex": tk.BooleanVar(value="codex" in self.state.get("inspect_products", [])),
            "gemini": tk.BooleanVar(value="gemini" in self.state.get("inspect_products", [])),
            "antigravity": tk.BooleanVar(value="antigravity" in self.state.get("inspect_products", [])),
        }
        self.overwrite_var = tk.BooleanVar(value=bool(self.state.get("overwrite_existing_email", False)))
        self.force_stop_var = tk.BooleanVar(value=bool(self.state.get("force_stop_processes", True)))
        self.codex_set_current_email_var = tk.StringVar(value=str(self.state.get("codex_set_current_email", "")))
        self.codex_activate_email_var = tk.StringVar(value=str(self.state.get("codex_activate_email", "")))
        self.gemini_activate_email_var = tk.StringVar(value=str(self.state.get("gemini_activate_email", "")))
        self.status_var = tk.StringVar(value="Pronto")

        self.inspect_tree: ttk.Treeview | None = None
        self.inspect_tree_mode = "provider"
        self.inspect_email_column = 1
        self.inspect_filter_var = tk.StringVar()
        self.inspect_hint_var = tk.StringVar(
            value="Controlla le mail trovate e, se vuoi, mandale direttamente al tab Trasferisci. Doppio click su una riga = usa in export."
        )
        self.inspect_meta_var = tk.StringVar(value="Nessun controllo eseguito.")
        self.inspect_unique_rows_cache: list[dict[str, object]] = []
        self.import_preview_text: tk.Text | None = None
        self.log_text: tk.Text | None = None
        self.email_text: tk.Text | None = None
        self.notebook: ttk.Notebook | None = None
        self.summary_var = tk.StringVar(value="Inserisci una o piu email e scegli cosa esportare.")
        self._build()
        self.inspect_filter_var.trace_add("write", self._on_inspect_filter_changed)
        self.package_var.trace_add("write", self._on_package_path_changed)
        self._restore_last_emails()
        self._ensure_default_provider_selection()
        self._update_summary()
        self._refresh_import_preview()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Transferimento Cockpits", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Scegli le email, crea uno ZIP unico, importalo sull'altro PC.",
            wraplength=820,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        summary = ttk.LabelFrame(outer, text="Riepilogo", padding=10)
        summary.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        summary.columnconfigure(0, weight=1)
        ttk.Label(summary, textvariable=self.summary_var, wraplength=840, justify="left").grid(row=0, column=0, sticky="w")

        notebook = ttk.Notebook(outer)
        self.notebook = notebook
        notebook.grid(row=2, column=0, sticky="nsew")
        outer.rowconfigure(2, weight=1)

        transfer_tab = ttk.Frame(notebook, padding=12)
        inspect_tab = ttk.Frame(notebook, padding=12)
        advanced_tab = ttk.Frame(notebook, padding=12)
        log_tab = ttk.Frame(notebook, padding=12)

        notebook.add(transfer_tab, text="Trasferisci")
        notebook.add(inspect_tab, text="Controllo")
        notebook.add(advanced_tab, text="Opzioni")
        notebook.add(log_tab, text="Log")

        self._build_transfer_tab(transfer_tab)
        self._build_inspect_tab(inspect_tab)
        self._build_advanced_tab(advanced_tab)
        self._build_log_tab(log_tab)

        footer = ttk.Frame(outer)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(1, weight=1)
        ttk.Button(footer, text="Pulisci log", command=self._clear_log).grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.status_var, relief="sunken", anchor="w", padding=6).grid(row=0, column=1, sticky="ew", padx=(10, 0))

    def _build_transfer_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        export_panel = ttk.LabelFrame(parent, text="Esporta", padding=10)
        export_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        export_panel.columnconfigure(0, weight=1)
        export_panel.rowconfigure(1, weight=1)
        ttk.Label(
            export_panel,
            text="Scegli le mail da trasferire oppure mandale qui dal tab Controllo.",
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        export_body = ttk.Frame(export_panel)
        export_body.grid(row=1, column=0, sticky="nsew")
        export_body.columnconfigure(0, weight=1)
        export_body.rowconfigure(0, weight=1)
        self._build_export_tab(export_body)

        import_panel = ttk.LabelFrame(parent, text="Importa", padding=10)
        import_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        import_panel.columnconfigure(0, weight=1)
        import_panel.rowconfigure(1, weight=1)
        ttk.Label(
            import_panel,
            text="Apri il file ricevuto, controlla l'anteprima e importalo su questo PC.",
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        import_body = ttk.Frame(import_panel)
        import_body.grid(row=1, column=0, sticky="nsew")
        import_body.columnconfigure(0, weight=1)
        import_body.rowconfigure(2, weight=1)
        self._build_import_tab(import_body)

    def _build_export_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        export_body = ttk.Frame(parent)
        export_body.grid(row=0, column=0, sticky="nsew")
        export_body.columnconfigure(0, weight=1)
        export_body.rowconfigure(1, weight=1)

        ttk.Label(export_body, text="Email da trasferire").grid(row=0, column=0, sticky="w")
        self.email_text = tk.Text(export_body, height=9, width=42, wrap="word")
        self.email_text.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.email_text.bind("<<Modified>>", self._on_email_text_modified)
        self.email_text.edit_modified(False)
        ttk.Label(export_body, text="Una per riga o separate da virgola.").grid(row=2, column=0, sticky="w", pady=(6, 0))

        email_actions = ttk.Frame(export_body)
        email_actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        email_actions.columnconfigure(3, weight=1)
        ttk.Button(email_actions, text="Ultimo set", command=self.restore_last_export_set).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(email_actions, text="Pulisci", command=self.clear_export_emails).grid(row=0, column=1)
        ttk.Button(email_actions, text="Controlla", command=self.inspect).grid(row=0, column=2, padx=(12, 8))
        ttk.Button(email_actions, text="Crea ZIP", command=self.create_zip_bundle).grid(row=0, column=3, sticky="e")

        ttk.Label(export_body, text="Provider da esportare").grid(row=4, column=0, sticky="w", pady=(14, 0))
        scope_frame = ttk.Frame(export_body)
        scope_frame.grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Checkbutton(
            scope_frame,
            text="Codex",
            variable=self.export_product_vars["codex"],
            command=self._update_summary,
        ).grid(row=0, column=0, padx=(0, 14))
        ttk.Checkbutton(
            scope_frame,
            text="Gemini",
            variable=self.export_product_vars["gemini"],
            command=self._update_summary,
        ).grid(row=0, column=1, padx=(0, 14))
        ttk.Checkbutton(
            scope_frame,
            text="Antigravity",
            variable=self.export_product_vars["antigravity"],
            command=self._update_summary,
        ).grid(row=0, column=2)

        ttk.Label(export_body, text=f"Output: {self._short_path(Path(self.output_dir_var.get()))}", wraplength=360, justify="left").grid(
            row=6, column=0, sticky="w", pady=(14, 0)
        )
        ttk.Label(
            export_body,
            text="Il controllo usa esattamente i provider selezionati qui sopra.",
            wraplength=360,
            justify="left",
        ).grid(row=7, column=0, sticky="w", pady=(8, 0))

    def _build_import_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        file_row = ttk.Frame(parent)
        file_row.grid(row=0, column=0, sticky="ew")
        file_row.columnconfigure(0, weight=1)
        ttk.Entry(file_row, textvariable=self.package_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(file_row, text="Sfoglia", command=self._pick_import_file).grid(row=0, column=1, padx=(6, 0))

        actions = ttk.Frame(parent)
        actions.grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(actions, text="Ultimo file", command=self.restore_last_import_file).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Importa", command=self.import_package).grid(row=0, column=1, sticky="w", padx=(8, 0))

        preview_box = ttk.LabelFrame(parent, text="Anteprima file", padding=10)
        preview_box.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(0, weight=1)
        self.import_preview_text = tk.Text(preview_box, wrap="word", height=12)
        self.import_preview_text.grid(row=0, column=0, sticky="nsew")
        preview_scrollbar = ttk.Scrollbar(preview_box, orient="vertical", command=self.import_preview_text.yview)
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        self.import_preview_text.configure(yscrollcommand=preview_scrollbar.set, state="disabled")

    def _build_inspect_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(10, weight=1)
        ttk.Checkbutton(toolbar, text="Codex", variable=self.inspect_product_vars["codex"]).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(toolbar, text="Gemini", variable=self.inspect_product_vars["gemini"]).grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Checkbutton(toolbar, text="Antigravity", variable=self.inspect_product_vars["antigravity"]).grid(row=0, column=2, sticky="w", padx=(10, 0))
        ttk.Button(toolbar, text="Usa provider export", command=self.match_inspect_products_to_export).grid(row=0, column=3, sticky="w", padx=(12, 0))
        ttk.Button(toolbar, text="Mail uniche", command=self.inspect_unique_selected).grid(row=0, column=4, sticky="w", padx=(12, 0))
        ttk.Button(toolbar, text="Vista tecnica", command=self.inspect_all_selected).grid(row=0, column=5, sticky="w", padx=(8, 0))
        ttk.Button(toolbar, text="Usa in export", command=self.use_current_emails_for_export).grid(row=0, column=6, sticky="w", padx=(12, 0))
        ttk.Button(toolbar, text="Copia", command=self.copy_current_emails).grid(row=0, column=7, sticky="w", padx=(8, 0))
        ttk.Label(toolbar, text="Filtro").grid(row=0, column=9, sticky="e", padx=(12, 6))
        ttk.Entry(toolbar, textvariable=self.inspect_filter_var, width=24).grid(row=0, column=10, sticky="ew")
        ttk.Button(toolbar, text="X", width=3, command=self.clear_inspect_filter).grid(row=0, column=11, sticky="w", padx=(6, 0))

        info_row = ttk.Frame(parent)
        info_row.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        info_row.columnconfigure(0, weight=1)
        ttk.Label(info_row, textvariable=self.inspect_meta_var).grid(row=0, column=0, sticky="w")
        ttk.Label(info_row, textvariable=self.inspect_hint_var, wraplength=520, justify="right").grid(row=0, column=1, sticky="e")

        columns = ("provider", "email", "account_id", "flags")
        self.inspect_tree = ttk.Treeview(parent, columns=columns, show="headings", height=18, selectmode="extended")
        self.inspect_tree.grid(row=2, column=0, sticky="nsew")
        self._configure_inspect_tree_for_provider_view()
        self.inspect_tree.bind("<Double-1>", self._on_inspect_tree_activate)
        self.inspect_tree.bind("<Return>", self._on_inspect_tree_activate)
        self.inspect_tree.bind("<<TreeviewSelect>>", self._on_inspect_selection_changed)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.inspect_tree.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.inspect_tree.configure(yscrollcommand=scrollbar.set)

    def _build_advanced_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        paths_box = ttk.LabelFrame(parent, text="Percorsi rilevati", padding=10)
        paths_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        paths_box.columnconfigure(1, weight=1)
        ttk.Label(paths_box, text="Antigravity").grid(row=0, column=0, sticky="w")
        ttk.Label(paths_box, text=self._short_path(Path(self.cockpit_dir_var.get()))).grid(row=0, column=1, sticky="w")
        ttk.Label(paths_box, text="Codex").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(paths_box, text=self._short_path(Path(self.codex_dir_var.get()))).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(paths_box, text="Gemini").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(paths_box, text=self._short_path(Path(self.gemini_dir_var.get()))).grid(row=2, column=1, sticky="w", pady=(8, 0))

        options_box = ttk.LabelFrame(parent, text="Opzioni facoltative", padding=10)
        options_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        options_box.columnconfigure(1, weight=0)
        ttk.Checkbutton(options_box, text="Sostituisci email gia presenti", variable=self.overwrite_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(options_box, text="Chiudi Codex o Cockpit Tools se serve", variable=self.force_stop_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Label(options_box, text="Email corrente in Cockpit Tools (Codex)").grid(row=2, column=0, sticky="w", pady=(14, 0))
        ttk.Entry(options_box, textvariable=self.codex_set_current_email_var, width=34).grid(row=2, column=1, sticky="w", pady=(14, 0))
        ttk.Label(options_box, text="Profilo locale .codex da attivare").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(options_box, textvariable=self.codex_activate_email_var, width=34).grid(row=3, column=1, sticky="w", pady=(8, 0))
        ttk.Label(options_box, text="Profilo locale .gemini da attivare").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(options_box, textvariable=self.gemini_activate_email_var, width=34).grid(row=4, column=1, sticky="w", pady=(8, 0))

        ttk.Label(
            options_box,
            text="Lasciali vuoti se vuoi solo importare gli account senza attivarli localmente.",
            wraplength=820,
            justify="left",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(14, 0))

    def _build_log_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        self.log_text = tk.Text(parent, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _short_path(self, path: Path) -> str:
        try:
            home = Path.home().resolve()
            resolved = path.resolve()
            if str(resolved).startswith(str(home)):
                return "~" + str(resolved)[len(str(home)) :]
        except Exception:
            pass
        return str(path)

    def _pick_import_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Transfer file", "*.zip *.json"), ("All files", "*.*")])
        if path:
            self.package_var.set(path)
            self._save_state()

    def _set_import_preview_text(self, text: str) -> None:
        if not self.import_preview_text:
            return
        self.import_preview_text.configure(state="normal")
        self.import_preview_text.delete("1.0", "end")
        self.import_preview_text.insert("1.0", text)
        self.import_preview_text.configure(state="disabled")

    def _refresh_import_preview(self) -> None:
        package_path = Path(self.package_var.get().strip()) if self.package_var.get().strip() else None
        if not package_path:
            self._set_import_preview_text("Seleziona un file .zip o .json per vedere l'anteprima.")
            return
        if not package_path.exists():
            self._set_import_preview_text("Il file selezionato non esiste.")
            return

        try:
            if package_path.suffix.lower() == ".zip":
                temp_dir, extracted_path = extract_zip_to_temp(package_path)
                try:
                    package = read_json_or_default(extracted_path, None)
                finally:
                    temp_dir.cleanup()
            else:
                package = read_json_or_default(package_path, None)
            self._set_import_preview_text("\n".join(build_package_preview(package)))
        except Exception as exc:
            self._set_import_preview_text(f"Impossibile leggere il file selezionato.\n\n{exc}")

    def _on_package_path_changed(self, *_args) -> None:
        self._refresh_import_preview()

    def _emails(self) -> list[str]:
        if not self.email_text:
            return []
        raw = self.email_text.get("1.0", "end").strip()
        if not raw:
            return []
        parts = [item.strip() for chunk in raw.splitlines() for item in chunk.split(",")]
        return self._unique_emails(item for item in parts if item)

    def _set_emails_text(self, emails: list[str]) -> None:
        if not self.email_text:
            return
        self.email_text.delete("1.0", "end")
        if emails:
            self.email_text.insert("1.0", "\n".join(emails))
        self.email_text.edit_modified(False)
        self._update_summary(persist=False)
        self._save_state()

    def _on_email_text_modified(self, _event=None) -> None:
        if not self.email_text or not self.email_text.edit_modified():
            return
        self.email_text.edit_modified(False)
        self._update_summary(persist=False)

    def _unique_emails(self, emails) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for email in emails:
            value = str(email).strip()
            key = value.lower()
            if value and key not in seen:
                seen.add(key)
                unique.append(value)
        return unique

    def _restore_last_emails(self) -> None:
        emails = self._unique_emails(self.state.get("last_emails", []))
        if emails:
            self._set_emails_text(emails)

    def _ensure_default_provider_selection(self) -> None:
        if not self._selected_products():
            for name, enabled in DEFAULT_EXPORT_PRODUCTS.items():
                self.export_product_vars[name].set(enabled)
        if not [name for name, enabled in self.inspect_product_vars.items() if enabled.get()]:
            for name, enabled in DEFAULT_INSPECT_PRODUCTS.items():
                self.inspect_product_vars[name].set(enabled)

    def _select_tab(self, tab_text: str) -> None:
        if not self.notebook:
            return
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text") == tab_text:
                self.notebook.select(tab_id)
                return

    def _state_snapshot(self) -> dict[str, object]:
        return {
            "export_products": self._selected_products(),
            "inspect_products": [name for name, enabled in self.inspect_product_vars.items() if enabled.get()],
            "last_emails": self._emails(),
            "output_dir": self.output_dir_var.get(),
            "last_package_path": self.package_var.get().strip(),
            "overwrite_existing_email": self.overwrite_var.get(),
            "force_stop_processes": self.force_stop_var.get(),
            "codex_set_current_email": self.codex_set_current_email_var.get().strip(),
            "codex_activate_email": self.codex_activate_email_var.get().strip(),
            "gemini_activate_email": self.gemini_activate_email_var.get().strip(),
        }

    def _save_state(self) -> None:
        snapshot = self._state_snapshot()
        save_app_state(self.state_path, snapshot)
        self.state = snapshot

    def _on_close(self) -> None:
        self._save_state()
        self.root.destroy()

    def _selected_products(self) -> list[str]:
        return [name for name, enabled in self.export_product_vars.items() if enabled.get()]

    def _manual_inspect_products(self) -> list[str]:
        return self._selected_products()

    def _set_export_products(self, products: list[str]) -> None:
        selected = set(products)
        for name, variable in self.export_product_vars.items():
            variable.set(name in selected)
        self._update_summary()
        self._save_state()

    def clear_export_emails(self) -> None:
        self._set_emails_text([])
        self.summary_var.set("Email da esportare pulite.")

    def restore_last_export_set(self) -> None:
        emails = self._unique_emails(self.state.get("last_emails", []))
        if not emails:
            messagebox.showinfo("Nessun set salvato", "Non ho ancora un set email precedente da ripristinare.")
            return
        self._set_export_products(list(self.state.get("export_products", self._selected_products())))
        self._set_emails_text(emails)
        self.summary_var.set(f"Ripristinato ultimo set: {len(emails)} email.")
        self._select_tab("Trasferisci")

    def restore_last_import_file(self) -> None:
        downloads_zip = latest_zip_in_dir(default_downloads_dir())
        if downloads_zip:
            self.package_var.set(str(downloads_zip))
            self.summary_var.set(f"Caricato ultimo ZIP da Downloads: {self._short_path(downloads_zip)}")
            self._select_tab("Trasferisci")
            self._save_state()
            return

        package_path = str(self.state.get("last_package_path", "")).strip()
        if package_path and Path(package_path).exists():
            resolved_path = Path(package_path)
            self.package_var.set(package_path)
            self.summary_var.set(f"Ripristinato ultimo file import: {self._short_path(resolved_path)}")
            self._select_tab("Trasferisci")
            return

        self.package_var.set("")
        self._save_state()
        messagebox.showinfo("Nessun file", "Non trovo ZIP recenti in Downloads e non c'e un file import salvato valido.")

    def _restart_cockpit_if_possible(self) -> str | None:
        return restart_cockpit_if_possible()

    def _send_emails_to_export(self, emails: list[str], source_label: str) -> None:
        unique = self._unique_emails(emails)
        if not unique:
            messagebox.showinfo("Nessuna email", "Non ci sono email da inviare al box export.")
            return
        self._set_emails_text(unique)
        self.summary_var.set(f"Email preparate per l'export da {source_label}: {len(unique)} email")
        self._log(f"Email inviate al box export da {source_label}: {len(unique)} email")
        self._select_tab("Trasferisci")

    def use_current_emails_for_export(self) -> None:
        selected = self._selected_emails_from_tree()
        if selected:
            self._send_emails_to_export(selected, "selezione corrente")
            return
        self._send_emails_to_export(self._visible_emails_from_tree(), "elenco corrente")

    def _set_inspect_products(self, products: list[str]) -> None:
        selected = set(products)
        for name, variable in self.inspect_product_vars.items():
            variable.set(name in selected)
        self._save_state()

    def match_inspect_products_to_export(self) -> None:
        export_products = self._selected_products()
        if not export_products:
            messagebox.showinfo("Nessun provider", "Seleziona prima almeno un provider nella pagina Trasferisci.")
            return
        self._set_inspect_products(export_products)
        self.summary_var.set("Provider del controllo allineati ai provider di export.")

    def _default_zip_name(self, products: list[str], emails: list[str]) -> str:
        return default_zip_name(products, emails)

    def _update_summary(self, persist: bool = True) -> None:
        products = self._selected_products()
        if not products:
            self.summary_var.set("Seleziona almeno un prodotto da esportare.")
            if persist:
                self._save_state()
            return
        label = " + ".join(product.capitalize() for product in products)
        emails_count = len(self._emails())
        self.summary_var.set(
            f"Esporta {label}. Email nel box: {emails_count}. Output: {self._short_path(Path(self.output_dir_var.get()))}."
        )
        if persist:
            self._save_state()

    def _log(self, message: str) -> None:
        if not self.log_text:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{stamp}] {message.rstrip()}\n")
        self.log_text.see("end")

    def _clear_log(self) -> None:
        if self.log_text:
            self.log_text.delete("1.0", "end")

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
        self.root.update_idletasks()

    def _run_action(self, label: str, action) -> None:
        self._set_status(label)
        self._log(label)
        try:
            result = action()
            if result:
                self._log(result.summary)
                for line in result.details:
                    self._log(f"- {line}")
                self._log("")
            self._set_status("Operazione completata")
            self._save_state()
        except Exception as exc:  # pragma: no cover - UI path
            self._log(f"ERRORE: {exc}")
            self._log(traceback.format_exc())
            self._set_status("Errore")
            messagebox.showerror("Errore", str(exc))

    def _validate_emails(self) -> tuple[list[str], list[str]]:
        products = self._selected_products()
        if not products:
            raise ValueError("Seleziona almeno un prodotto da esportare.")
        emails = self._emails()
        if not emails:
            raise ValueError("Inserisci almeno una email.")
        return products, emails

    def _configure_inspect_tree_for_provider_view(self) -> None:
        if not self.inspect_tree:
            return
        self.inspect_tree_mode = "provider"
        self.inspect_email_column = 1
        self.inspect_tree.configure(columns=("provider", "email", "account_id", "flags"))
        self.inspect_tree.heading("provider", text="Provider")
        self.inspect_tree.heading("email", text="Email")
        self.inspect_tree.heading("account_id", text="ID")
        self.inspect_tree.heading("flags", text="Stato")
        self.inspect_tree.column("provider", width=100, anchor="w")
        self.inspect_tree.column("email", width=320, anchor="w")
        self.inspect_tree.column("account_id", width=220, anchor="w")
        self.inspect_tree.column("flags", width=220, anchor="w")

    def _configure_inspect_tree_for_unique_view(self) -> None:
        if not self.inspect_tree:
            return
        self.inspect_tree_mode = "unique"
        self.inspect_email_column = 0
        self.inspect_tree.configure(columns=("email", "codex", "gemini", "antigravity", "notes"))
        self.inspect_tree.heading("email", text="Email")
        self.inspect_tree.heading("codex", text="Codex")
        self.inspect_tree.heading("gemini", text="Gemini")
        self.inspect_tree.heading("antigravity", text="Antigravity")
        self.inspect_tree.heading("notes", text="Note")
        self.inspect_tree.column("email", width=360, anchor="w")
        self.inspect_tree.column("codex", width=90, anchor="center")
        self.inspect_tree.column("gemini", width=90, anchor="center")
        self.inspect_tree.column("antigravity", width=100, anchor="center")
        self.inspect_tree.column("notes", width=250, anchor="w")

    def _fill_inspect_tree(self, rows_by_product: dict[str, list[dict[str, object]]]) -> None:
        if not self.inspect_tree:
            return
        self._configure_inspect_tree_for_provider_view()
        for item in self.inspect_tree.get_children():
            self.inspect_tree.delete(item)
        for product, rows in rows_by_product.items():
            for row in rows:
                flags = []
                for key, value in row.items():
                    if key in {"email", "account_id", "codex_account_id", "gemini_account_id"}:
                        continue
                    if isinstance(value, bool) and value:
                        flags.append(key.replace("_", " "))
                account_id = row.get("account_id") or row.get("codex_account_id") or row.get("gemini_account_id") or ""
                self.inspect_tree.insert("", "end", values=(product, row.get("email", ""), account_id, ", ".join(flags)))
        self._update_inspect_meta()

    def _fill_unique_inspect_tree(self, rows: list[dict[str, object]]) -> None:
        if not self.inspect_tree:
            return
        self._configure_inspect_tree_for_unique_view()
        for item in self.inspect_tree.get_children():
            self.inspect_tree.delete(item)
        for row in rows:
            self.inspect_tree.insert(
                "",
                "end",
                values=(
                    row.get("email", ""),
                    "Si" if row.get("codex_registered") else "-",
                    "Si" if row.get("gemini_registered") else "-",
                    "Si" if row.get("antigravity_registered") else "-",
                    row.get("notes", ""),
                ),
            )
        self._update_inspect_meta()

    def _filtered_unique_rows(self) -> list[dict[str, object]]:
        query = self.inspect_filter_var.get().strip().lower()
        if not query:
            return list(self.inspect_unique_rows_cache)
        filtered: list[dict[str, object]] = []
        for row in self.inspect_unique_rows_cache:
            haystack = " ".join(
                [
                    str(row.get("email", "")),
                    str(row.get("notes", "")),
                ]
            ).lower()
            if query in haystack:
                filtered.append(row)
        return filtered

    def _render_unique_rows(self) -> None:
        filtered_rows = self._filtered_unique_rows()
        self._fill_unique_inspect_tree(filtered_rows)

        total = len(self.inspect_unique_rows_cache)
        visible = len(filtered_rows)
        codex_count = sum(1 for row in filtered_rows if row.get("codex_registered"))
        gemini_count = sum(1 for row in filtered_rows if row.get("gemini_registered"))
        antigravity_count = sum(1 for row in filtered_rows if row.get("antigravity_registered"))
        filter_suffix = f" Filtrate: {visible}/{total}." if self.inspect_filter_var.get().strip() else f" Totali: {total}."
        self.summary_var.set(
            f"Mail uniche.{filter_suffix} Codex: {codex_count} | Gemini: {gemini_count} | Antigravity: {antigravity_count}"
        )
        self._update_inspect_meta()

    def _on_inspect_filter_changed(self, *_args) -> None:
        if self.inspect_tree_mode != "unique":
            return
        self._render_unique_rows()

    def clear_inspect_filter(self) -> None:
        if self.inspect_filter_var.get():
            self.inspect_filter_var.set("")

    def _on_inspect_tree_activate(self, _event=None) -> None:
        if self._selected_emails_from_tree():
            self.use_current_emails_for_export()

    def _on_inspect_selection_changed(self, _event=None) -> None:
        self._update_inspect_meta()

    def _update_inspect_meta(self) -> None:
        if not self.inspect_tree:
            self.inspect_meta_var.set("Nessun controllo eseguito.")
            return
        total_rows = len(self.inspect_tree.get_children())
        selected_rows = len(self.inspect_tree.selection())
        mode_label = "Mail uniche" if self.inspect_tree_mode == "unique" else "Dettaglio provider"
        self.inspect_meta_var.set(f"{mode_label}: {total_rows} righe | selezionate {selected_rows}")

    def _format_row_status(self, product: str, row: dict[str, object]) -> str:
        email = str(row.get("email", "")).strip()
        if product == "codex":
            present = bool(row.get("has_cockpit_index"))
            extra = []
            if row.get("is_current_in_cockpit"):
                extra.append("current")
            if row.get("is_active_codex_profile"):
                extra.append("active")
            suffix = f" ({', '.join(extra)})" if extra else ""
            return f"[{product}] {email}: {'presente' if present else 'mancante'}{suffix}"
        if product == "gemini":
            present = bool(row.get("has_cockpit_index"))
            suffix = " (active)" if row.get("is_active_gemini_profile") else ""
            return f"[{product}] {email}: {'presente' if present else 'mancante'}{suffix}"
        if product == "antigravity":
            present = bool(row.get("has_cockpit_index")) or bool(row.get("account_id"))
            return f"[{product}] {email}: {'presente' if present else 'mancante'}"
        return f"[{product}] {email}"

    def _confirm_export_report(self, report: dict[str, object], archive_path: Path) -> bool:
        dialog = tk.Toplevel(self.root)
        dialog.title("Conferma export")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("620x420")
        dialog.minsize(560, 360)

        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text=f"Sto per creare questo file:\n{self._short_path(archive_path)}",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        text = tk.Text(frame, wrap="word", height=14)
        text.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        lines = ["Riepilogo prima dell'export", ""]
        for product, product_report in report.items():
            if not isinstance(product_report, dict):
                continue
            lines.append(
                f"{product.capitalize()}: trovate {product_report.get('found_count', 0)} su {product_report.get('selected_count', 0)}, mancanti {product_report.get('missing_count', 0)}"
            )
            found = product_report.get("found_emails") or []
            missing = product_report.get("missing_emails") or []
            if found:
                lines.append("Trovate: " + ", ".join(str(item) for item in found))
            if missing:
                lines.append("Mancanti: " + ", ".join(str(item) for item in missing))
            lines.append("")
        text.insert("1.0", "\n".join(lines).strip())
        text.configure(state="disabled")

        result = {"confirmed": False}

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)

        def confirm() -> None:
            result["confirmed"] = True
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        ttk.Button(buttons, text="Annulla", command=cancel).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Crea ZIP", command=confirm).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(dialog)
        return bool(result["confirmed"])

    def inspect(self) -> None:
        def action():
            _, emails = self._validate_emails()
            products = self._manual_inspect_products()
            rows_by_product = inspect_products(
                products,
                Path(self.cockpit_dir_var.get()),
                Path(self.codex_dir_var.get()),
                Path(self.gemini_dir_var.get()),
                emails,
            )
            self._fill_inspect_tree(rows_by_product)
            details = []
            summary_chunks = []
            for product, rows in rows_by_product.items():
                product_found = 0
                product_missing = 0
                for row in rows:
                    if product == "antigravity":
                        has_index = bool(row.get("has_cockpit_index")) or bool(row.get("account_id"))
                    else:
                        has_index = bool(row.get("has_cockpit_index"))
                    product_found += 1 if has_index else 0
                    product_missing += 0 if has_index else 1
                    details.append(self._format_row_status(product, row))
                summary_chunks.append(f"{product.capitalize()}: presenti {product_found}, mancanti {product_missing}")
            self.summary_var.set(
                f"Controllo sulle email inserite ({len(emails)} email). " + " | ".join(summary_chunks)
            )
            return OperationResult("Controllo email completato.", details)

        self._run_action("Controllo email in corso...", action)

    def inspect_all(self, products: list[str]) -> None:
        def action():
            self.inspect_unique_rows_cache = []
            rows_by_product = inspect_products(
                products,
                Path(self.cockpit_dir_var.get()),
                Path(self.codex_dir_var.get()),
                Path(self.gemini_dir_var.get()),
                None,
            )
            self._fill_inspect_tree(rows_by_product)
            self.inspect_hint_var.set(
                "Vista tecnica: utile solo se vuoi vedere le righe lette dai singoli file. Doppio click su una riga = usa in export."
            )
            summary_chunks = []
            details = []
            for product, rows in rows_by_product.items():
                emails = []
                for row in rows:
                    email = row.get("email")
                    has_index = bool(row.get("has_cockpit_index")) or bool(row.get("account_id"))
                    if email and has_index:
                        emails.append(str(email))
                summary_chunks.append(f"{product.capitalize()}: {len(emails)} email")
                details.append(f"[{product}] trovate {len(emails)} email")
            self.summary_var.set(" | ".join(summary_chunks) if summary_chunks else "Nessuna email trovata.")
            return OperationResult("Elenco email completato.", details)

        self._run_action("Lettura elenco email in corso...", action)

    def inspect_unique(self, products: list[str]) -> None:
        def action():
            rows_by_product = inspect_products(
                products,
                Path(self.cockpit_dir_var.get()),
                Path(self.codex_dir_var.get()),
                Path(self.gemini_dir_var.get()),
                None,
            )
            unique_rows = summarize_unique_emails(rows_by_product)
            self.inspect_unique_rows_cache = unique_rows
            self.inspect_hint_var.set(
                "Vista principale: una riga per email e una colonna per ogni provider. Doppio click su una riga = usa in export."
            )
            self._render_unique_rows()
            codex_count = sum(1 for row in unique_rows if row.get("codex_registered"))
            gemini_count = sum(1 for row in unique_rows if row.get("gemini_registered"))
            antigravity_count = sum(1 for row in unique_rows if row.get("antigravity_registered"))
            details = [f"Mail uniche trovate: {len(unique_rows)}"]
            details.append(f"Registrate su Codex: {codex_count}")
            details.append(f"Registrate su Gemini: {gemini_count}")
            details.append(f"Registrate su Antigravity: {antigravity_count}")
            return OperationResult("Vista mail uniche completata.", details)

        self._run_action("Costruzione vista mail uniche...", action)

    def inspect_all_selected(self) -> None:
        products = [name for name, enabled in self.inspect_product_vars.items() if enabled.get()]
        if not products:
            messagebox.showinfo("Selezione vuota", "Seleziona almeno un provider da elencare.")
            return
        self.inspect_all(products)

    def inspect_unique_selected(self) -> None:
        products = [name for name, enabled in self.inspect_product_vars.items() if enabled.get()]
        if not products:
            messagebox.showinfo("Selezione vuota", "Seleziona almeno un provider da elencare.")
            return
        self.inspect_unique(products)

    def _extract_email_from_tree_values(self, values: tuple[object, ...] | list[object]) -> str:
        if len(values) <= self.inspect_email_column:
            return ""
        return str(values[self.inspect_email_column]).strip()

    def _visible_emails_from_tree(self) -> list[str]:
        if not self.inspect_tree:
            return []
        emails: list[str] = []
        seen: set[str] = set()
        for item in self.inspect_tree.get_children():
            values = self.inspect_tree.item(item, "values")
            email = self._extract_email_from_tree_values(values)
            key = email.lower()
            if email and key not in seen:
                seen.add(key)
                emails.append(email)
        return emails

    def _selected_emails_from_tree(self) -> list[str]:
        if not self.inspect_tree:
            return []
        emails: list[str] = []
        seen: set[str] = set()
        for item in self.inspect_tree.selection():
            values = self.inspect_tree.item(item, "values")
            email = self._extract_email_from_tree_values(values)
            key = email.lower()
            if email and key not in seen:
                seen.add(key)
                emails.append(email)
        return emails

    def _copy_emails(self, emails: list[str], empty_message: str, success_message: str) -> None:
        if not emails:
            messagebox.showinfo("Nessuna email", empty_message)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(emails))
        self.root.update()
        self.summary_var.set(f"{success_message}: {len(emails)} email")
        self._log(f"{success_message}: {len(emails)} email")

    def copy_selected_emails(self) -> None:
        self._copy_emails(
            self._selected_emails_from_tree(),
            "Seleziona una o piu righe nella tabella.",
            "Email selezionate copiate negli appunti",
        )

    def copy_all_visible_emails(self) -> None:
        self._copy_emails(
            self._visible_emails_from_tree(),
            "Non ci sono email visibili da copiare.",
            "Tutte le email visibili sono state copiate negli appunti",
        )

    def copy_current_emails(self) -> None:
        selected = self._selected_emails_from_tree()
        if selected:
            self._copy_emails(selected, "Seleziona una o piu righe.", "Email selezionate copiate")
            return
        self._copy_emails(self._visible_emails_from_tree(), "Non ci sono email visibili da copiare.", "Email copiate")

    def create_zip_bundle(self) -> None:
        def action():
            products, emails = self._validate_emails()
            output_dir = Path(self.output_dir_var.get())
            archive_path = output_dir / self._default_zip_name(products, emails)

            from .multi_transfer import export_products

            with tempfile.TemporaryDirectory() as tmp:
                package_path = Path(tmp) / "transfer-package.json"
                export_result = export_products(
                    products,
                    emails,
                    Path(self.cockpit_dir_var.get()),
                    Path(self.codex_dir_var.get()),
                    Path(self.gemini_dir_var.get()),
                    package_path,
                )
                package_data = read_json_or_default(package_path, {})
                report = package_data.get("report") or {}
                if report and not self._confirm_export_report(report, archive_path):
                    return OperationResult("Export annullato.", ["Hai annullato la creazione dello ZIP."])
                zip_result = create_bundle_zip(
                    package_path,
                    archive_path,
                    codex_set_current_email=self.codex_set_current_email_var.get().strip() or None,
                    codex_activate_email=self.codex_activate_email_var.get().strip() or None,
                    gemini_activate_email=self.gemini_activate_email_var.get().strip() or None,
                )
            self.package_var.set(str(archive_path))
            summary_parts = [f"ZIP pronto: {self._short_path(archive_path)}"]
            for line in export_result.details:
                if "trovate" in line and line.startswith("["):
                    summary_parts.append(line)
            self.summary_var.set(" | ".join(summary_parts))
            return OperationResult("File ZIP creato.", [*export_result.details, *zip_result.details], archive_path)

        self._run_action("Creazione ZIP in corso...", action)

    def import_package(self) -> None:
        def action():
            import_path = Path(self.package_var.get())
            if not import_path.exists():
                raise ValueError("Seleziona un file ZIP o JSON valido.")

            if import_path.suffix.lower() == ".zip":
                temp_dir, package_path = extract_zip_to_temp(import_path)
                try:
                    result = import_products(
                        package_path,
                        Path(self.cockpit_dir_var.get()),
                        Path(self.codex_dir_var.get()),
                        Path(self.gemini_dir_var.get()),
                        overwrite_existing_email=self.overwrite_var.get(),
                        codex_set_current_email=self.codex_set_current_email_var.get().strip() or None,
                        codex_activate_email=self.codex_activate_email_var.get().strip() or None,
                        gemini_activate_email=self.gemini_activate_email_var.get().strip() or None,
                        force_stop_processes=self.force_stop_var.get(),
                    )
                finally:
                    temp_dir.cleanup()
                restart_target = self._restart_cockpit_if_possible()
                if restart_target:
                    result.details.append(f"Cockpit riavviato automaticamente: {restart_target}")
                    self.summary_var.set(
                        "Import completato dal file ZIP ricevuto. Cockpit e' stato riavviato automaticamente."
                    )
                else:
                    result.details.append("Riavvio automatico Cockpit non disponibile: launcher non trovato.")
                    self.summary_var.set(
                        "Import completato dal file ZIP ricevuto. Controlla il tab Log per vedere cosa e' stato importato o saltato per ogni provider."
                    )
                return result

            result = import_products(
                import_path,
                Path(self.cockpit_dir_var.get()),
                Path(self.codex_dir_var.get()),
                Path(self.gemini_dir_var.get()),
                overwrite_existing_email=self.overwrite_var.get(),
                codex_set_current_email=self.codex_set_current_email_var.get().strip() or None,
                codex_activate_email=self.codex_activate_email_var.get().strip() or None,
                gemini_activate_email=self.gemini_activate_email_var.get().strip() or None,
                force_stop_processes=self.force_stop_var.get(),
            )
            restart_target = self._restart_cockpit_if_possible()
            if restart_target:
                result.details.append(f"Cockpit riavviato automaticamente: {restart_target}")
                self.summary_var.set("Import completato dal file selezionato. Cockpit e' stato riavviato automaticamente.")
            else:
                result.details.append("Riavvio automatico Cockpit non disponibile: launcher non trovato.")
                self.summary_var.set("Import completato dal file selezionato. Controlla il tab Log per vedere cosa e' stato importato o saltato per ogni provider.")
            return result

        self._run_action("Import in corso...", action)


def launch_gui() -> None:
    root = tk.Tk()
    TransferApp(root)
    root.mainloop()
