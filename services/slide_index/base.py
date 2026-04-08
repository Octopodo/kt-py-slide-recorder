from typing import Protocol, runtime_checkable


@runtime_checkable
class SlideIndexProvider(Protocol):
    """
    Abstraction for resolving the current slide index.

    Current implementation: simple key-press counter (KeyCountSlideIndexProvider).
    Future implementation: query the PowerPoint COM/API for the real slide number,
    allowing the index to reflect mouse-driven jumps or other navigation methods.

    Swap the implementation at composition root (ui/app.py) without touching
    RecordingService or any other consumer.
    """

    @property
    def current_index(self) -> int: ...

    def on_forward(self) -> None: ...

    def on_backward(self) -> None: ...

    def reset(self) -> None: ...
