"""Save, autosave, and application shutdown handlers."""

import os
from tkinter import filedialog, messagebox

from services.recording_service import RecordingState


class SaveHandlersMixin:
    """Mixin for persistence (manual save, autosave) and graceful shutdown."""

    # ------------------------------------------------------------------ #
    # Save path                                                            #
    # ------------------------------------------------------------------ #

    def _on_path_changed(self, path: str) -> None:
        self._storage_service.set_save_path(path)
        self._settings.last_save_path = path

        basename = os.path.basename(path)
        name, _ = os.path.splitext(basename)
        if name:
            self._control_panel.set_title(name)
            self._settings.last_session_title = name

    # ------------------------------------------------------------------ #
    # Manual save                                                          #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Autosave                                                             #
    # ------------------------------------------------------------------ #

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
