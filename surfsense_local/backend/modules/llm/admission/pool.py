import asyncio
import enum
import itertools
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

# A guard on a runaway caller, not a limit one person meets.
MAX_WAITING = 64


class Priority(enum.IntEnum):
    """Who goes first: what someone is watching, then what runs in the background."""

    INTERACTIVE = 0
    BACKGROUND = 1


class LineFullError(Exception):
    """More requests are waiting than any one person could have sent."""


@dataclass(eq=False)
class _Waiter:
    cost: int
    priority: Priority
    order: int
    granted: asyncio.Future[None]
    on_position: Callable[[int], None] | None
    position: int = field(default=0)


class AdmissionPool:
    """The slots and shared cache of one loaded model, and the line for them.

    A request is let in when a slot is free and its tokens fit beside those
    already committed; one that would be refused only for being long is let in
    when nothing else runs, since the window, not admission, refuses an
    oversize prompt. The line is ordered by priority, then arrival, and its
    head is never overtaken: a large request cannot be starved by small ones.
    `budget` None counts slots alone, for a cache whose size is unknown.
    """

    def __init__(
        self, slots: int, budget: int | None, max_waiting: int = MAX_WAITING
    ) -> None:
        self.slots = max(1, slots)
        self.budget = budget
        self._max_waiting = max_waiting
        self._running = 0
        self._committed = 0
        self._waiting: list[_Waiter] = []
        self._arrivals = itertools.count()
        self._paused = False
        self._drained = asyncio.Event()
        self._drained.set()

    @property
    def idle(self) -> bool:
        return self._running == 0 and not self._waiting and not self._paused

    def pause(self) -> None:
        """Admit nobody until `resume`; those waiting keep their place."""
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        self._admit_waiting()

    async def drained(self) -> None:
        """Return once nothing admitted is still generating."""
        await self._drained.wait()

    @asynccontextmanager
    async def admitted(
        self,
        cost: int,
        priority: Priority,
        on_position: Callable[[int], None] | None = None,
    ) -> AsyncIterator[None]:
        """Hold a slot and `cost` tokens for the block; wait in line for them."""
        if not self._waiting and self._fits(cost):
            self._take(cost)
        else:
            await self._wait(cost, priority, on_position)
        try:
            yield
        finally:
            self._give_back(cost)

    async def _wait(
        self,
        cost: int,
        priority: Priority,
        on_position: Callable[[int], None] | None,
    ) -> None:
        if len(self._waiting) >= self._max_waiting:
            raise LineFullError("too many requests are waiting for the model")
        waiter = _Waiter(
            cost,
            priority,
            next(self._arrivals),
            asyncio.get_running_loop().create_future(),
            on_position,
        )
        self._waiting.append(waiter)
        self._waiting.sort(key=lambda w: (w.priority, w.order))
        self._tell_positions()
        try:
            await waiter.granted
        except asyncio.CancelledError:
            if waiter.granted.done() and not waiter.granted.cancelled():
                # Let in at the moment it left: hand the room on.
                self._give_back(cost)
            else:
                self._waiting.remove(waiter)
                self._admit_waiting()
            raise

    def _fits(self, cost: int) -> bool:
        if self._paused or self._running >= self.slots:
            return False
        if self._running == 0 or self.budget is None:
            return True
        return self._committed + cost <= self.budget

    def _take(self, cost: int) -> None:
        self._running += 1
        self._committed += cost
        self._drained.clear()

    def _give_back(self, cost: int) -> None:
        self._running -= 1
        self._committed -= cost
        if self._running == 0:
            self._drained.set()
        self._admit_waiting()

    def _admit_waiting(self) -> None:
        while self._waiting and self._fits(self._waiting[0].cost):
            head = self._waiting.pop(0)
            if head.granted.done():
                # Cancelled and not yet cleaned up after: it has left the line.
                continue
            self._take(head.cost)
            head.granted.set_result(None)
        self._tell_positions()

    def _tell_positions(self) -> None:
        for place, waiter in enumerate(self._waiting, start=1):
            if waiter.position != place:
                waiter.position = place
                if waiter.on_position is not None:
                    waiter.on_position(place)
