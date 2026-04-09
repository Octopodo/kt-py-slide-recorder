"""
slide_recorder_macro.py
LibreOffice Impress macro — Slide Recorder Bridge

Connects to the kt-py-slide-recorder app over TCP and sends slide events
using the Impress Bridge Protocol v1 (JSON Lines).

INSTALLATION (one-time, manual):

  1. Copy THIS FILE (slide_recorder_macro.py) to the LibreOffice Python scripts folder:
       Windows : %APPDATA%/LibreOffice/4/user/Scripts/python/
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
import sys
import threading
from datetime import datetime

import uno
import unohelper
from com.sun.star.document import XDocumentEventListener

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 2765
PROTOCOL_VERSION = 1

_LOG_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "slide_recorder_debug.log")

# ── Persistent module-level state ──────────────────────────────────────

if not hasattr(sys, "_sliderecorder_globals"):
    sys._sliderecorder_globals = {
        "connection": None,
        "poll_thread": None,
        "poll_stop": threading.Event(),
        "poll_lock": threading.Lock(),
        "global_listener": None,
    }

sg = sys._sliderecorder_globals


# ── Logging ────────────────────────────────────────────────────────────


def _log(msg):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  {msg}\n")
    except Exception:
        pass


# ── TCP connection ─────────────────────────────────────────────────────


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
                    return False
            try:
                self._sock.sendall(line.encode("utf-8"))
                return True
            except OSError:
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
    if sg["connection"] is None:
        sg["connection"] = _BridgeConnection(BRIDGE_HOST, BRIDGE_PORT)
    return sg["connection"]


def _send(msg) -> bool:
    return _get_connection().send(msg)


# ── Poll thread ───────────────────────────────────────────────────────


def _is_polling() -> bool:
    with sg["poll_lock"]:
        return sg["poll_thread"] is not None and sg["poll_thread"].is_alive()


def _start_poll(ctrl, doc) -> None:
    with sg["poll_lock"]:
        sg["poll_stop"].set()
        sg["poll_stop"] = threading.Event()
        stop = sg["poll_stop"]
        sg["poll_thread"] = threading.Thread(
            target=_poll_slides, args=(ctrl, doc, stop), daemon=True
        )
        sg["poll_thread"].start()
    _log("_start_poll: thread started")


def _stop_poll(reason: str = "") -> None:
    with sg["poll_lock"]:
        if sg["poll_thread"] is None or not sg["poll_thread"].is_alive():
            return
        _log(f"_stop_poll: {reason}")
        sg["poll_stop"].set()


def _poll_slides(ctrl, doc, stop_evt):
    last_idx = None
    was_disconnected = False
    errors = 0
    try:
        total = doc.DrawPages.Count
    except Exception:
        total = 0
    _send({"v": PROTOCOL_VERSION, "type": "slideshow_started", "total": total})
    _log(f"_poll_slides: started, total={total}")

    while not stop_evt.is_set():
        try:
            idx = ctrl.getCurrentSlideIndex()
            errors = 0
        except Exception as exc:
            errors += 1
            if errors >= 3:
                _log(f"_poll_slides: controller dead ({exc}) — stopping")
                break
            stop_evt.wait(0.25)
            continue

        if was_disconnected:
            try:
                total = doc.DrawPages.Count
            except Exception:
                pass
            ok = _send(
                {"v": PROTOCOL_VERSION, "type": "slideshow_started", "total": total}
            )
            if ok:
                was_disconnected = False
                last_idx = idx
        elif last_idx is None or idx != last_idx:
            try:
                total = doc.DrawPages.Count
            except Exception:
                pass
            ok = _send(
                {
                    "v": PROTOCOL_VERSION,
                    "type": "slide_changed",
                    "index": idx + 1,
                    "total": total,
                }
            )
            if ok:
                last_idx = idx
                _log(f"_poll_slides: slide {idx + 1}/{total}")
            else:
                was_disconnected = True

        stop_evt.wait(0.25)

    _send({"v": PROTOCOL_VERSION, "type": "slideshow_ended"})
    _get_connection().close()
    _log("_poll_slides: ended")


# ── Presentation detection ─────────────────────────────────────────────
#
# IMPORTANT: All UNO API calls MUST happen from the main LibreOffice thread
# (the event handler thread). UNO services are NOT accessible from Python
# threading.Thread or threading.Timer threads.
#
# Strategy:
#   1. On every document event, try to find a running presentation
#      controller using Desktop (main thread, UNO-safe).
#   2. If found and not already polling, start the poll thread.
#      (The poll thread only uses ctrl.getCurrentSlideIndex() on an
#      already-obtained proxy, which does work cross-thread.)
#   3. If not found, do nothing — wait for the next event.
#      LibreOffice fires multiple events during presentation startup,
#      so we'll get another chance.


def _get_desktop():
    """Get the Desktop service. MUST be called from main thread."""
    try:
        ctx = uno.getComponentContext()
        sm = ctx.ServiceManager
        return sm.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    except Exception:
        return None


def _find_presentation_controller(event_doc):
    """Try to find a running presentation controller.

    Checks multiple sources: event document, Desktop's current component,
    and all open components. MUST be called from main thread.

    Returns (doc, ctrl) or (None, None).
    """
    candidates = []

    # Source 1: The event document itself
    if event_doc is not None:
        candidates.append(("event_doc", event_doc))

    # Source 2: Desktop.getCurrentComponent()
    desktop = _get_desktop()
    if desktop is not None:
        try:
            current = desktop.getCurrentComponent()
            if current is not None:
                candidates.append(("desktop_current", current))
        except Exception as exc:
            _log(f"  getCurrentComponent failed: {exc}")

        # Source 3: Enumerate all open components
        try:
            components = desktop.getComponents()
            if components is not None:
                enum = components.createEnumeration()
                while enum.hasMoreElements():
                    comp = enum.nextElement()
                    if comp is not None:
                        candidates.append(("enumerated", comp))
        except Exception as exc:
            _log(f"  getComponents/enumerate failed: {exc}")

    # Try each candidate
    for source_name, comp in candidates:
        # Check if it's an Impress document
        try:
            if not hasattr(comp, "Presentation"):
                continue
        except Exception:
            continue

        # Try getController() directly (most reliable)
        try:
            pres = comp.Presentation
            ctrl = pres.getController()
            if ctrl is not None:
                _log(
                    f"  FOUND controller via {source_name}.Presentation.getController()"
                )
                return comp, ctrl
        except Exception as exc:
            _log(f"  {source_name}.getController() failed: {exc}")

        # Fallback: check isRunning
        try:
            pres = comp.Presentation
            running = pres.isRunning()
            _log(f"  {source_name}.isRunning() = {running}")
            if running:
                ctrl = pres.getController()
                if ctrl is not None:
                    _log(f"  FOUND controller via {source_name} isRunning path")
                    return comp, ctrl
                _log(f"  {source_name}: isRunning=True but getController()=None")
        except Exception as exc:
            _log(f"  {source_name}.isRunning() failed: {exc}")

    return None, None


# ── Event listener ─────────────────────────────────────────────────────


class GlobalDocumentEventListener(unohelper.Base, XDocumentEventListener):
    """Listens for ALL document events and attempts to detect presentation
    start/stop on every relevant event.

    Key insight: we don't rely on specific event names like OnStartPresentation
    (which may not fire in all LibreOffice versions). Instead, on EVERY event
    from a presentation document, we check if a controller is available.
    """

    # Events that could indicate presentation state changes
    _RELEVANT_EVENTS = frozenset(
        {
            "OnModeChanged",
            "OnStartPresentation",
            "OnPresentationBegin",
            "OnEndPresentation",
            "OnPresentationEnd",
            "OnFocus",
            "OnViewCreated",
        }
    )

    def documentEventOccured(self, event):
        try:
            name = event.EventName
            doc = event.Source

            # Quick filter: skip clearly irrelevant events
            if name not in self._RELEVANT_EVENTS:
                return

            # Filter: only Impress documents (tolerate None/broken Source)
            try:
                if doc is not None and hasattr(doc, "supportsService"):
                    if not doc.supportsService(
                        "com.sun.star.presentation.PresentationDocument"
                    ):
                        return
            except Exception:
                # doc.Source is None or broken — still try, we'll use Desktop
                pass

            _log(f"event: {name}  polling={_is_polling()}")

            if _is_polling():
                # Already tracking a presentation — check if it ended
                self._check_detach(name, doc)
            else:
                # Not tracking — check if a presentation started
                self._check_attach(name, doc)

        except Exception as exc:
            _log(f"documentEventOccured EXCEPTION: {exc}")

    def _check_attach(self, name, doc):
        """Try to find and connect to a running presentation."""
        found_doc, ctrl = _find_presentation_controller(doc)
        if ctrl is not None:
            _log(f"  → starting poll from {name}")
            _start_poll(ctrl, found_doc)
        else:
            _log(f"  → no controller found yet")

    def _check_detach(self, name, doc):
        """Check if the presentation we're tracking has ended."""
        # Only check on events that could indicate ending
        if name not in (
            "OnModeChanged",
            "OnEndPresentation",
            "OnPresentationEnd",
            "OnFocus",
            "OnViewCreated",
        ):
            return
        # The poll thread will self-terminate when the controller dies
        # (getCurrentSlideIndex throws 3 times). But we also check here
        # for faster detection.
        found_doc, ctrl = _find_presentation_controller(doc)
        if ctrl is None and _is_polling():
            _log(f"  → controller gone, stopping poll from {name}")
            _stop_poll(f"controller gone ({name})")

    def disposing(self, source):
        pass


