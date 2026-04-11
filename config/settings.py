"""
Settings — persistent user preferences stored in config.json next to the
executable (or next to main.py during development).

Wraps reading and writing a flat JSON file. Keys map 1:1 to config/defaults.py
constants. Unknown keys in the file are preserved (forward compatibility).

Usage:
    settings = Settings()          # loads from disk if file exists
    settings.obs_host              # read
    settings.obs_host = "192.x"   # write (auto-saves)
    settings.save()                # explicit save if needed
"""

import json
import os
from typing import Any

from config.defaults import (
    DEFAULT_AUTOSAVE_INTERVAL_S,
    DEFAULT_BACKWARD_KEY,
    DEFAULT_FORWARD_KEY,
    IMPRESS_AUTO_SYNC,
    IMPRESS_BRIDGE_PORT,
    OBS_AUTO_CONTROL,
    OBS_HOST,
    OBS_PASSWORD,
    OBS_PORT,
)

_CONFIG_FILENAME = "config.json"


def _config_path() -> str:
    """Resolve config.json path: same directory as this file's package root."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)  # project root (one level up from config/)
    return os.path.join(root, _CONFIG_FILENAME)


class Settings:
    def __init__(self) -> None:
        self._path = _config_path()
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass  # non-fatal — user will reconfigure next time

    def _get(self, key: str, default: Any) -> Any:
        return self._data.get(key, default)

    def _set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def forward_key(self) -> str:
        return self._get("forward_key", DEFAULT_FORWARD_KEY)

    @forward_key.setter
    def forward_key(self, v: str) -> None:
        self._set("forward_key", v)

    @property
    def backward_key(self) -> str:
        return self._get("backward_key", DEFAULT_BACKWARD_KEY)

    @backward_key.setter
    def backward_key(self, v: str) -> None:
        self._set("backward_key", v)

    @property
    def autosave_interval_s(self) -> int:
        return int(self._get("autosave_interval_s", DEFAULT_AUTOSAVE_INTERVAL_S))

    @autosave_interval_s.setter
    def autosave_interval_s(self, v: int) -> None:
        self._set("autosave_interval_s", v)

    @property
    def impress_bridge_port(self) -> int:
        return int(self._get("impress_bridge_port", IMPRESS_BRIDGE_PORT))

    @impress_bridge_port.setter
    def impress_bridge_port(self, v: int) -> None:
        self._set("impress_bridge_port", v)

    @property
    def impress_auto_sync(self) -> bool:
        return bool(self._get("impress_auto_sync", IMPRESS_AUTO_SYNC))

    @impress_auto_sync.setter
    def impress_auto_sync(self, v: bool) -> None:
        self._set("impress_auto_sync", v)

    @property
    def obs_host(self) -> str:
        return self._get("obs_host", OBS_HOST)

    @obs_host.setter
    def obs_host(self, v: str) -> None:
        self._set("obs_host", v)

    @property
    def obs_port(self) -> int:
        return int(self._get("obs_port", OBS_PORT))

    @obs_port.setter
    def obs_port(self, v: int) -> None:
        self._set("obs_port", v)

    @property
    def obs_password(self) -> str:
        return self._get("obs_password", OBS_PASSWORD)

    @obs_password.setter
    def obs_password(self, v: str) -> None:
        self._set("obs_password", v)

    @property
    def obs_auto_control(self) -> bool:
        return bool(self._get("obs_auto_control", OBS_AUTO_CONTROL))

    @obs_auto_control.setter
    def obs_auto_control(self, v: bool) -> None:
        self._set("obs_auto_control", v)

    @property
    def last_save_path(self) -> str:
        return self._get("last_save_path", "")

    @last_save_path.setter
    def last_save_path(self, v: str) -> None:
        self._set("last_save_path", v)

    @property
    def last_session_title(self) -> str:
        return self._get("last_session_title", "")

    @last_session_title.setter
    def last_session_title(self, v: str) -> None:
        self._set("last_session_title", v)
