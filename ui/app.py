import os

import customtkinter as ctk

from config.defaults import APP_GEOMETRY, APP_TITLE, DEFAULT_SAVE_DIR, DEFAULT_SESSION_TITLE
from config.settings import Settings
from services.impress_bridge import ImpressBridge
from services.key_listener_service import (
    KeyListenerService,
    key_from_name,
    key_to_display,
)
from services.obs_adapter import ObsAdapter
from services.recording_service import RecordingService
from services.slide_index.impress_provider import ImpressSlideIndexProvider
from services.slide_index.key_count_provider import KeyCountSlideIndexProvider
from services.storage_service import StorageService
from ui.handlers import AppHandlersMixin
from ui.components.collapsible_section import CollapsibleSection
from ui.components.connection_panel import ConnectionPanel
from ui.components.control_panel import ControlPanel
from ui.components.debug_panel import DebugPanel
from ui.components.key_config_panel import KeyConfigPanel
from ui.components.obs_settings_panel import ObsSettingsPanel
from ui.components.save_panel import SavePanel


class App(AppHandlersMixin, ctk.CTk):
    """
    Root window and orchestration hub.

    Layout and service wiring live here.
    All callback / handler logic is in AppHandlersMixin.
    """

    def __init__(self) -> None:
        super().__init__()
        self._settings = Settings()

        self.title(APP_TITLE)
        self.geometry(self._settings.window_geometry or APP_GEOMETRY)
        self.resizable(True, True)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._autosave_interval_s: int = self._settings.autosave_interval_s
        self._event_count: int = 0
        self._timer_job = None
        self._obs_recording: bool = False
        self._floating_record_panel = None

        self._initial_title = self._settings.last_session_title or DEFAULT_SESSION_TITLE
        self._initial_save_path = self._settings.last_save_path or os.path.join(
            DEFAULT_SAVE_DIR, f"{self._initial_title}.json"
        )

        self._init_services()
        self._build_ui()
        self._wire_callbacks()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    # Service initialisation                                               #
    # ------------------------------------------------------------------ #

    def _init_services(self) -> None:
        self._impress_provider = ImpressSlideIndexProvider()
        self._key_provider = KeyCountSlideIndexProvider()

        self._recording_service = RecordingService(self._impress_provider)
        self._storage_service = StorageService()
        self._storage_service.set_save_path(self._initial_save_path)

        self._key_listener = KeyListenerService(
            forward_key=key_from_name(self._settings.forward_key),
            backward_key=key_from_name(self._settings.backward_key),
            on_forward=self._on_keyboard_forward,
            on_backward=self._on_keyboard_backward,
        )
        self._key_listener.start()

        self._impress_bridge = ImpressBridge(port=self._settings.impress_bridge_port)
        self._impress_bridge.on_slide_changed = self._on_impress_slide_changed
        self._impress_bridge.on_slideshow_started = self._on_impress_slideshow_started
        self._impress_bridge.on_slideshow_ended = self._on_impress_slideshow_ended
        self._impress_bridge.on_client_connected = self._on_impress_connected
        self._impress_bridge.on_client_disconnected = self._on_impress_disconnected
        self._impress_bridge.start()

        self._obs_adapter = ObsAdapter(
            host=self._settings.obs_host,
            port=self._settings.obs_port,
            password=self._settings.obs_password,
        )
        self._obs_adapter.on_state_changed = self._on_obs_state_changed
        self._obs_adapter.on_connection_changed = self._on_obs_connection_changed
        self._obs_adapter.on_connection_attempt = self._on_obs_connection_attempt
        self._obs_adapter.connect()

    # ------------------------------------------------------------------ #
    # UI layout                                                            #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        sec_opts = {"fill": "x", "padx": 4, "pady": 4}

        # ── Recording ──────────────────────────────────────────────────
        sec_record = CollapsibleSection(scroll, "Recording", expanded=True)
        sec_record.pack(**sec_opts)

        rec_row = ctk.CTkFrame(sec_record.content_frame, fg_color="transparent")
        rec_row.pack(fill="x")
        rec_row.columnconfigure(0, weight=1)

        self._control_panel = ControlPanel(
            rec_row,
            on_record=self.trigger_start,
            on_stop=self.trigger_stop,
            on_overlay_topmost_changed=self._on_recording_overlay_topmost_changed,
            overlay_topmost=self._settings.recording_overlay_topmost,
            default_title=self._initial_title,
        )
        self._control_panel.grid(row=0, column=0, sticky="nsew")

        self._debug_panel = DebugPanel(rec_row)
        self._debug_panel.grid(row=0, column=1, sticky="ns", padx=(4, 0))

        # ── Connections ────────────────────────────────────────────────
        sec_conn = CollapsibleSection(scroll, "Connections", expanded=True)
        sec_conn.pack(**sec_opts)
        self._connection_panel = ConnectionPanel(
            sec_conn.content_frame,
            on_obs_auto_control_changed=self._on_obs_auto_control_changed,
            on_debug_changed=self._on_debug_changed,
            obs_auto_control=self._settings.obs_auto_control,
            debug=self._settings.debug,
        )
        self._connection_panel.pack(fill="x")

        # ── Save ───────────────────────────────────────────────────────
        sec_save = CollapsibleSection(scroll, "Save", expanded=True)
        sec_save.pack(**sec_opts)
        self._save_panel = SavePanel(
            sec_save.content_frame,
            on_path_changed=self._on_path_changed,
            on_manual_save=self._on_manual_save,
            on_autosave_interval_changed=self._on_autosave_interval_changed,
            default_interval=self._autosave_interval_s,
            default_path=self._initial_save_path,
        )
        self._save_panel.pack(fill="x")

        # ── OBS Settings ──────────────────────────────────────────────
        sec_obs = CollapsibleSection(scroll, "OBS Settings", expanded=False)
        sec_obs.pack(**sec_opts)
        self._obs_settings_panel = ObsSettingsPanel(
            sec_obs.content_frame,
            on_connect=self._on_obs_reconnect,
            obs_host=self._settings.obs_host,
            obs_port=self._settings.obs_port,
            obs_password=self._settings.obs_password,
        )
        self._obs_settings_panel.pack(fill="x")

        # ── Key Bindings ──────────────────────────────────────────────
        sec_keys = CollapsibleSection(scroll, "Key Bindings", expanded=False)
        sec_keys.pack(**sec_opts)
        self._key_bindings_enabled = self._settings.key_bindings_enabled
        self._key_config_panel = KeyConfigPanel(
            sec_keys.content_frame,
            on_capture_forward=self._start_capture_forward,
            on_capture_backward=self._start_capture_backward,
            on_enabled_changed=self._on_key_bindings_enabled_changed,
            forward_display=key_to_display(self._key_listener.forward_key),
            backward_display=key_to_display(self._key_listener.backward_key),
            enabled=self._key_bindings_enabled,
        )
        self._key_config_panel.pack(fill="x")

    # ------------------------------------------------------------------ #
    # Internal wiring                                                      #
    # ------------------------------------------------------------------ #

    def _wire_callbacks(self) -> None:
        self._recording_service.on_event = self._on_slide_event_from_thread
        self._recording_service.on_state_change = self._on_state_change_from_thread
