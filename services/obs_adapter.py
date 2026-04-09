"""
ObsAdapter — wraps obsws-python to control an OBS instance over WebSocket v5.

Connection topology:
  This app is a WebSocket CLIENT. OBS is the WebSocket SERVER.
  This app never opens a server socket for OBS.
  OBS can run on the same machine (host="localhost") or on another machine
  on the LAN (host="192.168.1.x"). Only OBS_HOST in config changes — all
  other code is identical.

Design:
  - connect() is non-blocking: spawns a background thread that tries to
    reach OBS and retries on failure with exponential backoff.
  - start_record() / stop_record() are thread-safe no-ops when not connected.
  - An EventClient background thread listens for RecordStateChanged and
    ExitStarted events pushed by OBS.
  - on_state_changed(active: bool) callback is called from the event thread;
    App must marshal to UI thread via app.after(0, ...).
  - on_connection_changed(connected: bool) notifies the App when OBS
    connects or disconnects so the UI indicator can update.

Requires: obsws-python (pip install obsws-python)
"""

import threading
import time
from typing import Callable, Optional

try:
    import obsws_python as obs
except ImportError:
    obs = None  # obsws-python not installed — adapter degrades gracefully


_RETRY_DELAYS = (2, 4, 8, 16, 30)  # seconds between reconnect attempts


class ObsAdapter:
    """
    Controls OBS recording via WebSocket v5.

    Implements ExternalRecorderSink protocol (compatible with App hub).
    """

    def __init__(self, host: str, port: int, password: str) -> None:
        self._host = host
        self._port = port
        self._password = password

        self._req_client: Optional[object] = None
        self._event_client: Optional[object] = None
        self._connected = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._connect_thread: Optional[threading.Thread] = None

        # Callbacks — set by App after construction
        self.on_state_changed: Optional[Callable[[bool], None]] = None
        self.on_connection_changed: Optional[Callable[[bool], None]] = None

    # ------------------------------------------------------------------ #
    # Public API (ExternalRecorderSink protocol)                          #
    # ------------------------------------------------------------------ #

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def connect(self) -> None:
        """
        Begin attempting to connect to OBS in the background. Idempotent.
        Retries automatically until stop() is called.
        """
        if obs is None:
            return  # obsws-python not available
        if self._connect_thread and self._connect_thread.is_alive():
            return
        self._stop_event.clear()
        self._connect_thread = threading.Thread(
            target=self._connect_loop, daemon=True, name="ObsAdapter-connect"
        )
        self._connect_thread.start()

    def disconnect(self) -> None:
        """Clean up all OBS connections. Idempotent."""
        self._stop_event.set()
        self._teardown()

    def start_record(self) -> None:
        """Tell OBS to start recording. No-op if not connected."""
        with self._lock:
            client = self._req_client if self._connected else None
        if client is None:
            return
        try:
            client.start_record()
        except Exception:
            pass

    def stop_record(self) -> None:
        """Tell OBS to stop recording. No-op if not connected."""
        with self._lock:
            client = self._req_client if self._connected else None
        if client is None:
            return
        try:
            client.stop_record()
        except Exception:
            pass

    def update_settings(self, host: str, port: int, password: str) -> None:
        """Update connection settings and reconnect. Called from UI thread."""
        self._host = host
        self._port = port
        self._password = password
        self.disconnect()
        self.connect()

    # ------------------------------------------------------------------ #
    # Internal — connection loop                                           #
    # ------------------------------------------------------------------ #

    def _connect_loop(self) -> None:
        delay_idx = 0
        while not self._stop_event.is_set():
            try:
                self._try_connect()
                # Connection established — wait until it drops
                self._stop_event.wait()  # blocks until disconnect() is called
                return
            except Exception:
                delay = _RETRY_DELAYS[min(delay_idx, len(_RETRY_DELAYS) - 1)]
                delay_idx += 1
                self._stop_event.wait(timeout=delay)

    def _try_connect(self) -> None:
        if obs is None:
            raise RuntimeError("obsws-python not installed")

        req = obs.ReqClient(
            host=self._host,
            port=self._port,
            password=self._password,
            timeout=5,
        )
        event = obs.EventClient(
            host=self._host,
            port=self._port,
            password=self._password,
        )
        event.callback.register(self._on_record_state_changed)
        event.callback.register(self._on_obs_exit_started)

        with self._lock:
            self._req_client = req
            self._event_client = event
            self._connected = True

        if self.on_connection_changed:
            self.on_connection_changed(True)

    def _teardown(self) -> None:
        with self._lock:
            req = self._req_client
            ev = self._event_client
            self._req_client = None
            self._event_client = None
            was_connected = self._connected
            self._connected = False

        for client in (req, ev):
            if client is not None:
                try:
                    client.disconnect()
                except Exception:
                    pass

        if was_connected and self.on_connection_changed:
            self.on_connection_changed(False)

    # ------------------------------------------------------------------ #
    # Internal — OBS event callbacks (called from EventClient thread)     #
    # ------------------------------------------------------------------ #

    def _on_record_state_changed(self, data) -> None:
        active = getattr(data, "output_active", False)
        if self.on_state_changed:
            self.on_state_changed(active)

    def _on_obs_exit_started(self, data) -> None:
        """OBS is shutting down — tear down and schedule reconnect."""
        self._teardown()
        if not self._stop_event.is_set():
            # Restart connect loop after OBS exits
            self._connect_thread = threading.Thread(
                target=self._connect_loop, daemon=True, name="ObsAdapter-reconnect"
            )
            self._connect_thread.start()
