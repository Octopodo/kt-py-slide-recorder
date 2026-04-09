"""
ObsSettingsPanel — UI for configuring the OBS WebSocket connection.

Fields: host, port, password, and a Connect button.
Settings are persisted immediately via the Settings object on change.
"""

from typing import Callable

import customtkinter as ctk


class ObsSettingsPanel(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_connect: Callable[[str, int, str], None],
        obs_host: str = "localhost",
        obs_port: int = 4455,
        obs_password: str = "",
    ) -> None:
        super().__init__(parent, corner_radius=8)
        self._on_connect = on_connect
        self._build_ui(obs_host, obs_port, obs_password)

    def _build_ui(self, host: str, port: int, password: str) -> None:
        ctk.CTkLabel(
            self,
            text="OBS Settings",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 6), sticky="w")

        # Host
        ctk.CTkLabel(self, text="Host:").grid(
            row=1, column=0, padx=(12, 6), pady=4, sticky="e"
        )
        self._host_var = ctk.StringVar(value=host)
        ctk.CTkEntry(self, textvariable=self._host_var, width=200).grid(
            row=1, column=1, padx=(4, 12), pady=4, sticky="ew"
        )

        # Port
        ctk.CTkLabel(self, text="Port:").grid(
            row=2, column=0, padx=(12, 6), pady=4, sticky="e"
        )
        self._port_var = ctk.StringVar(value=str(port))
        ctk.CTkEntry(self, textvariable=self._port_var, width=200).grid(
            row=2, column=1, padx=(4, 12), pady=4, sticky="ew"
        )

        # Password
        ctk.CTkLabel(self, text="Password:").grid(
            row=3, column=0, padx=(12, 6), pady=4, sticky="e"
        )
        self._password_var = ctk.StringVar(value=password)
        ctk.CTkEntry(self, textvariable=self._password_var, show="*", width=200).grid(
            row=3, column=1, padx=(4, 12), pady=4, sticky="ew"
        )

        # Connect button
        ctk.CTkButton(
            self,
            text="Connect / Reconnect",
            command=self._on_connect_clicked,
        ).grid(row=4, column=0, columnspan=2, padx=12, pady=(6, 10))

        self.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------ #
    # Public                                                              #
    # ------------------------------------------------------------------ #

    @property
    def host(self) -> str:
        return self._host_var.get().strip()

    @property
    def port(self) -> int:
        try:
            return int(self._port_var.get().strip())
        except ValueError:
            return 4455

    @property
    def password(self) -> str:
        return self._password_var.get()

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    def _on_connect_clicked(self) -> None:
        self._on_connect(self.host, self.port, self.password)
