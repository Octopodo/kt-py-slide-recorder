"""
ConnectionPanel — shows live connection status for Impress Bridge and OBS,
plus opt-in feature checkboxes.

Status indicators use colored dots:
  ● green  = connected / active
  ● yellow = connecting / waiting
  ○ grey   = disconnected

All update_*() methods are safe to call from the main (UI) thread only.
The App routes background-thread callbacks through app.after(0, ...) before
calling these methods.
"""

from typing import Callable

import customtkinter as ctk

# Dot characters and colors
_DOT_ON = "●"
_DOT_OFF = "○"
_COLOR_GREEN = "#27ae60"
_COLOR_YELLOW = "#f39c12"
_COLOR_GREY = ("gray60", "gray40")


class ConnectionPanel(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_obs_auto_control_changed: Callable[[bool], None],
        on_debug_changed: Callable[[bool], None],
        obs_auto_control: bool = False,
        debug: bool = False,
    ) -> None:
        super().__init__(parent, corner_radius=8)
        self._on_obs_auto_control_changed = on_obs_auto_control_changed
        self._on_debug_changed = on_debug_changed
        self._build_ui(obs_auto_control, debug)

    def _build_ui(self, obs_auto_control: bool, debug: bool) -> None:
        ctk.CTkLabel(
            self,
            text="Connections",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        # ── Impress row ────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Impress:").grid(
            row=1, column=0, padx=(12, 6), pady=4, sticky="w"
        )
        self._impress_dot = ctk.CTkLabel(self, text=_DOT_OFF, text_color=_COLOR_GREY)
        self._impress_dot.grid(row=1, column=1, padx=4, pady=4, sticky="w")
        self._impress_status = ctk.CTkLabel(self, text="Waiting", anchor="w")
        self._impress_status.grid(row=1, column=2, padx=(2, 12), pady=4, sticky="w")

        # ── Separator ──────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=("gray75", "gray30")).grid(
            row=2, column=0, columnspan=3, padx=12, pady=4, sticky="ew"
        )

        # ── OBS row ────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="OBS:").grid(
            row=3, column=0, padx=(12, 6), pady=4, sticky="w"
        )
        self._obs_dot = ctk.CTkLabel(self, text=_DOT_OFF, text_color=_COLOR_GREY)
        self._obs_dot.grid(row=3, column=1, padx=4, pady=4, sticky="w")
        self._obs_status = ctk.CTkLabel(self, text="Disconnected", anchor="w")
        self._obs_status.grid(row=3, column=2, padx=(2, 12), pady=4, sticky="w")

        self._obs_control_var = ctk.BooleanVar(value=obs_auto_control)
        ctk.CTkCheckBox(
            self,
            text="Control OBS recording",
            variable=self._obs_control_var,
            command=self._on_obs_control,
        ).grid(row=4, column=0, columnspan=3, padx=(28, 12), pady=(0, 4), sticky="w")

        self._debug_var = ctk.BooleanVar(value=debug)
        ctk.CTkCheckBox(
            self,
            text="Debug",
            variable=self._debug_var,
            command=self._on_debug_toggle,
        ).grid(row=5, column=0, columnspan=3, padx=(28, 12), pady=(0, 10), sticky="w")

        self.columnconfigure(2, weight=1)

    # ------------------------------------------------------------------ #
    # Public update methods (call from main thread only)                  #
    # ------------------------------------------------------------------ #

    def update_impress_status(
        self, connected: bool, in_presentation: bool = False
    ) -> None:
        if connected and in_presentation:
            self._impress_dot.configure(text=_DOT_ON, text_color=_COLOR_GREEN)
            self._impress_status.configure(text="In Presentation")
        elif connected:
            self._impress_dot.configure(text=_DOT_ON, text_color=_COLOR_YELLOW)
            self._impress_status.configure(text="Connected")
        else:
            self._impress_dot.configure(text=_DOT_OFF, text_color=_COLOR_GREY)
            self._impress_status.configure(text="Waiting")

    def update_obs_status(self, connected: bool, recording: bool = False) -> None:
        if connected and recording:
            self._obs_dot.configure(text=_DOT_ON, text_color=_COLOR_GREEN)
            self._obs_status.configure(text="Recording")
        elif connected:
            self._obs_dot.configure(text=_DOT_ON, text_color=_COLOR_GREEN)
            self._obs_status.configure(text="Connected")
        else:
            self._obs_dot.configure(text=_DOT_OFF, text_color=_COLOR_GREY)
            self._obs_status.configure(text="Disconnected")

    @property
    def obs_auto_control(self) -> bool:
        return self._obs_control_var.get()

    @property
    def debug(self) -> bool:
        return self._debug_var.get()

    # ------------------------------------------------------------------ #
    # Internal callbacks                                                  #
    # ------------------------------------------------------------------ #

    def _on_obs_control(self) -> None:
        self._on_obs_auto_control_changed(self._obs_control_var.get())

    def _on_debug_toggle(self) -> None:
        self._on_debug_changed(self._debug_var.get())
