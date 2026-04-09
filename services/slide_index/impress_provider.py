"""
ImpressSlideIndexProvider — SlideIndexProvider backed by real slide data
received from the LibreOffice Impress macro via ImpressBridge.

The absolute index is set externally by calling notify_slide(index).
on_forward() and on_backward() are no-ops: when Impress is connected the
real slide number always comes from the macro, not from key-press counting.

Thread safety: notify_slide() may be called from the ImpressBridge client
thread. The index is stored in a threading.Lock-protected variable.
"""

import threading

from services.slide_index.base import SlideIndexProvider


class ImpressSlideIndexProvider:
    """
    SlideIndexProvider whose index is driven by ImpressBridge messages.

    Implements SlideIndexProvider protocol (compatible with RecordingService).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index: int = 1
        self._total: int = 0

    # ------------------------------------------------------------------ #
    # SlideIndexProvider protocol                                          #
    # ------------------------------------------------------------------ #

    @property
    def current_index(self) -> int:
        with self._lock:
            return self._index

    def on_forward(self) -> None:
        """No-op: index is set externally by Impress."""

    def on_backward(self) -> None:
        """No-op: index is set externally by Impress."""

    def reset(self) -> None:
        with self._lock:
            self._index = 1
            self._total = 0

    # ------------------------------------------------------------------ #
    # ImpressBridge integration                                            #
    # ------------------------------------------------------------------ #

    @property
    def total_slides(self) -> int:
        with self._lock:
            return self._total

    def notify_slide(self, index: int, total: int = 0) -> None:
        """Called by ImpressBridge when a slide_changed message arrives."""
        with self._lock:
            self._index = index
            if total:
                self._total = total
