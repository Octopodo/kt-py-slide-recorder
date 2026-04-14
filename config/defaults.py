import os

APP_TITLE: str = "Slide Recorder"
APP_GEOMETRY: str = "480x680"

_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SAVE_DIR: str = os.path.join(_PROJECT_ROOT, "tests", "results")
DEFAULT_SESSION_TITLE: str = "recording"

DEFAULT_FORWARD_KEY: str = "right"
DEFAULT_BACKWARD_KEY: str = "left"
DEFAULT_AUTOSAVE_INTERVAL_S: int = 60

# ImpressBridge — TCP server (localhost only by default)
IMPRESS_BRIDGE_PORT: int = 2765

# OBS WebSocket v5
OBS_HOST: str = "localhost"
OBS_PORT: int = 4455
OBS_PASSWORD: str = ""

# Feature flags (opt-in, persisted via settings.py)
OBS_AUTO_CONTROL: bool = False  # start/stop OBS when session starts/stops
IMPRESS_AUTO_SYNC: bool = False  # auto start/stop session on slideshow F5/Esc
RECORDING_OVERLAY_TOPMOST: bool = True
RECORDING_OVERLAY_GEOMETRY: str = ""
