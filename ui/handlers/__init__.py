"""Aggregated handler mixin for the App class.

Each domain lives in its own module; this package re-exports them as a
single ``AppHandlersMixin`` so that ``App`` can inherit from one class.
"""

from .impress import ImpressHandlersMixin
from .keyboard import KeyboardHandlersMixin
from .obs import ObsHandlersMixin
from .recording import RecordingHandlersMixin
from .save import SaveHandlersMixin


class AppHandlersMixin(
    RecordingHandlersMixin,
    ImpressHandlersMixin,
    ObsHandlersMixin,
    KeyboardHandlersMixin,
    SaveHandlersMixin,
):
    """Combined mixin aggregating all handler domains."""
