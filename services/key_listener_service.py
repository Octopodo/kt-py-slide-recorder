import threading
from typing import Callable, Optional

from pynput import keyboard
from pynput.keyboard import Key, KeyCode


def key_to_display(key) -> str:
    """Convert a pynput key object to a human-readable string."""
    if isinstance(key, Key):
        return key.name
    if isinstance(key, KeyCode) and key.char:
        return key.char
    return str(key)


def key_from_name(name: str):
    """
    Convert a key name string (e.g. "right", "left", "a") to a pynput key object.
    Tries the Key enum first (special keys), falls back to KeyCode for regular chars.
    """
    try:
        return Key[name]
    except KeyError:
        return KeyCode.from_char(name)


class KeyListenerService:
    """
    Global keyboard listener using pynput. Works even when another application
    (e.g. PowerPoint) has focus.

    Supports:
    - Configurable forward and backward key bindings.
    - One-shot capture mode: capture_next_key() intercepts the next key press
      and routes it to a callback instead of the slide-event handlers.
      Used by the UI to let users re-bind keys while the app is not recording.
    """

    def __init__(
        self,
        forward_key,
        backward_key,
        on_forward: Callable[[], None],
        on_backward: Callable[[], None],
    ) -> None:
        self._forward_key = forward_key
        self._backward_key = backward_key
        self._on_forward = on_forward
        self._on_backward = on_backward

        self._capture_callback: Optional[Callable[[object], None]] = None
        self._capture_lock = threading.Lock()
        self._listener: Optional[keyboard.Listener] = None

    @property
    def is_active(self) -> bool:
        return self._listener is not None and self._listener.is_alive()

    def start(self) -> None:
        """Start the global listener. Idempotent."""
        if self._listener and self._listener.is_alive():
            return
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        """Stop the global listener."""
        if self._listener:
            self._listener.stop()
            self._listener = None

    @property
    def forward_key(self):
        return self._forward_key

    @property
    def backward_key(self):
        return self._backward_key

    def set_forward_key(self, key) -> None:
        self._forward_key = key

    def set_backward_key(self, key) -> None:
        self._backward_key = key

    def capture_next_key(self, callback: Callable[[object], None]) -> None:
        """
        Enter one-shot capture mode. The very next key press will be passed
        to *callback* and will NOT be processed as a slide event.
        Called from the UI thread; callback is invoked from the pynput thread.
        """
        with self._capture_lock:
            self._capture_callback = callback

    def cancel_capture(self) -> None:
        """Cancel a pending capture without consuming a key press."""
        with self._capture_lock:
            self._capture_callback = None

    def _on_press(self, key) -> None:
        with self._capture_lock:
            if self._capture_callback is not None:
                cb = self._capture_callback
                self._capture_callback = None
                cb(key)
                return

        if key == self._forward_key:
            self._on_forward()
        elif key == self._backward_key:
            self._on_backward()
