"""
ImpressBridge — TCP server that receives slide events from the LibreOffice
Impress macro (slide_recorder_macro.py).

Wire protocol: JSON Lines (one JSON object per line, UTF-8, \\n terminated).
Message format: {"v": 1, "type": "<type>", ...fields}

Supported incoming message types:
  slide_changed      {"v":1,"type":"slide_changed","index":3,"total":12}
  slideshow_started  {"v":1,"type":"slideshow_started","total":12}
  slideshow_ended    {"v":1,"type":"slideshow_ended"}
  ping               {"v":1,"type":"ping"}  → replies with pong

Outgoing:
  pong               {"v":1,"type":"pong"}

Threading model:
  - The server socket runs in a daemon thread (_accept_thread).
  - Each client connection runs in its own daemon thread (_client_thread).
  - Callbacks (on_slide_changed, on_slideshow_started, on_slideshow_ended,
    on_client_connected, on_client_disconnected) are called from the client
    thread. App must marshal UI updates via app.after(0, ...).

Scalability note:
  BIND_HOST is currently "127.0.0.1" (localhost-only). To accept connections
  from other machines on the LAN, change it to "0.0.0.0". All other code
  remains unchanged — this is the only configuration knob needed.
"""

import json
import socket
import threading
from typing import Callable, Optional


BIND_HOST = "127.0.0.1"  # change to "0.0.0.0" for LAN access
PROTOCOL_VERSION = 1


class ImpressBridge:
    """
    TCP server that receives slide-event messages from the Impress macro.

    Accepts one client connection at a time. If a second client connects,
    the first is cleanly closed first.
    """

    def __init__(self, port: int) -> None:
        self._port = port
        self._server_socket: Optional[socket.socket] = None
        self._client_socket: Optional[socket.socket] = None
        self._client_lock = threading.Lock()
        self._running = False
        self._accept_thread: Optional[threading.Thread] = None

        # Callbacks — set by the App after construction
        self.on_slide_changed: Optional[Callable[[int, int], None]] = None
        self.on_slideshow_started: Optional[Callable[[int], None]] = None
        self.on_slideshow_ended: Optional[Callable[[], None]] = None
        self.on_client_connected: Optional[Callable[[], None]] = None
        self.on_client_disconnected: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @property
    def is_active(self) -> bool:
        """True when the server socket is open and accepting connections."""
        return self._running

    @property
    def is_client_connected(self) -> bool:
        with self._client_lock:
            return self._client_socket is not None

    def start(self) -> None:
        """Start the TCP server. Idempotent."""
        if self._running:
            return
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((BIND_HOST, self._port))
        self._server_socket.listen(1)
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="ImpressBridge-accept"
        )
        self._accept_thread.start()

    def stop(self) -> None:
        """Stop the server and close any open client connection. Idempotent."""
        self._running = False
        self._close_client()
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

    # ------------------------------------------------------------------ #
    # Internal — accept loop                                              #
    # ------------------------------------------------------------------ #

    def _accept_loop(self) -> None:
        while self._running:
            try:
                self._server_socket.settimeout(1.0)
                try:
                    conn, _ = self._server_socket.accept()
                except socket.timeout:
                    continue
            except OSError:
                break  # server socket closed

            self._close_client()  # drop any previous connection
            with self._client_lock:
                self._client_socket = conn

            if self.on_client_connected:
                self.on_client_connected()

            t = threading.Thread(
                target=self._client_thread,
                args=(conn,),
                daemon=True,
                name="ImpressBridge-client",
            )
            t.start()

    # ------------------------------------------------------------------ #
    # Internal — client thread                                            #
    # ------------------------------------------------------------------ #

    def _client_thread(self, conn: socket.socket) -> None:
        buffer = ""
        try:
            conn.settimeout(30.0)  # heartbeat timeout
            while self._running:
                try:
                    chunk = conn.recv(4096).decode("utf-8", errors="replace")
                except socket.timeout:
                    # Send a ping to check liveness; macro should pong back
                    try:
                        conn.sendall(
                            (
                                json.dumps({"v": PROTOCOL_VERSION, "type": "ping"})
                                + "\n"
                            ).encode()
                        )
                    except OSError:
                        break
                    continue
                except OSError:
                    break

                if not chunk:
                    break  # connection closed by remote

                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._dispatch(conn, line)
        finally:
            with self._client_lock:
                if self._client_socket is conn:
                    self._client_socket = None
            try:
                conn.close()
            except OSError:
                pass
            if self.on_client_disconnected:
                self.on_client_disconnected()

    def _dispatch(self, conn: socket.socket, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return  # ignore malformed messages

        msg_type = msg.get("type", "")

        if msg_type == "slide_changed":
            index = int(msg.get("index", 0))
            total = int(msg.get("total", 0))
            if self.on_slide_changed:
                self.on_slide_changed(index, total)

        elif msg_type == "slideshow_started":
            total = int(msg.get("total", 0))
            if self.on_slideshow_started:
                self.on_slideshow_started(total)

        elif msg_type == "slideshow_ended":
            if self.on_slideshow_ended:
                self.on_slideshow_ended()

        elif msg_type == "ping":
            try:
                conn.sendall(
                    (
                        json.dumps({"v": PROTOCOL_VERSION, "type": "pong"}) + "\n"
                    ).encode()
                )
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Internal — helpers                                                  #
    # ------------------------------------------------------------------ #

    def _close_client(self) -> None:
        with self._client_lock:
            if self._client_socket:
                try:
                    self._client_socket.close()
                except OSError:
                    pass
                self._client_socket = None
