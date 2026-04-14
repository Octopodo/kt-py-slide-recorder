"""LibreOffice Impress bridge callback handlers."""

import logging

log = logging.getLogger(__name__)


class ImpressHandlersMixin:
    """Mixin for Impress TCP bridge events (slide changes, connect/disconnect)."""

    def _on_impress_slide_changed(
        self, index: int, total: int, event_type: str = "slide_changed"
    ) -> None:
        self._impress_provider.notify_slide(index, total)
        self._recording_service.register_slide_change(index, event_type)

    def _on_impress_slideshow_started(self, total: int) -> None:
        self._impress_provider.reset()
        self._recording_service.register_slide_change(0, "slideshow_started")
        self.after(0, self._handle_slideshow_started)

    def _on_impress_slideshow_ended(self) -> None:
        self._recording_service.register_slide_change(
            self._impress_provider.current_index, "slideshow_ended"
        )
        self.after(0, self._handle_slideshow_ended)

    def _on_impress_connected(self) -> None:
        self.after(0, self._handle_impress_connected)

    def _on_impress_disconnected(self) -> None:
        self.after(0, self._handle_impress_disconnected)

    # ------------------------------------------------------------------ #
    # Main-thread UI updates                                               #
    # ------------------------------------------------------------------ #

    def _handle_slideshow_started(self) -> None:
        log.info("Impress: slideshow started")
        self._impress_connected = True
        self._impress_in_presentation = True
        self._connection_panel.update_impress_status(True, True)
        self._update_floating_impress_status()

    def _handle_slideshow_ended(self) -> None:
        log.info("Impress: slideshow ended")
        self._impress_connected = True
        self._impress_in_presentation = False
        self._connection_panel.update_impress_status(True, False)
        self._update_floating_impress_status()

    def _handle_impress_connected(self) -> None:
        log.info("Impress: macro connected")
        self._impress_connected = True
        self._impress_in_presentation = False
        self._connection_panel.update_impress_status(True, False)
        self._update_floating_impress_status()

    def _handle_impress_disconnected(self) -> None:
        log.info("Impress: macro disconnected")
        self._impress_connected = False
        self._impress_in_presentation = False
        self._connection_panel.update_impress_status(False, False)
        self._update_floating_impress_status()

    def _update_floating_impress_status(self) -> None:
        panel = self._floating_record_panel
        if panel is not None and panel.winfo_exists():
            panel.update_impress_status(self._impress_connected, self._impress_in_presentation)
