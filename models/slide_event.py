from dataclasses import dataclass


@dataclass
class SlideEvent:
    time_s: float
    slide_index: int
    event_type: str = "slide_changed"
