from services.slide_index.base import SlideIndexProvider


class KeyCountSlideIndexProvider:
    """
    Slide index provider based on key-press counting.

    Starts at slide 1 and increments/decrements by 1 on each navigation event.
    The minimum index is 1 (cannot go below slide 1).

    Replace this with a COM/API-backed provider when real slide numbers
    are available from the presentation software.
    """

    def __init__(self, start_index: int = 1) -> None:
        self._index: int = start_index

    @property
    def current_index(self) -> int:
        return self._index

    def on_forward(self) -> None:
        self._index += 1

    def on_backward(self) -> None:
        self._index = max(1, self._index - 1)

    def reset(self) -> None:
        self._index = 1
