import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config.defaults import (
    APP_GEOMETRY,
    APP_TITLE,
    DEFAULT_AUTOSAVE_INTERVAL_S,
    DEFAULT_BACKWARD_KEY,
    DEFAULT_FORWARD_KEY,
)
from models.slide_event import SlideEvent
from services.key_listener_service import (
    KeyListenerService,
    key_from_name,
    key_to_display,
)
from services.recording_service import RecordingService, RecordingState
from services.slide_index.key_count_provider import KeyCountSlideIndexProvider
from services.storage_service import StorageService
from ui.components.control_panel import ControlPanel
from ui.components.key_config_panel import KeyConfigPanel
from ui.components.save_panel import SavePanel


class App(ctk.CTk):
    """
    Root window. Assembles all panels and wires the service layer.

    Threading contract:
    - Service callbacks arrive from non-UI threads (pynput, Timer).
    - All such callbacks route through self.after(0, ...) to safely
      update the UI from the main thread.
    - Services are never called directly from Timer/pynput threads
      for any tkinter operation.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.resizable(False, False)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._autosave_interval_s: int = DEFAULT_AUTOSAVE_INTERVAL_S
        self._event_count: int = 0
        self._timer_job = None

        self._init_services()
        self._build_ui()
        self._wire_callbacks()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    # Initialisation                                                       #
    # ------------------------------------------------------------------ #

    def _init_services(self) -> None:
        self._slide_provider = KeyCountSlideIndexProvider()
        self._recording_service = RecordingService(self._slide_provider)
        self._storage_service = StorageService()
        self._key_listener = KeyListenerService(
            forward_key=key_from_name(DEFAULT_FORWARD_KEY),
            backward_key=key_from_name(DEFAULT_BACKWARD_KEY),
            on_forward=lambda: self._recording_service.register_event("forward"),
            on_backward=lambda: self._recording_service.register_event("backward"),
        )
        self._key_listener.start()

    def _build_ui(self) -> None:
        pack_opts = {"fill": "x", "padx": 16}

        self._control_panel = ControlPanel(
            self,
            on_record=self._on_record,
            on_stop=self._on_stop,
        )
        self._control_panel.pack(**pack_opts, pady=(16, 8))

        self._key_config_panel = KeyConfigPanel(
            self,
            on_capture_forward=self._start_capture_forward,
            on_capture_backward=self._start_capture_backward,
            forward_display=key_to_display(self._key_listener.forward_key),
            backward_display=key_to_display(self._key_listener.backward_key),
        )
        self._key_config_panel.pack(**pack_opts, pady=8)

        self._save_panel = SavePanel(
            self,
            on_path_changed=self._on_path_changed,
            on_manual_save=self._on_manual_save,
            on_autosave_interval_changed=self._on_autosave_interval_changed,
            default_interval=DEFAULT_AUTOSAVE_INTERVAL_S,
        )
        self._save_panel.pack(**pack_opts, pady=(8, 16))

    def _wire_callbacks(self) -> None:
        self._recording_service.on_event = self._on_slide_event_from_thread
        self._recording_service.on_state_change = self._on_state_change_from_thread

    # ------------------------------------------------------------------ #
    # Recording actions (called from main thread via button)              #
    # ------------------------------------------------------------------ #

    def _on_record(self) -> None:
        if not self._save_panel.save_path:
            messagebox.showwarning(
                "No save path",
                "Please select a save path before starting the recording.",
            )
            return

        # Warn if stopping over an unsaved session
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
        self._recording_service.start(title=self._control_panel.title)

        # Generate the initial JSON file as soon as recording begins
        snapshot = self._recording_service.get_session_snapshot()
        if snapshot:
            try:
                self._storage_service.save_session(snapshot, self._save_panel.save_path)
            except OSError as exc:
                messagebox.showerror("Initial save failed", str(exc))

    def _on_stop(self) -> None:
        self._recording_service.stop()
        self._storage_service.finalize_session()

    # ------------------------------------------------------------------ #
    # Callbacks from service threads — routed to main thread via after()  #
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
            # Cancel any stale autosave before starting fresh
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
            self.after(0, ui_callback, key_to_display(key))

        self._key_listener.capture_next_key(_on_captured)

    def _start_capture_backward(self, ui_callback: callable) -> None:
        def _on_captured(key) -> None:
            self._key_listener.set_backward_key(key)
            self.after(0, ui_callback, key_to_display(key))

        self._key_listener.capture_next_key(_on_captured)

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #

    def _on_path_changed(self, path: str) -> None:
        self._storage_service.set_save_path(path)

    def _on_manual_save(self) -> None:
        """Save Now: always opens a dialog so the user can pick any location."""
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
            if answer is None:  # Cancel — abort close
                return
            if answer:  # Yes — attempt save
                if not self._save_snapshot(snapshot):
                    return  # Save failed or was cancelled — abort close

        self._recording_service.stop()
        self._storage_service.stop_autosave()
        self._key_listener.stop()
        self.destroy()

    def _save_snapshot(self, snapshot) -> bool:
        """
        Save *snapshot* to the configured primary path, or prompt for one.
        Returns True on success, False if the user cancelled or an error occurred.
        """
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
