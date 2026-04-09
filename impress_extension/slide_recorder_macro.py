"""
slide_recorder_macro.py
LibreOffice Impress macro — Slide Recorder Bridge

Connects to the kt-py-slide-recorder app over TCP and sends slide events
using the Impress Bridge Protocol v1 (JSON Lines).

INSTALLATION (one-time, manual):

  1. Copy THIS FILE (slide_recorder_macro.py) to the LibreOffice Python scripts folder:
       Windows : %APPDATA%\LibreOffice\4\user\Scripts\python\
       macOS   : ~/Library/Application Support/LibreOffice/4/user/Scripts/python/
       Linux   : ~/.config/libreoffice/4/user/Scripts/python/

  2. In LibreOffice: Tools → Options → LibreOffice → Security
     → Macro Security → set to Medium → OK → restart LibreOffice.

  3. In LibreOffice Impress with a presentation open:
       Tools → Macros → Organize Python Macros...
     Select slide_recorder_macro → RegisterSlideRecorderListeners → Run

  4. (Optional) Auto-run on every session:
       Tools → Customize → Events tab
       Event: "Start Application"
       Macro... → My Macros → slide_recorder_macro → RegisterSlideRecorderListeners
       OK

  NOTE: Python macros are NOT pasted into the Basic IDE.
        The Basic IDE only accepts LibreOffice Basic (a different language).
        Use "Tools → Macros → Organize Python Macros" instead.

PROTOCOL:
  Host : localhost (127.0.0.1)
  Port : 2765  (must match BRIDGE_PORT in kt-py-slide-recorder config)
  Format: one JSON object per line, UTF-8, LF-terminated.

DEBUG:
  Run ShowLog from the macro browser to display the last 40 log lines.
  Log file: ~/Desktop/slide_recorder_debug.log
"""

import json
import os
import socket
import threading
import time
from datetime import datetime

import uno
import unohelper
from com.sun.star.document import XDocumentEventListener

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 2765
PROTOCOL_VERSION = 1

_LOG_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "slide_recorder_debug.log")
_connection = None

# ── Poll singleton ────────────────────────────────────────────────────
# There is at most ONE active poll thread at any time.
# stop_evt is signalled to terminate the current thread cleanly.
_poll_thread = None
_poll_stop = threading.Event()
_poll_lock = threading.Lock()

# ── _on_start chain control ───────────────────────────────────────────
# Each time we want to (re)attach, the sequence number is incremented.
# Any running _on_start chain that sees a stale seq aborts itself.
_on_start_seq = 0
_on_start_seq_lock = threading.Lock()

# ── Listener singleton ────────────────────────────────────────────────
_global_listener = None


def _log(msg):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  {msg}\n")
    except Exception:
        pass


