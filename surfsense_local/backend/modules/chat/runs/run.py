import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

DONE = b"data: [DONE]\n\n"


@dataclass(frozen=True)
class RunState:
    """Where a run stands, as its engine says: `queued` with its place in line,
    `running`, or `needs-approval` while it waits on the user."""

    state: str
    position: int | None = None


class Run:
    """One reply being generated, and every frame it has sent so far.

    The frames stay with the run, so a window that leaves and comes back can
    replay what it missed; the run itself never depends on anyone watching.
    """

    def __init__(self, on_state: Callable[[RunState], None] | None = None) -> None:
        self._frames: list[bytes] = []
        self._on_state = on_state
        self.state = RunState("running")
        self._changed = asyncio.Event()
        self._finished = False
        self._stop_requested = False
        self.task: asyncio.Task[None] | None = None

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    def add(self, frame: bytes) -> None:
        """Number a frame and hand it to every follower."""
        self._frames.append(b"id: %d\n" % (len(self._frames) + 1) + frame)
        self._wake()

    def set_state(self, state: RunState) -> None:
        """Record where the run stands, send it as a frame, and tell every window."""
        if state == self.state:
            return
        self.state = state
        payload: dict = {"type": "run-state", "state": state.state}
        if state.position is not None:
            payload["position"] = state.position
        self.add(f"data: {json.dumps(payload)}\n\n".encode())
        if self._on_state is not None:
            self._on_state(state)

    def finish(self) -> None:
        """No more frames; followers drain what is left and close."""
        if not self._frames or not self._frames[-1].endswith(DONE):
            self.add(DONE)
        self._finished = True
        self._wake()

    def stop(self) -> None:
        """The person ends the reply; it stores what it has before it goes."""
        self._stop_requested = True
        self.interrupt()

    def interrupt(self) -> None:
        """End the reply because the app is going away, not by anyone's choice."""
        if self.task is not None:
            self.task.cancel()

    async def follow(self, after: int = 0) -> AsyncIterator[bytes]:
        """The frames numbered above `after`, then each new one as it comes."""
        index = max(0, after)
        while True:
            while index < len(self._frames):
                yield self._frames[index]
                index += 1
            if self._finished:
                return
            await self._changed.wait()

    def _wake(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()
