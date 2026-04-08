from typing import Callable

import customtkinter as ctk


class KeyConfigPanel(ctk.CTkFrame):
    """
    Panel for configuring the forward and backward key bindings.

    Exposes two "Capture" buttons. When clicked, the button enters a waiting
    state and the next key pressed (intercepted via KeyListenerService) becomes
    the new binding. The UI is updated via a callback passed back from app.py,
    which runs on the main thread via app.after(0, ...).
    """

    def __init__(
        self,
        parent,
        on_capture_forward: Callable[[Callable[[str], None]], None],
        on_capture_backward: Callable[[Callable[[str], None]], None],
        forward_display: str = "right",
        backward_display: str = "left",
    ) -> None:
        super().__init__(parent, corner_radius=8)
        self._on_capture_forward = on_capture_forward
        self._on_capture_backward = on_capture_backward
        self._build_ui(forward_display, backward_display)

    def _build_ui(self, forward_display: str, backward_display: str) -> None:
        ctk.CTkLabel(
            self,
            text="Key Bindings",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 4), sticky="w")

        # Forward row
        ctk.CTkLabel(self, text="Forward:").grid(
            row=1, column=0, padx=(12, 6), pady=8, sticky="w"
        )
        self._forward_label = ctk.CTkLabel(
            self,
            text=forward_display,
            width=100,
            fg_color=("gray80", "gray30"),
            corner_radius=4,
        )
        self._forward_label.grid(row=1, column=1, padx=6, pady=8)
        self._capture_fwd_btn = ctk.CTkButton(
            self,
            text="Capture",
            width=90,
            command=self._start_capture_forward,
        )
        self._capture_fwd_btn.grid(row=1, column=2, padx=(6, 12), pady=8)

        # Backward row
        ctk.CTkLabel(self, text="Backward:").grid(
            row=2, column=0, padx=(12, 6), pady=(0, 10), sticky="w"
        )
        self._backward_label = ctk.CTkLabel(
            self,
            text=backward_display,
            width=100,
            fg_color=("gray80", "gray30"),
            corner_radius=4,
        )
        self._backward_label.grid(row=2, column=1, padx=6, pady=(0, 10))
        self._capture_bwd_btn = ctk.CTkButton(
            self,
            text="Capture",
            width=90,
            command=self._start_capture_backward,
        )
        self._capture_bwd_btn.grid(row=2, column=2, padx=(6, 12), pady=(0, 10))

        self.columnconfigure(1, weight=1)

    def set_enabled(self, enabled: bool) -> None:
        """Disable capture buttons during recording to avoid accidental rebinding."""
        state = "normal" if enabled else "disabled"
        self._capture_fwd_btn.configure(state=state)
        self._capture_bwd_btn.configure(state=state)

    def _start_capture_forward(self) -> None:
        self._capture_fwd_btn.configure(state="disabled", text="Press key…")
        self._on_capture_forward(self._finish_capture_forward)

    def _start_capture_backward(self) -> None:
        self._capture_bwd_btn.configure(state="disabled", text="Press key…")
        self._on_capture_backward(self._finish_capture_backward)

    def _finish_capture_forward(self, key_display: str) -> None:
        """Called on the main thread via app.after(0, ...)."""
        self._forward_label.configure(text=key_display)
        self._capture_fwd_btn.configure(state="normal", text="Capture")

    def _finish_capture_backward(self, key_display: str) -> None:
        """Called on the main thread via app.after(0, ...)."""
        self._backward_label.configure(text=key_display)
        self._capture_bwd_btn.configure(state="normal", text="Capture")
