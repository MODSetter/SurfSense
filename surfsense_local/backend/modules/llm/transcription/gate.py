"""The one way to the transcription server, which runs one model and one request
at a time anyway: a speaker's phrase goes ahead of a recording's window, and no
window starts while someone dictates or the text runtime is held.

A dictation phrase so waits at most for the window in flight, about 2.5 s for
28 s of audio at the measured 11.5x.
"""

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal

__all__ = ["TranscriptionGate", "WindowWaitError"]

# Why a window is not sent yet. `busy`: another window is in flight.
WaitReason = Literal["dictation", "hold", "busy"]
_POLL_SECONDS = 1.0


class WindowWaitError(Exception):
    def __init__(self, reason: WaitReason) -> None:
        super().__init__(reason)
        self.reason = reason


class TranscriptionGate:
    def __init__(
        self,
        *,
        dictating: Callable[[], bool],
        unload: Callable[[str], Awaitable[None]],
        poll_seconds: float = _POLL_SECONDS,
    ) -> None:
        # A dictation's quiet end is a time, not an event, so waiters poll it.
        self._dictating = dictating
        self._unload = unload
        self._poll_seconds = poll_seconds
        self._in_flight: str | None = None
        self._phrases_waiting = 0
        self._holds = 0
        # The model last sent, which a hold unloads: only this gate loads one.
        self._model: str | None = None
        self._changed = asyncio.Event()

    @asynccontextmanager
    async def dictation_turn(self, model: str) -> AsyncIterator[None]:
        self._phrases_waiting += 1
        try:
            await self._take("dictation", self._busy, deadline=None)
        finally:
            self._phrases_waiting -= 1
        self._model = model
        try:
            yield
        finally:
            self._release()

    @asynccontextmanager
    async def window_turn(
        self, model: str, *, wait_seconds: float
    ) -> AsyncIterator[None]:
        """Raises WindowWaitError once `wait_seconds` pass without a turn."""
        await self._take(
            "window", self._window_blocked, deadline=time.monotonic() + wait_seconds
        )
        self._model = model
        try:
            yield
        finally:
            self._release()

    @asynccontextmanager
    async def text_runtime_held(self) -> AsyncIterator[None]:
        """While a podcast voices or an image draws: no new window, the one in
        flight finishes, then the speech model gives its memory back.
        Dictation goes on, loading the model again behind the memory check."""
        self._holds += 1
        self._notify()
        try:
            await self._take("unload", self._busy, deadline=None)
            try:
                if self._model is not None:
                    await self._unload(self._model)
            finally:
                self._release()
            yield
        finally:
            self._holds -= 1
            self._notify()

    def _busy(self) -> WaitReason | None:
        return "busy" if self._in_flight is not None else None

    def _window_blocked(self) -> WaitReason | None:
        if self._holds:
            return "hold"
        if self._dictating() or self._phrases_waiting or self._in_flight == "dictation":
            return "dictation"
        return self._busy()

    async def _take(
        self,
        kind: str,
        blocked: Callable[[], WaitReason | None],
        *,
        deadline: float | None,
    ) -> None:
        while (reason := blocked()) is not None:
            wait = self._poll_seconds
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WindowWaitError(reason)
                wait = min(wait, remaining)
            changed = self._changed
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(changed.wait(), wait)
        self._in_flight = kind

    def _release(self) -> None:
        self._in_flight = None
        self._notify()

    def _notify(self) -> None:
        # A fresh event per change: every waiter wakes, rechecks, and waits anew.
        self._changed.set()
        self._changed = asyncio.Event()
