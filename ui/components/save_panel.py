from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk


class SavePanel(ctk.CTkFrame):
    """
    Save settings panel.

    - Browse: selects the PRIMARY save path used for the final session file
      and for autosave (written to <name>_autosave.json in the same folder).
    - Autosave interval: configures how often the autosave fires (minimum 5 s).
    - Save Now: opens a separate file dialog so the user can write a copy of
      the current session to any location without changing the primary path.
    """

    def __init__(
        self,
        parent,
        on_path_changed: Callable[[str], None],
        on_manual_save: Callable[[], None],
        on_autosave_interval_changed: Callable[[int], None],
        default_interval: int = 60,
        default_path: str = "",
    ) -> None:
        super().__init__(parent, corner_radius=8)
        self._on_path_changed = on_path_changed
        self._on_manual_save = on_manual_save
        self._on_autosave_interval_changed = on_autosave_interval_changed
        self._default_path = default_path
        self._build_ui(default_interval)

    def _build_ui(self, default_interval: int) -> None:
        ctk.CTkLabel(
            self,
            text="Save Settings",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        # Primary save path
        ctk.CTkLabel(self, text="Save path:").grid(
            row=1, column=0, padx=(12, 6), pady=4, sticky="w"
        )
        self._path_var = ctk.StringVar(value=self._default_path)
        self._path_entry = ctk.CTkEntry(
            self,
            textvariable=self._path_var,
            width=220,
            state="readonly",
            placeholder_text="No path selected",
        )
        self._path_entry.grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(self, text="Browse", width=80, command=self._browse).grid(
            row=1, column=2, padx=(4, 12), pady=4
        )

        # Autosave interval
        ctk.CTkLabel(self, text="Autosave (s):").grid(
            row=2, column=0, padx=(12, 6), pady=4, sticky="w"
        )
        self._interval_var = ctk.StringVar(value=str(default_interval))
        ctk.CTkEntry(self, textvariable=self._interval_var, width=60).grid(
            row=2, column=1, padx=4, pady=4, sticky="w"
        )
        ctk.CTkButton(self, text="Apply", width=80, command=self._apply_interval).grid(
            row=2, column=2, padx=(4, 12), pady=4
        )

        # Save Now button
        self._save_btn = ctk.CTkButton(
            self,
            text="Save Now",
            command=self._on_manual_save,
            state="disabled",
        )
        self._save_btn.grid(
            row=3, column=0, columnspan=3, padx=12, pady=(6, 12), sticky="ew"
        )

        self.columnconfigure(1, weight=1)

    def _browse(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Select save location",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._path_var.set(path)
            self._on_path_changed(path)

    def _apply_interval(self) -> None:
        try:
            val = int(self._interval_var.get())
            if val < 5:
                raise ValueError
            self._on_autosave_interval_changed(val)
        except ValueError:
            messagebox.showerror(
                "Invalid interval",
                "Autosave interval must be an integer ≥ 5 seconds.",
            )

    def enable_save_button(self, enabled: bool) -> None:
        self._save_btn.configure(state="normal" if enabled else "disabled")

    @property
    def save_path(self) -> str:
        return self._path_var.get()
