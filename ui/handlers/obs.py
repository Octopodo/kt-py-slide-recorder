"""OBS WebSocket callback and settings handlers."""

from tkinter import messagebox


class ObsHandlersMixin:
    """Mixin for OBS recording state, connection, and settings changes."""

    def _on_obs_state_changed(self, active: bool) -> None:
        self._obs_recording = active
        self.after(0, self._handle_obs_status_update, self._obs_adapter.is_connected, active)

    def _on_obs_connection_changed(self, connected: bool) -> None:
        self.after(
            0,
            self._handle_obs_status_update,
            connected,
            self._obs_recording if connected else False,
        )

    def _handle_obs_status_update(self, connected: bool, recording: bool) -> None:
        self._connection_panel.update_obs_status(connected, recording)
        panel = self._floating_record_panel
        if panel is not None and panel.winfo_exists():
            panel.update_obs_status(connected, recording)

    def _on_obs_connection_attempt(self, success: bool, message: str) -> None:
        self.after(0, self._show_obs_connection_result, success, message)

    def _show_obs_connection_result(self, success: bool, message: str) -> None:
        if not self._connection_panel.debug:
            return
        if success:
            messagebox.showinfo("OBS Connection", message)
        else:
            messagebox.showerror("OBS Connection", message)

    def _on_debug_changed(self, value: bool) -> None:
        self._settings.debug = value

    def _on_obs_auto_control_changed(self, value: bool) -> None:
        self._settings.obs_auto_control = value

    def _on_obs_reconnect(self, host: str, port: int, password: str) -> None:
        self._settings.obs_host = host
        self._settings.obs_port = port
        self._settings.obs_password = password
        self._obs_adapter.update_settings(host, port, password)
