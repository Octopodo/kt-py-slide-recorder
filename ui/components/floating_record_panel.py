"""Floating compact window shown while recording."""

import customtkinter as ctk


class FloatingRecordPanel(ctk.CTkToplevel):
    """Minimal always-available recording controls and debug information."""

    _WIDTH = 330
    _HEIGHT = 310
    _TEXT_COLOR = "#bfbfbf"  # approx 75% opacity white over black
    _TITLE_COLOR = "#ff8a84"
    _DOT_ON = "●"
    _DOT_OFF = "○"
    _COLOR_GREEN = "#4cd97b"
    _COLOR_YELLOW = "#f0b429"
    _COLOR_GREY = "#7f7f7f"

    def __init__(
        self,
        parent,
        on_stop: callable,
        topmost: bool = True,
        start_geometry: str = "",
    ) -> None:
        super().__init__(parent)
        self._on_stop = on_stop
        self.configure(fg_color="#000000")
        self._build_ui()

        self.title("Recording")
        self.resizable(True, True)
        self.minsize(self._WIDTH, self._HEIGHT)
        if start_geometry:
            self.geometry(start_geometry)
        else:
            self._place_top_right()
        self.set_topmost(topmost)
        self._set_alpha(0.8)
        self.protocol("WM_DELETE_WINDOW", self._on_stop)

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Recording",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self._TITLE_COLOR,
            fg_color="transparent",
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 2), sticky="w")

        self._stop_btn = ctk.CTkButton(
            self,
            text="Stop",
            command=self._on_stop,
            fg_color="#27ae60",
            hover_color="#1e8449",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
        )
        self._stop_btn.grid(row=1, column=0, columnspan=2, padx=12, pady=(4, 4), sticky="ew")

        # ── Connection status ──────────────────────────────────────────
        ctk.CTkLabel(
            self, text="Impress:", text_color=self._TEXT_COLOR, fg_color="transparent"
        ).grid(row=2, column=0, padx=(12, 4), pady=(2, 1), sticky="w")
        self._impress_status_label = ctk.CTkLabel(
            self,
            text=f"{self._DOT_OFF}  Waiting",
            text_color=self._COLOR_GREY,
            fg_color="transparent",
            anchor="w",
        )
        self._impress_status_label.grid(row=2, column=1, padx=(4, 12), pady=(2, 1), sticky="w")

        ctk.CTkLabel(
            self, text="OBS:", text_color=self._TEXT_COLOR, fg_color="transparent"
        ).grid(row=3, column=0, padx=(12, 4), pady=(1, 4), sticky="w")
        self._obs_status_label = ctk.CTkLabel(
            self,
            text=f"{self._DOT_OFF}  Disconnected",
            text_color=self._COLOR_GREY,
            fg_color="transparent",
            anchor="w",
        )
        self._obs_status_label.grid(row=3, column=1, padx=(4, 12), pady=(1, 4), sticky="w")

        # ── Elapsed ────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Elapsed:", text_color=self._TEXT_COLOR).grid(
            row=4, column=0, padx=(12, 4), pady=(0, 2), sticky="w"
        )
        self._elapsed_label = ctk.CTkLabel(
            self,
            text="00:00:00",
            font=ctk.CTkFont(size=22, family="Courier New"),
            text_color=self._TEXT_COLOR,
        )
        self._elapsed_label.grid(row=4, column=1, padx=(4, 12), pady=(0, 2), sticky="w")

        self._events_label = self._add_debug_row(5, "Events:", "0")
        self._type_label = self._add_debug_row(6, "type:", "-")
        self._slide_label = self._add_debug_row(7, "slide:", "-")
        self._hms_label = self._add_debug_row(8, "hms:", "-")
        self._ms_label = self._add_debug_row(9, "ms:", "-")

    def _add_debug_row(self, row: int, label: str, initial: str):
        ctk.CTkLabel(
            self,
            text=label,
            fg_color="transparent",
            text_color=self._TEXT_COLOR,
        ).grid(
            row=row, column=0, padx=(12, 4), pady=1, sticky="w"
        )
        value_label = ctk.CTkLabel(
            self,
            text=initial,
            font=ctk.CTkFont(size=12, family="Courier New"),
            anchor="w",
            text_color=self._TEXT_COLOR,
        )
        value_label.grid(row=row, column=1, padx=(4, 12), pady=1, sticky="w")
        return value_label

    def current_geometry(self) -> str:
        return self.geometry()

    def _place_top_right(self) -> None:
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        x = max(0, screen_w - self._WIDTH - 16)
        y = 24
        self.geometry(f"{self._WIDTH}x{self._HEIGHT}+{x}+{y}")

    def _set_alpha(self, value: float) -> None:
        try:
            self.attributes("-alpha", value)
        except Exception:
            pass

    def set_topmost(self, topmost: bool) -> None:
        try:
            self.attributes("-topmost", bool(topmost))
        except Exception:
            pass
        self.lift()

    def update_elapsed(self, elapsed_s: float) -> None:
        h = int(elapsed_s // 3600)
        m = int((elapsed_s % 3600) // 60)
        s = int(elapsed_s % 60)
        self._elapsed_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

    def update_event_count(self, count: int) -> None:
        self._events_label.configure(text=str(count))

    def update_last_event(self, event) -> None:
        self._type_label.configure(text=event.event_type)
        self._slide_label.configure(text=str(event.slide_index))
        self._hms_label.configure(text=event.time_hms)
        self._ms_label.configure(text=str(event.time_ms))

    def update_impress_status(self, connected: bool, in_presentation: bool = False) -> None:
        if connected and in_presentation:
            self._impress_status_label.configure(
                text=f"{self._DOT_ON}  In Presentation", text_color=self._COLOR_GREEN
            )
        elif connected:
            self._impress_status_label.configure(
                text=f"{self._DOT_ON}  Connected", text_color=self._COLOR_YELLOW
            )
        else:
            self._impress_status_label.configure(
                text=f"{self._DOT_OFF}  Waiting", text_color=self._COLOR_GREY
            )

    def update_obs_status(self, connected: bool, recording: bool = False) -> None:
        if connected and recording:
            self._obs_status_label.configure(
                text=f"{self._DOT_ON}  Recording", text_color=self._COLOR_GREEN
            )
        elif connected:
            self._obs_status_label.configure(
                text=f"{self._DOT_ON}  Connected", text_color=self._COLOR_YELLOW
            )
        else:
            self._obs_status_label.configure(
                text=f"{self._DOT_OFF}  Disconnected", text_color=self._COLOR_GREY
            )
