"""The one dictation that may be open, which keeps file windows off the server
so the speaker's phrases never queue behind a recording."""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["DictationEndedError", "DictationSessions"]

# The composer sends a keepalive every 10 s while recording.
_QUIET_SECONDS = 20.0
# Recording stops at 5 minutes; the last phrases still land after it.
_LONGEST_SECONDS = 6 * 60.0


class DictationEndedError(Exception):
    """Not the open dictation: ended, replaced, or never opened here."""


@dataclass
class _Dictation:
    id: str
    opened_at: float
    seen_at: float


class DictationSessions:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._open: _Dictation | None = None

    def open(self) -> str:
        """A new dictation; any other ends, though its phrases in flight answer."""
        now = self._clock()
        self._open = _Dictation(uuid.uuid4().hex, now, now)
        return self._open.id

    def touch(self, dictation_id: str) -> None:
        """A phrase or keepalive arrived for it."""
        current = self._current()
        if current is None or current.id != dictation_id:
            raise DictationEndedError(dictation_id)
        current.seen_at = self._clock()

    def close(self, dictation_id: str) -> None:
        if self._open is not None and self._open.id == dictation_id:
            self._open = None

    def any_open(self) -> bool:
        return self._current() is not None

    def _current(self) -> _Dictation | None:
        current = self._open
        now = self._clock()
        if current is not None and (
            now - current.seen_at >= _QUIET_SECONDS
            or now - current.opened_at >= _LONGEST_SECONDS
        ):
            self._open = current = None
        return current
