import json
import os
import threading
from dataclasses import asdict
from typing import Callable, Optional

from models.session import Session


class StorageService:
    """
    Handles JSON serialization and persistence of recording sessions.

    Final save: save_session(session, path) — blocks briefly on I/O.
    Autosave: a restartable threading.Timer writes to <filename>_autosave.json
              in the same directory as the primary save path.

    Thread safety:
    - _write_lock ensures autosave and manual save don't interleave on disk.
    - The Timer thread never calls into tkinter; it only does file I/O.
    """

    def __init__(self) -> None:
        self._save_path: str = ""
        self._autosave_timer: Optional[threading.Timer] = None
        self._autosave_interval_s: int = 60
        self._session_getter: Optional[Callable[[], Optional[Session]]] = None
        self._write_lock = threading.Lock()

    def set_save_path(self, path: str) -> None:
        self._save_path = path

    @property
    def save_path(self) -> str:
        return self._save_path

    def save_session(self, session: Session, path: Optional[str] = None) -> str:
        """
        Serialize *session* and write to *path* (or the configured save path).
        Returns the path actually written to. Raises ValueError if no path is set.
        """
        target = path or self._save_path
        if not target:
            raise ValueError("No save path configured.")
        payload = self._serialize(session)
        with self._write_lock:
            with open(target, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
        return target

    def start_autosave(
        self,
        session_getter: Callable[[], Optional[Session]],
        interval_s: int,
    ) -> None:
        """
        Start the autosave loop. Cancels any existing timer first.
        *session_getter* must be thread-safe (RecordingService.get_session_snapshot).
        """
        self.stop_autosave()
        self._session_getter = session_getter
        self._autosave_interval_s = interval_s
        self._schedule_next()

    def stop_autosave(self) -> None:
        """Cancel the pending autosave timer. Safe to call if not running."""
        if self._autosave_timer is not None:
            self._autosave_timer.cancel()
            self._autosave_timer = None

    def finalize_session(self) -> None:
        """
        Stop the autosave timer, flush the final snapshot to the primary path,
        and delete the autosave file.

        Call this when a recording ends so the primary file contains all events
        and no stale autosave file is left behind.
        Safe to call if autosave was not running.
        """
        self.stop_autosave()

        if self._save_path and self._session_getter:
            session = self._session_getter()
            if session:
                try:
                    cleaned = self._strip_non_slide_events(session)
                    payload = self._serialize(cleaned)
                    with self._write_lock:
                        with open(self._save_path, "w", encoding="utf-8") as fh:
                            json.dump(payload, fh, indent=2, ensure_ascii=False)
                except OSError:
                    pass  # Best-effort; keep going to attempt autosave cleanup

            autosave = self._autosave_path()
            try:
                if os.path.exists(autosave):
                    os.remove(autosave)
            except OSError:
                pass

        self._session_getter = None

    def _schedule_next(self) -> None:
        self._autosave_timer = threading.Timer(
            self._autosave_interval_s, self._autosave_tick
        )
        self._autosave_timer.daemon = True
        self._autosave_timer.start()

    def _autosave_tick(self) -> None:
        """Called by the Timer thread. Writes snapshot then reschedules."""
        if self._save_path and self._session_getter:
            session = self._session_getter()
            if session and session.events:
                try:
                    payload = self._serialize(session)
                    autosave_path = self._autosave_path()
                    with self._write_lock:
                        with open(autosave_path, "w", encoding="utf-8") as fh:
                            json.dump(payload, fh, indent=2, ensure_ascii=False)
                except OSError:
                    pass  # Best-effort; never crash the app on autosave failure
        self._schedule_next()

    def _autosave_path(self) -> str:
        base, ext = os.path.splitext(self._save_path)
        return f"{base}_autosave{ext}"

    @staticmethod
    def _serialize(session: Session) -> dict:
        return {
            "title": session.title,
            "session_start_iso": session.start_iso,
            "duration_s": round(session.duration_s, 3),
            "total_events": len(session.events),
            "events": [asdict(e) for e in session.events],
        }

    @staticmethod
    def _strip_non_slide_events(session: Session) -> Session:
        """Return a shallow copy keeping only 'initial' and 'slide_changed' events."""
        _KEEP = {"initial", "slide_changed", "record_end"}
        filtered = [e for e in session.events if e.event_type in _KEEP]
        return Session(
            start_iso=session.start_iso,
            title=session.title,
            events=filtered,
            duration_s=session.duration_s,
        )
