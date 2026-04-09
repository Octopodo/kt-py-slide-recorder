import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config.defaults import APP_GEOMETRY, APP_TITLE
from config.settings import Settings
from models.slide_event import SlideEvent
from services.impress_bridge import ImpressBridge
from services.key_listener_service import (
    KeyListenerService,
    key_from_name,
    key_to_display,
)
from services.obs_adapter import ObsAdapter
from services.recording_service import RecordingService, RecordingState
from services.slide_index.impress_provider import ImpressSlideIndexProvider
from services.slide_index.key_count_provider import KeyCountSlideIndexProvider
from services.storage_service import StorageService
from ui.components.connection_panel import ConnectionPanel
from ui.components.control_panel import ControlPanel
from ui.components.key_config_panel import KeyConfigPanel
from ui.components.obs_settings_panel import ObsSettingsPanel
from ui.components.save_panel import SavePanel


class _CollapsibleSection(ctk.CTkFrame):
    """Clickable header that shows/hides a content_frame below it."""

    def __init__(self, parent, title: str, expanded: bool = True, **kw) -> None:
        super().__init__(parent, corner_radius=8, **kw)
        self._expanded = expanded
        self._title = title
        self._header = ctk.CTkButton(
            self,
            text=self._label(),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray82", "gray28"),
            command=self._toggle,
        )
        self._header.pack(fill="x", padx=2, pady=(4, 0))
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        if expanded:
            self.content_frame.pack(fill="x", padx=4, pady=(0, 6))

    def _label(self) -> str:
        return f"{'\u25bc' if self._expanded else '\u25b6'}  {self._title}"

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._header.configure(text=self._label())
        if self._expanded:
            self.content_frame.pack(fill="x", padx=4, pady=(0, 6))
        else:
            self.content_frame.pack_forget()


