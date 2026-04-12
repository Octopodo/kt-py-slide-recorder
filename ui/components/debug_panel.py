import customtkinter as ctk


class DebugPanel(ctk.CTkFrame):
    """
    Horizontally collapsible debug panel showing event count and
    last-event field values (time_hms, time_ms, slide_index, event_type).
    """

    # The widest label is "Events:" (7 chars) and the widest value is a
    # 13-digit epoch ms timestamp.  A fixed width avoids layout jumps.
    _PANEL_WIDTH = 190
    _COLLAPSED_WIDTH = 28

    def __init__(self, parent, **kw) -> None:
        super().__init__(parent, corner_radius=8, width=self._PANEL_WIDTH, **kw)
        self.grid_propagate(False)
        self._expanded = False
        self._build_ui()
        self._apply_visibility()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        self._toggle_btn = ctk.CTkButton(
            self,
            text="\u25c0",
            width=self._COLLAPSED_WIDTH,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray82", "gray28"),
            command=self._toggle,
        )
        self._toggle_btn.grid(row=0, column=0, sticky="n", padx=2, pady=(4, 0))

        self._content = ctk.CTkFrame(self, fg_color="transparent")

        mono = ctk.CTkFont(size=12, family="Courier New")
        label_opts = {"sticky": "w", "padx": (6, 2), "pady": 1}
        value_opts = {"sticky": "w", "padx": (2, 6), "pady": 1}
        _VAL_W = 110  # fits 13-char epoch ms values in Courier New 12

        row = 0
        ctk.CTkLabel(self._content, text="Events:").grid(row=row, column=0, **label_opts)
        self._events_label = ctk.CTkLabel(self._content, text="0", font=mono, width=_VAL_W, anchor="w")
        self._events_label.grid(row=row, column=1, **value_opts)

        row += 1
        ctk.CTkLabel(self._content, text="type:").grid(row=row, column=0, **label_opts)
        self._type_label = ctk.CTkLabel(self._content, text="\u2014", font=mono, width=_VAL_W, anchor="w")
        self._type_label.grid(row=row, column=1, **value_opts)

        row += 1
        ctk.CTkLabel(self._content, text="slide:").grid(row=row, column=0, **label_opts)
        self._slide_label = ctk.CTkLabel(self._content, text="\u2014", font=mono, width=_VAL_W, anchor="w")
        self._slide_label.grid(row=row, column=1, **value_opts)

        row += 1
        ctk.CTkLabel(self._content, text="hms:").grid(row=row, column=0, **label_opts)
        self._hms_label = ctk.CTkLabel(self._content, text="\u2014", font=mono, width=_VAL_W, anchor="w")
        self._hms_label.grid(row=row, column=1, **value_opts)

        row += 1
        ctk.CTkLabel(self._content, text="ms:").grid(row=row, column=0, **label_opts)
        self._ms_label = ctk.CTkLabel(self._content, text="\u2014", font=mono, width=_VAL_W, anchor="w")
        self._ms_label.grid(row=row, column=1, **value_opts)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        if self._expanded:
            self._toggle_btn.configure(text="\u25b6")
            self._content.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=2, pady=(4, 6))
        else:
            self._toggle_btn.configure(text="\u25c0")
            self._content.grid_forget()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def update_event_count(self, count: int) -> None:
        self._events_label.configure(text=str(count))

    def update_last_event(self, event) -> None:
        """Update all fields from a SlideEvent dataclass instance."""
        self._type_label.configure(text=event.event_type)
        self._slide_label.configure(text=str(event.slide_index))
        self._hms_label.configure(text=event.time_hms)
        self._ms_label.configure(text=str(event.time_ms))

    def reset(self) -> None:
        self._events_label.configure(text="0")
        for lbl in (self._type_label, self._slide_label, self._hms_label, self._ms_label):
            lbl.configure(text="\u2014")
