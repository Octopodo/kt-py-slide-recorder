import threading
import time
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Optional

from models.session import Session
from models.slide_event import SlideEvent
from services.slide_index.base import SlideIndexProvider


class RecordingState(Enum):
    IDLE = auto()
    RECORDING = auto()
    STOPPED = auto()


class RecordingService:
    """
    State machine: IDLE → RECORDING → STOPPED → IDLE (or RECORDING again).

    All state mutations are protected by a threading.Lock so the service
    is safe to call from both the main (UI) thread and the pynput listener thread.

    Callbacks (on_event, on_state_change) are invoked *outside* the lock
    and may be called from a non-UI thread — callers must schedule UI updates
    via app.after(0, ...).
    """

    def __init__(self, slide_index_provider: SlideIndexProvider) -> None:
        self._provider = slide_index_provider
        self._lock = threading.Lock()
        self._state = RecordingState.IDLE
        self._session: Optional[Session] = None
        self._start_monotonic: float = 0.0

        # Callbacks — set by the UI layer
        self.on_event: Optional[Callable[[SlideEvent], None]] = None
        self.on_state_change: Optional[Callable[[RecordingState], None]] = None

    @property
    def state(self) -> RecordingState:
        with self._lock:
            return self._state

    def start(self, title: str = "") -> None:
        """Start a new recording session. Safe to call from IDLE or STOPPED."""
        with self._lock:
            if self._state == RecordingState.RECORDING:
                return
            self._provider.reset()
            self._start_monotonic = time.monotonic()
            self._session = Session(
                start_iso=datetime.now().astimezone().isoformat(),
                title=title,
            )
            self._state = RecordingState.RECORDING

        if self.on_state_change:
            self.on_state_change(RecordingState.RECORDING)

    def stop(self) -> None:
        """Stop the current recording. No-op if not recording."""
        with self._lock:
            if self._state != RecordingState.RECORDING:
                return
            if self._session is not None:
                self._session.duration_s = time.monotonic() - self._start_monotonic
            self._state = RecordingState.STOPPED

        if self.on_state_change:
            self.on_state_change(RecordingState.STOPPED)

    def register_event(self, direction: str) -> None:
        """
        Record a slide navigation event. Called from the pynput thread.
        direction must be "forward" or "backward".
        """
        event: Optional[SlideEvent] = None
        with self._lock:
            if self._state != RecordingState.RECORDING or self._session is None:
                return
            if direction == "forward":
                self._provider.on_forward()
            else:
                self._provider.on_backward()
            event = SlideEvent(
                time_s=round(time.monotonic() - self._start_monotonic, 3),
                direction=direction,
                slide_index=self._provider.current_index,
            )
            self._session.events.append(event)

        if event is not None and self.on_event:
            self.on_event(event)

    def get_elapsed_s(self) -> float:
        """Elapsed seconds since recording started. Returns 0 if not recording."""
        with self._lock:
            if self._state != RecordingState.RECORDING:
                return 0.0
            return time.monotonic() - self._start_monotonic

    def get_session_snapshot(self) -> Optional[Session]:
        """
        Returns a snapshot of the current session (copy of events list).
        Safe for serialization — does not hold the lock during I/O.
        Returns None if no session exists.
        """
        with self._lock:
            if self._session is None:
                return None
            duration = (
                self._session.duration_s
                if self._state == RecordingState.STOPPED
                else time.monotonic() - self._start_monotonic
            )
            return Session(
                start_iso=self._session.start_iso,
                title=self._session.title,
                events=list(self._session.events),
                duration_s=round(duration, 3),
            )