class App(ctk.CTk):
    """
    Root window and orchestration hub.

    Sources (Impress macro, keyboard) feed slide-change events in.
    Sinks (OBS) receive record commands out.
    All external callbacks are marshalled to the main thread via after(0,...).

    Threading contract:
    - Service callbacks arrive from non-UI threads (pynput, socket, OBS event).
    - All such callbacks route through self.after(0, ...) to safely
      update the UI from the main thread.
    - Services are never called directly from those threads for any
      tkinter operation.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.resizable(False, False)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._settings = Settings()
        self._autosave_interval_s: int = self._settings.autosave_interval_s
        self._event_count: int = 0
        self._timer_job = None
        self._obs_recording: bool = False

        self._init_services()
        self._build_ui()
        self._wire_callbacks()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    # Initialisation                                                       #
    # ------------------------------------------------------------------ #

    def _init_services(self) -> None:
        # Slide providers — Impress (real index) with keyboard fallback
        self._impress_provider = ImpressSlideIndexProvider()
        self._key_provider = KeyCountSlideIndexProvider()

        self._recording_service = RecordingService(self._impress_provider)
        self._storage_service = StorageService()

        # Keyboard listener — fallback when Impress is not connected
        self._key_listener = KeyListenerService(
            forward_key=key_from_name(self._settings.forward_key),
            backward_key=key_from_name(self._settings.backward_key),
            on_forward=self._on_keyboard_forward,
            on_backward=self._on_keyboard_backward,
        )
        self._key_listener.start()

        # Impress TCP bridge — primary slide source
        self._impress_bridge = ImpressBridge(port=self._settings.impress_bridge_port)
        self._impress_bridge.on_slide_changed = self._on_impress_slide_changed
        self._impress_bridge.on_slideshow_started = self._on_impress_slideshow_started
        self._impress_bridge.on_slideshow_ended = self._on_impress_slideshow_ended
        self._impress_bridge.on_client_connected = self._on_impress_connected
        self._impress_bridge.on_client_disconnected = self._on_impress_disconnected
        self._impress_bridge.start()

        # OBS adapter — external recorder sink
        self._obs_adapter = ObsAdapter(
            host=self._settings.obs_host,
            port=self._settings.obs_port,
            password=self._settings.obs_password,
        )
        self._obs_adapter.on_state_changed = self._on_obs_state_changed
        self._obs_adapter.on_connection_changed = self._on_obs_connection_changed
        self._obs_adapter.connect()

    def _build_ui(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        sec_opts = {"fill": "x", "padx": 4, "pady": 4}

        # ── Recording ──────────────────────────────────────────────────
        sec_record = _CollapsibleSection(scroll, "Recording", expanded=True)
        sec_record.pack(**sec_opts)
        self._control_panel = ControlPanel(
            sec_record.content_frame,
            on_record=self.trigger_start,
            on_stop=self.trigger_stop,
        )
        self._control_panel.pack(fill="x")

        # ── Key Bindings ───────────────────────────────────────────────
        sec_keys = _CollapsibleSection(scroll, "Key Bindings", expanded=True)
        sec_keys.pack(**sec_opts)
        self._key_config_panel = KeyConfigPanel(
            sec_keys.content_frame,
            on_capture_forward=self._start_capture_forward,
            on_capture_backward=self._start_capture_backward,
            forward_display=key_to_display(self._key_listener.forward_key),
            backward_display=key_to_display(self._key_listener.backward_key),
        )
        self._key_config_panel.pack(fill="x")

        # ── Connections ────────────────────────────────────────────────
        sec_conn = _CollapsibleSection(scroll, "Connections", expanded=True)
        sec_conn.pack(**sec_opts)
        self._connection_panel = ConnectionPanel(
            sec_conn.content_frame,
            on_obs_auto_control_changed=self._on_obs_auto_control_changed,
            obs_auto_control=self._settings.obs_auto_control,
        )
        self._connection_panel.pack(fill="x")

        # ── OBS Settings (collapsed by default) ────────────────────────
        sec_obs = _CollapsibleSection(scroll, "OBS Settings", expanded=False)
        sec_obs.pack(**sec_opts)
        self._obs_settings_panel = ObsSettingsPanel(
            sec_obs.content_frame,
            on_connect=self._on_obs_reconnect,
            obs_host=self._settings.obs_host,
            obs_port=self._settings.obs_port,
            obs_password=self._settings.obs_password,
        )
        self._obs_settings_panel.pack(fill="x")

        # ── Save ───────────────────────────────────────────────────────
        sec_save = _CollapsibleSection(scroll, "Save", expanded=True)
        sec_save.pack(**sec_opts)
        self._save_panel = SavePanel(
            sec_save.content_frame,
            on_path_changed=self._on_path_changed,
            on_manual_save=self._on_manual_save,
            on_autosave_interval_changed=self._on_autosave_interval_changed,
            default_interval=self._autosave_interval_s,
        )
        self._save_panel.pack(fill="x")

    def _wire_callbacks(self) -> None:
        self._recording_service.on_event = self._on_slide_event_from_thread
        self._recording_service.on_state_change = self._on_state_change_from_thread

    # ------------------------------------------------------------------ #
    # Recording actions (called from main thread via button)              #
    # ------------------------------------------------------------------ #

    def trigger_start(self) -> None:
        """Start a recording session. Called by UI button or external sources."""
        if not self._save_panel.save_path:
            messagebox.showwarning(
                "No save path",
                "Please select a save path before starting the recording.",
            )
            return

        snapshot = self._recording_service.get_session_snapshot()
        if (
            snapshot
            and snapshot.events
            and self._recording_service.state == RecordingState.STOPPED
        ):
            if not messagebox.askyesno(
                "Start new recording?",
                "Starting a new recording will discard the previous unsaved session.\n"
                "Continue?",
            ):
                return

        self._event_count = 0
        self._control_panel.reset_display()
        self._impress_provider.reset()
        self._key_provider.reset()
        self._recording_service.start(title=self._control_panel.title)

        snapshot = self._recording_service.get_session_snapshot()
        if snapshot:
            try:
                self._storage_service.save_session(snapshot, self._save_panel.save_path)
            except OSError as exc:
                messagebox.showerror("Initial save failed", str(exc))

        if self._connection_panel.obs_auto_control and self._obs_adapter.is_connected:
            self._obs_adapter.start_record()

    def trigger_stop(self) -> None:
        """Stop the current recording session."""
        self._recording_service.stop()
        self._storage_service.finalize_session()

        if self._connection_panel.obs_auto_control and self._obs_adapter.is_connected:
            self._obs_adapter.stop_record()

    # ------------------------------------------------------------------ #
    # Impress bridge callbacks (socket thread → after(0,...) → main)      #
    # ------------------------------------------------------------------ #

    def _on_impress_slide_changed(self, index: int, total: int) -> None:
        self._impress_provider.notify_slide(index, total)
        self._recording_service.register_slide_change(index)

    def _on_impress_slideshow_started(self, total: int) -> None:
        self._impress_provider.reset()
        self.after(0, self._connection_panel.update_impress_status, True, True)

    def _on_impress_slideshow_ended(self) -> None:
        self.after(0, self._connection_panel.update_impress_status, True, False)

    def _on_impress_connected(self) -> None:
        self.after(0, self._connection_panel.update_impress_status, True, False)

    def _on_impress_disconnected(self) -> None:
        self.after(0, self._connection_panel.update_impress_status, False, False)

    # ------------------------------------------------------------------ #
    # OBS callbacks (OBS event thread → after(0,...) → main)              #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Keyboard fallback (when Impress is not connected)                   #
    # ------------------------------------------------------------------ #

    def _on_keyboard_forward(self) -> None:
        if self._impress_bridge.is_client_connected:
            return
        self._key_provider.on_forward()
        self._recording_service.register_slide_change(self._key_provider.current_index)

    def _on_keyboard_backward(self) -> None:
        if self._impress_bridge.is_client_connected:
            return
        self._key_provider.on_backward()
        self._recording_service.register_slide_change(self._key_provider.current_index)

    # ------------------------------------------------------------------ #
    # Callbacks from RecordingService threads → main thread               #
    # ------------------------------------------------------------------ #

    def _on_slide_event_from_thread(self, event: SlideEvent) -> None:
        self.after(0, self._handle_slide_event, event)

    def _on_state_change_from_thread(self, state: RecordingState) -> None:
        self.after(0, self._handle_state_change, state)

    def _handle_slide_event(self, _event: SlideEvent) -> None:
        self._event_count += 1
        self._control_panel.update_event_count(self._event_count)

    def _handle_state_change(self, state: RecordingState) -> None:
        if state == RecordingState.RECORDING:
            self._control_panel.set_recording(True)
            self._key_config_panel.set_enabled(False)
            self._save_panel.enable_save_button(False)
            self._start_chronometer()
            self._storage_service.stop_autosave()
            self._storage_service.start_autosave(
                session_getter=self._recording_service.get_session_snapshot,
                interval_s=self._autosave_interval_s,
            )
        elif state == RecordingState.STOPPED:
            self._control_panel.set_recording(False)
            self._key_config_panel.set_enabled(True)
            self._save_panel.enable_save_button(True)
            self._stop_chronometer()
        elif state == RecordingState.IDLE:
            self._control_panel.set_recording(False)
            self._key_config_panel.set_enabled(True)
            self._save_panel.enable_save_button(False)
            self._stop_chronometer()

    # ------------------------------------------------------------------ #
    # Chronometer                                                          #
    # ------------------------------------------------------------------ #

    def _start_chronometer(self) -> None:
        self._tick_chronometer()

    def _tick_chronometer(self) -> None:
        elapsed = self._recording_service.get_elapsed_s()
        self._control_panel.update_elapsed(elapsed)
        self._timer_job = self.after(100, self._tick_chronometer)

    def _stop_chronometer(self) -> None:
        if self._timer_job is not None:
            self.after_cancel(self._timer_job)
            self._timer_job = None

    # ------------------------------------------------------------------ #
    # Key capture                                                          #
    # ------------------------------------------------------------------ #

    def _start_capture_forward(self, ui_callback: callable) -> None:
        def _on_captured(key) -> None:
            self._key_listener.set_forward_key(key)
            self._settings.forward_key = key_to_display(key)
            self.after(0, ui_callback, key_to_display(key))

        self._key_listener.capture_next_key(_on_captured)

    def _start_capture_backward(self, ui_callback: callable) -> None:
        def _on_captured(key) -> None:
            self._key_listener.set_backward_key(key)
            self._settings.backward_key = key_to_display(key)
            self.after(0, ui_callback, key_to_display(key))

        self._key_listener.capture_next_key(_on_captured)

    # ------------------------------------------------------------------ #
    # Settings callbacks                                                   #
    # ------------------------------------------------------------------ #

    def _on_obs_auto_control_changed(self, value: bool) -> None:
        self._settings.obs_auto_control = value

    def _on_obs_reconnect(self, host: str, port: int, password: str) -> None:
        self._settings.obs_host = host
        self._settings.obs_port = port
        self._settings.obs_password = password
        self._obs_adapter.update_settings(host, port, password)

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #

    def _on_path_changed(self, path: str) -> None:
        self._storage_service.set_save_path(path)

    def _on_manual_save(self) -> None:
        snapshot = self._recording_service.get_session_snapshot()
        if not snapshot or not snapshot.events:
            messagebox.showwarning("No data", "No recorded events to save.")
            return

        initial_dir = (
            os.path.dirname(self._save_panel.save_path)
            if self._save_panel.save_path
            else ""
        )
        path = filedialog.asksaveasfilename(
            title="Save recording",
            initialdir=initial_dir,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._storage_service.save_session(snapshot, path)
            messagebox.showinfo("Saved", f"Session saved to:\n{path}")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))

    def _on_autosave_interval_changed(self, interval_s: int) -> None:
        self._autosave_interval_s = interval_s
        self._settings.autosave_interval_s = interval_s
        if self._recording_service.state == RecordingState.RECORDING:
            self._storage_service.stop_autosave()
            self._storage_service.start_autosave(
                session_getter=self._recording_service.get_session_snapshot,
                interval_s=interval_s,
            )

    # ------------------------------------------------------------------ #
    # Shutdown                                                             #
    # ------------------------------------------------------------------ #

    def _on_close(self) -> None:
        snapshot = self._recording_service.get_session_snapshot()
        if snapshot and snapshot.events:
            answer = messagebox.askyesnocancel(
                "Unsaved data",
                "You have unsaved recording data.\nSave before closing?",
            )
            if answer is None:
                return
            if answer:
                if not self._save_snapshot(snapshot):
                    return

        self._recording_service.stop()
        self._storage_service.stop_autosave()
        self._key_listener.stop()
        self._impress_bridge.stop()
        self._obs_adapter.disconnect()
        self.destroy()

    def _save_snapshot(self, snapshot) -> bool:
        path = self._save_panel.save_path
        if not path:
            path = filedialog.asksaveasfilename(
                title="Save recording",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return False
            self._storage_service.set_save_path(path)
        try:
            self._storage_service.save_session(snapshot, path)
            return True
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return False
