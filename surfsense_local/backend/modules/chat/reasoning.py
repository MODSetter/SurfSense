"""A thinking model's trace for one turn: what it said, and how long it thought."""

import time
from collections.abc import Callable


class ReasoningTrace:
    """Timed from the trace's first piece to the answer's first piece.

    Stored for the UI only. History sends the model its answers, never its
    traces, so a long think does not eat the next turn's window.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._pieces: list[str] = []
        self._started: float | None = None
        self._duration_ms: int | None = None

    def add(self, text: str) -> None:
        if self._started is None:
            self._started = self._clock()
        self._pieces.append(text)

    def end(self) -> int | None:
        """The duration the first time a trace ends, and None ever after or
        when the model never thought."""
        if self._started is None or self._duration_ms is not None:
            return None
        self._duration_ms = round((self._clock() - self._started) * 1000)
        return self._duration_ms

    def stored(self) -> dict | None:
        if self._started is None:
            return None
        self.end()
        return {"text": "".join(self._pieces), "duration_ms": self._duration_ms}