# ── Public entry points ────────────────────────────────────────────────


def RegisterSlideRecorderListeners(*args):
    _log("RegisterSlideRecorderListeners called")
    ctx = uno.getComponentContext()
    sm = ctx.ServiceManager
    broadcaster = sm.createInstanceWithContext(
        "com.sun.star.frame.GlobalEventBroadcaster", ctx
    )
    if sg["global_listener"] is not None:
        try:
            broadcaster.removeDocumentEventListener(sg["global_listener"])
            _log("Removed old listener")
        except Exception as exc:
            _log(f"Could not remove old listener: {exc}")
    _stop_poll("re-registration")
    listener = GlobalDocumentEventListener()
    broadcaster.addDocumentEventListener(listener)
    sg["global_listener"] = listener
    _log("Registered GlobalDocumentEventListener")


def TestConnection(*args):
    try:
        sock = socket.create_connection(("127.0.0.1", BRIDGE_PORT), timeout=2)
        sock.close()
        raise RuntimeError(f"EXITO: Puerto {BRIDGE_PORT} accesible.")
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
        text = "(log file not found)"
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
            0,
            1,
            "slide_recorder_debug.log",
            text or "(log is empty)",
        )
        msgbox.execute()


g_exportedScripts = (RegisterSlideRecorderListeners, TestConnection, ShowLog)
