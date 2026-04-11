from dataclasses import dataclass


@dataclass
class SlideEvent:
    time_hms: str
    time_ms: int
    slide_index: int
    event_type: str = "slide_changed"
