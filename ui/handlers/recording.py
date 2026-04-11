"""Recording actions, state-machine callbacks, and chronometer."""

import logging
from tkinter import messagebox

from models.slide_event import SlideEvent
from services.recording_service import RecordingState

log = logging.getLogger(__name__)


class RecordingHandlersMixin:
    """Start/stop recording, react to state transitions, drive the timer."""

    # ------------------------------------------------------------------ #
    # Recording actions                                                    #
    # ------------------------------------------------------------------ #

    def trigger_start(self) -> None:
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
        self._settings.last_session_title = self._control_panel.title
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
        self._recording_service.stop()
        self._storage_service.finalize_session()

        if self._connection_panel.obs_auto_control and self._obs_adapter.is_connected:
            self._obs_adapter.stop_record()

    # ------------------------------------------------------------------ #
    # RecordingService callbacks (worker thread → main thread)             #
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
