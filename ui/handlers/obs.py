"""OBS WebSocket callback and settings handlers."""


class ObsHandlersMixin:
    """Mixin for OBS recording state, connection, and settings changes."""

    def _on_obs_state_changed(self, active: bool) -> None:
        self._obs_recording = active
        self.after(
            0,
            self._connection_panel.update_obs_status,
            self._obs_adapter.is_connected,
            active,
        )

    def _on_obs_connection_changed(self, connected: bool) -> None:
        self.after(
            0,
            self._connection_panel.update_obs_status,
            connected,
            self._obs_recording if connected else False,
        )

    def _on_obs_auto_control_changed(self, value: bool) -> None:
        self._settings.obs_auto_control = value

    def _on_obs_reconnect(self, host: str, port: int, password: str) -> None:
        self._settings.obs_host = host
        self._settings.obs_port = port
        self._settings.obs_password = password
        self._obs_adapter.update_settings(host, port, password)
