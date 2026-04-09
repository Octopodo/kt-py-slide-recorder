"""
Formal contracts (Protocols) for all pluggable components.

These interfaces are the shared boundary between the App hub and external
adapters (Impress, OBS, future sources). Once stable, do not change existing
method signatures — add new optional methods instead. The "v" field in the
wire protocol performs the same role at the network layer.

Three protocol families:
  - SlideEventSource  : produces slide-change events (Impress macro, keyboard)
  - SessionTriggerSource : requests session start/stop (Impress slideshow, future)
  - ExternalRecorderSink : receives record commands (OBS, future recorders)
"""

from typing import Callable, Optional, Protocol, runtime_checkable


@runtime_checkable
class SlideEventSource(Protocol):
    """
    Anything that can report an absolute slide index change.

    The callback receives the new 1-based slide index.
    Implementations must be thread-safe: the callback may be called from
    a background thread; callers are responsible for dispatching to the UI
    thread if needed (via app.after(0, ...)).
    """

    on_slide_changed: Optional[Callable[[int], None]]

    @property
    def is_active(self) -> bool:
        """True when the source is running and providing events."""
        ...

    def start(self) -> None:
        """Begin producing events. Idempotent."""
        ...

    def stop(self) -> None:
        """Stop producing events. Idempotent."""
        ...


@runtime_checkable
class SessionTriggerSource(Protocol):
    """
    Anything that can request the app to start or stop a recording session.

    Callbacks are invoked from background threads — the App must marshal
    them to the main thread via after(0, ...).
    """

    on_start_requested: Optional[Callable[[], None]]
    on_stop_requested: Optional[Callable[[], None]]

    @property
    def is_active(self) -> bool:
        """True when the trigger source is connected and listening."""
        ...

    def start(self) -> None:
        """Begin listening for trigger events. Idempotent."""
        ...

    def stop(self) -> None:
        """Stop listening. Idempotent."""
        ...


@runtime_checkable
class ExternalRecorderSink(Protocol):
    """
    Anything that can be told to start or stop recording.

    Implementations must be non-blocking: start_record() / stop_record()
    return immediately and do nothing if not connected.
    The on_state_changed callback reports the actual recorder state (e.g.
    OBS confirming that recording has started/stopped).
    """

    on_state_changed: Optional[Callable[[bool], None]]

    @property
    def is_connected(self) -> bool:
        """True when the sink is reachable."""
        ...

    def connect(self) -> None:
        """
        Attempt to connect to the external recorder (non-blocking).
        Connection retries should be managed internally in a background thread.
        """
        ...

    def disconnect(self) -> None:
        """Cleanly disconnect. Idempotent."""
        ...

    def start_record(self) -> None:
        """Tell the recorder to begin recording. No-op if not connected."""
        ...

    def stop_record(self) -> None:
        """Tell the recorder to stop recording. No-op if not connected."""
        ...
