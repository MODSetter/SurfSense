"""The job codes a run held back: each code whose check was deferred because a run of its pack
was pending or processing, with that pack's id, until the schedule checks the code once more
after the run ends (contract 6, consumer rule 5).

Process-wide, since the user's Download and the schedule's own checks both defer, and in
memory only: a restart begins with the startup check, which asks for every code anyway.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable


class HeldBack:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._codes: dict[str, str] = {}
        self._listeners: list[Callable[[], None]] = []

    def hold(self, code: str, pack_id: str) -> None:
        """Record that a run of `pack_id` held `code`'s check back, and tell the listeners."""
        with self._lock:
            self._codes[code] = pack_id
            listeners = list(self._listeners)
        for told in listeners:
            told()

    def release(self, codes: Iterable[str]) -> None:
        """Forget these codes: checked since, or about to be."""
        with self._lock:
            for code in codes:
                self._codes.pop(code, None)

    def held(self) -> dict[str, str]:
        """Each code held back, to the id of the pack whose run held it."""
        with self._lock:
            return dict(self._codes)

    def listen(self, told: Callable[[], None]) -> Callable[[], None]:
        """Calls `told`, from whatever thread holds a code, each time one is held, until the
        function returned is called."""
        with self._lock:
            self._listeners.append(told)

        def stop() -> None:
            with self._lock:
                if told in self._listeners:
                    self._listeners.remove(told)

        return stop


HELD_BACK = HeldBack()
