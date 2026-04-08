from dataclasses import dataclass, field
from typing import List

from models.slide_event import SlideEvent


@dataclass
class Session:
    start_iso: str
    events: List[SlideEvent] = field(default_factory=list)
    duration_s: float = 0.0
