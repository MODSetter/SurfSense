import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

DONE = b"data: [DONE]\n\n"

# Frames that only append text, as both engines spell them; consecutive ones
# of a kind read the same as one frame carrying their joined text.
_TEXT_HEADS = {
    "delta": b'data: {"type": "delta", "text": "',
    "reasoning": b'data: {"type": "reasoning", "text": "',
}
_TEXT_TAIL = b'"}\n\n'


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
        # Each frame's text kind, or None for a frame that is not only text.
        self._kinds: list[str | None] = []
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
        self._kinds.append(_text_kind(frame))
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
        """The frames numbered above `after`, then each new one as it comes.

        Text frames of one kind already waiting in a row go as one, numbered as
        the last of them, so a window that attaches mid-reply replays a few
        frames rather than one per token. Nothing waits to be merged.
        """
        index = max(0, after)
        while True:
            while index < len(self._frames):
                last = self._last_alike(index)
                yield (
                    self._frames[index] if last == index else self._merged(index, last)
                )
                index = last + 1
            if self._finished:
                return
            await self._changed.wait()

    def _last_alike(self, index: int) -> int:
        """The last frame of the run of same-kind text frames starting at `index`."""
        kind = self._kinds[index]
        last = index
        while kind and last + 1 < len(self._kinds) and self._kinds[last + 1] == kind:
            last += 1
        return last

    def _merged(self, first: int, last: int) -> bytes:
        """Frames `first` to `last` as one, carrying the last one's id.

        JSON escapes a string a character at a time, so the strings' insides
        joined are the joined text's, escaped, with nothing to parse again.
        """
        head = _TEXT_HEADS[self._kinds[first]]
        inner = b"".join(
            stored[stored.index(b"\n") + 1 + len(head) : -len(_TEXT_TAIL)]
            for stored in self._frames[first : last + 1]
        )
        return b"id: %d\n%s%s%s" % (last + 1, head, inner, _TEXT_TAIL)

    def _wake(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()


def _text_kind(frame: bytes) -> str | None:
    """`delta` or `reasoning` for a frame that carries nothing but text, spelled
    exactly as json.dumps spells it."""
    if not frame.endswith(_TEXT_TAIL):
        return None
    for kind, head in _TEXT_HEADS.items():
        if frame.startswith(head):
            # Every quote inside a string is escaped, so with none between head
            # and tail the frame holds that one string. Only a frame with one is
            # parsed: parsing every token's would double what a token costs here.
            if b'"' not in frame[len(head) : -len(_TEXT_TAIL)]:
                return kind
            return kind if _only_text(frame) else None
    return None


def _only_text(frame: bytes) -> bool:
    """Whether the frame is json.dumps of a type and a text, and nothing else."""
    payload = json.loads(frame[len(b"data: ") :])
    return (
        payload.keys() == {"type", "text"}
        and isinstance(payload["text"], str)
        and frame == f"data: {json.dumps(payload)}\n\n".encode()
    )