class _BridgeConnection:
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._sock = None
        self._lock = threading.Lock()

    def send(self, msg):
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        with self._lock:
            if self._sock is None:
                if not self._connect():
                    _log(f"send: connect failed for msg type={msg.get('type')}")
                    return False
            try:
                self._sock.sendall(line.encode("utf-8"))
                _log(f"send OK: {msg.get('type')}")
                return True
            except OSError as e:
                _log(f"send OSError: {e}")
                self._close()
                return False

    def _connect(self):
        try:
            s = socket.create_connection((self._host, self._port), timeout=2)
            s.settimeout(None)
            self._sock = s
            _log(f"TCP connected to {self._host}:{self._port}")
            return True
        except OSError as e:
            _log(f"TCP connect failed: {e}")
            return False

    def _close(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def close(self):
        with self._lock:
            self._close()


def _get_connection():
    global _connection
    if _connection is None:
        _connection = _BridgeConnection(BRIDGE_HOST, BRIDGE_PORT)
    return _connection


def _send(msg) -> bool:
    return _get_connection().send(msg)


# ── Poll thread management ────────────────────────────────────────────

def _is_polling() -> bool:
    with _poll_lock:
        return _poll_thread is not None and _poll_thread.is_alive()


def _start_poll(ctrl, doc) -> None:
    global _poll_thread, _poll_stop
    with _poll_lock:
        _poll_stop.set()                          # stop any prior thread
        _poll_stop = threading.Event()
        stop = _poll_stop
        _poll_thread = threading.Thread(
            target=_poll_slides, args=(ctrl, doc, stop), daemon=True
        )
        _poll_thread.start()
    _log("_start_poll: new thread started")


def _stop_poll(reason: str = "") -> None:
    with _poll_lock:
        if _poll_thread is None or not _poll_thread.is_alive():
            return
        _log(f"_stop_poll: {reason}")
        _poll_stop.set()


def _poll_slides(ctrl, doc, stop_evt: threading.Event) -> None:
    """Poll getCurrentSlideIndex every 250 ms; send slide_changed on every change.
    Re-sends slideshow_started if TCP reconnects mid-presentation.
    Sends slideshow_ended when the thread exits (presentation over or stopped).
    """
    last_idx = None
    was_disconnected = False
    _log("_poll_slides: started")
    try:
        total = doc.DrawPages.Count
    except Exception:
        total = 0
    _send({"v": PROTOCOL_VERSION, "type": "slideshow_started", "total": total})

    while not stop_evt.is_set():
        try:
            idx = ctrl.getCurrentSlideIndex()
        except Exception as exc:
            _log(f"_poll_slides: controller error: {exc} — stopping")
            break

        if was_disconnected:
            try:
                total = doc.DrawPages.Count
            except Exception:
                total = 0
            ok = _send({"v": PROTOCOL_VERSION, "type": "slideshow_started", "total": total})
            if ok:
                was_disconnected = False
                last_idx = idx
                _log("_poll_slides: reconnected, re-sent slideshow_started")
        else:
            if last_idx is None:
                last_idx = idx
                _log(f"_poll_slides: initial slide {idx + 1}")
            elif idx != last_idx:
                try:
                    total = doc.DrawPages.Count
                except Exception:
                    total = 0
                ok = _send({
                    "v": PROTOCOL_VERSION,
                    "type": "slide_changed",
                    "index": idx + 1,
                    "total": total,
                })
                if ok:
                    last_idx = idx
                    _log(f"_poll_slides: slide → {idx + 1}/{total}")
                else:
                    was_disconnected = True

        stop_evt.wait(0.25)   # sleep 250 ms, wakes immediately if event is set

    _send({"v": PROTOCOL_VERSION, "type": "slideshow_ended"})
    _log("_poll_slides: stopped, sent slideshow_ended")


# ── Attach / detach helpers ───────────────────────────────────────────

def _try_attach(doc) -> None:
    """Called on presentation-mode events — start polling if not already."""
    global _on_start_seq
    if _is_polling():
        return
    with _on_start_seq_lock:
        _on_start_seq += 1
        seq = _on_start_seq
    _log(f"_try_attach: launching _on_start chain #{seq}")
    threading.Thread(target=_on_start, args=(doc, 0, seq), daemon=True).start()


def _try_detach(doc) -> None:
    """Called on presentation-mode events — stop polling if presentation ended."""
    if not _is_polling():
        return
    try:
        running = doc.Presentation.isRunning()
    except Exception:
        running = False
    if not running:
        _stop_poll("OnModeChanged: presentation no longer running")


def _on_start(doc, retries: int = 0, seq: int = 0) -> None:
    """Retry loop: wait for pres.isRunning(), then start the poll thread."""
    # Abort if a newer chain superseded us
    with _on_start_seq_lock:
        if seq != _on_start_seq:
            return
    # Already polling? Nothing to do
    if _is_polling():
        return
    try:
        running = doc.Presentation.isRunning()
    except Exception as exc:
        _log(f"_on_start #{seq}: pres error: {exc}")
        return
    if not running:
        if retries < 30:
            threading.Timer(0.5, _on_start, args=(doc, retries + 1, seq)).start()
        else:
            _log(f"_on_start #{seq}: gave up waiting")
        return
    try:
        ctrl = doc.Presentation.getController()
    except Exception as exc:
        _log(f"_on_start #{seq}: getController error: {exc}")
        return
    if ctrl is None:
        if retries < 30:
            threading.Timer(0.5, _on_start, args=(doc, retries + 1, seq)).start()
        else:
            _log(f"_on_start #{seq}: gave up (no controller)")
        return
    _log(f"_on_start #{seq}: OK on retry {retries}")
    _start_poll(ctrl, doc)


# ── Broadcaster listener ──────────────────────────────────────────────

class GlobalDocumentEventListener(unohelper.Base, XDocumentEventListener):
    def documentEventOccured(self, event):
        try:
            name = event.EventName
            doc = event.Source
            # Filter to presentation documents only (dialogs also send OnModeChanged)
            try:
                if not doc.supportsService(
                    "com.sun.star.presentation.PresentationDocument"
                ):
                    return
            except Exception:
                return
            _log(f"event: {name}")
            if name in ("OnStartPresentation", "OnModeChanged"):
                _try_attach(doc)
                _try_detach(doc)
        except Exception as exc:
            _log(f"documentEventOccured EXCEPTION: {exc}")

    def disposing(self, source):
        pass


def RegisterSlideRecorderListeners(*args):
    global _global_listener
    _log("RegisterSlideRecorderListeners called")
    ctx = uno.getComponentContext()
    sm = ctx.ServiceManager
    broadcaster = sm.createInstanceWithContext(
        "com.sun.star.frame.GlobalEventBroadcaster", ctx
    )
    # Singleton: remove previous listener (if module wasn't reloaded)
    if _global_listener is not None:
        try:
            broadcaster.removeDocumentEventListener(_global_listener)
            _log("Removed old listener")
        except Exception as exc:
            _log(f"Could not remove old listener: {exc}")
    # Also stop any active poll so state is fully clean
    _stop_poll("re-registration")
    listener = GlobalDocumentEventListener()
    broadcaster.addDocumentEventListener(listener)
    _global_listener = listener
    _log("Registered singleton GlobalDocumentEventListener")


def TestConnection(*args):
    try:
        sock = socket.create_connection(("127.0.0.1", 2765), timeout=2)
        sock.close()
        raise RuntimeError("EXITO: Puerto 2765 accesible.")
    except RuntimeError:
        raise
    except ConnectionRefusedError:
        raise RuntimeError(
            "FALLO: Conexion rechazada. Abre kt-py-slide-recorder primero."
        )
    except OSError as e:
        raise RuntimeError(f"FALLO: {type(e).__name__}: {e}")


def ShowLog(*args):
    """Display the last 40 lines of the debug log in a message box."""
    try:
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        text = "".join(lines[-40:])
    except FileNotFoundError:
        text = "(log file not found — run RegisterSlideRecorderListeners first)"
    except Exception as e:
        text = f"Error reading log: {e}"
    ctx = uno.getComponentContext()
    sm = ctx.ServiceManager
    desktop = sm.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    frame = desktop.getCurrentFrame() if desktop else None
    if frame:
        toolkit = sm.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        msgbox = toolkit.createMessageBox(
            frame.getContainerWindow(),
            0,  # MESSAGEBOX
            1,  # OK button
            "slide_recorder_debug.log",
            text or "(log is empty)",
        )
        msgbox.execute()


# Only expose public entry points in the LibreOffice macro browser.
# Internal helpers (_log, _send, _get_connection, etc.) are NOT listed here
# and will not appear as runnable macros.
g_exportedScripts = (RegisterSlideRecorderListeners, TestConnection, ShowLog)
