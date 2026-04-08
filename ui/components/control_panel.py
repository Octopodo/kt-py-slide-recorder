import customtkinter as ctk


class ControlPanel(ctk.CTkFrame):
    """
    Record/Stop toggle button, elapsed time chronometer, and event counter.

    The chronometer is driven by app.after() in the UI layer — this panel
    just exposes update methods.
    """

    def __init__(
        self,
        parent,
        on_record: callable,
        on_stop: callable,
    ) -> None:
        super().__init__(parent, corner_radius=8)
        self._on_record = on_record
        self._on_stop = on_stop
        self._is_recording = False
        self._build_ui()

    def _build_ui(self) -> None:
        ctk.CTkLabel(
            self,
            text="Recording",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 6), sticky="w")

        self._toggle_btn = ctk.CTkButton(
            self,
            text="⏺  Record",
            width=200,
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#c0392b",
            hover_color="#a93226",
            command=self._toggle,
        )
        self._toggle_btn.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 10))

        ctk.CTkLabel(self, text="Elapsed:").grid(
            row=2, column=0, padx=(12, 4), pady=4, sticky="e"
        )
        self._elapsed_label = ctk.CTkLabel(
            self,
            text="00:00:00",
            font=ctk.CTkFont(size=22, family="Courier New"),
        )
        self._elapsed_label.grid(row=2, column=1, padx=(4, 12), pady=4, sticky="w")

        ctk.CTkLabel(self, text="Events:").grid(
            row=3, column=0, padx=(12, 4), pady=(4, 10), sticky="e"
        )
        self._counter_label = ctk.CTkLabel(
            self,
            text="0",
            font=ctk.CTkFont(size=22, family="Courier New"),
        )
        self._counter_label.grid(
            row=3, column=1, padx=(4, 12), pady=(4, 10), sticky="w"
        )

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _toggle(self) -> None:
        if self._is_recording:
            self._on_stop()
        else:
            self._on_record()

    def set_recording(self, recording: bool) -> None:
        self._is_recording = recording
        if recording:
            self._toggle_btn.configure(
                text="⏹  Stop",
                fg_color="#27ae60",
                hover_color="#1e8449",
            )
        else:
            self._toggle_btn.configure(
                text="⏺  Record",
                fg_color="#c0392b",
                hover_color="#a93226",
            )

    def update_elapsed(self, elapsed_s: float) -> None:
        h = int(elapsed_s // 3600)
        m = int((elapsed_s % 3600) // 60)
        s = int(elapsed_s % 60)
        self._elapsed_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

    def update_event_count(self, count: int) -> None:
        self._counter_label.configure(text=str(count))

    def reset_display(self) -> None:
        self.update_elapsed(0.0)
        self.update_event_count(0)
