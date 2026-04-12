"""Keyboard fallback navigation and key-capture handlers."""

from services.key_listener_service import key_to_display


class KeyboardHandlersMixin:
    """Mixin for keyboard forward/backward fallback and key capture."""

    # ------------------------------------------------------------------ #
    # Fallback slide navigation (when Impress is not connected)            #
    # ------------------------------------------------------------------ #

    def _on_keyboard_forward(self) -> None:
        if not self._key_bindings_enabled:
            return
        if self._impress_bridge.is_client_connected:
            return
        self._key_provider.on_forward()
        self._recording_service.register_slide_change(self._key_provider.current_index)

    def _on_keyboard_backward(self) -> None:
        if not self._key_bindings_enabled:
            return
        if self._impress_bridge.is_client_connected:
            return
        self._key_provider.on_backward()
        self._recording_service.register_slide_change(self._key_provider.current_index)

    # ------------------------------------------------------------------ #
    # Key capture                                                          #
    # ------------------------------------------------------------------ #

    def _on_key_bindings_enabled_changed(self, value: bool) -> None:
        self._key_bindings_enabled = value
        self._settings.key_bindings_enabled = value

    def _start_capture_forward(self, ui_callback: callable) -> None:
        def _on_captured(key) -> None:
            self._key_listener.set_forward_key(key)
            self._settings.forward_key = key_to_display(key)
            self.after(0, ui_callback, key_to_display(key))

        self._key_listener.capture_next_key(_on_captured)

    def _start_capture_backward(self, ui_callback: callable) -> None:
        def _on_captured(key) -> None:
            self._key_listener.set_backward_key(key)
            self._settings.backward_key = key_to_display(key)
            self.after(0, ui_callback, key_to_display(key))

        self._key_listener.capture_next_key(_on_captured)
