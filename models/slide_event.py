from dataclasses import dataclass


@dataclass
class SlideEvent:
    time_s: float
    direction: str  # "forward" | "backward"
    slide_index: int
