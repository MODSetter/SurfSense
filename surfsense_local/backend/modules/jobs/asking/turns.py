"""Two models that cannot be loaded at once, the answering one and the checker, taking turns."""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable

from modules.jobs.asking.model import AnswerModel, ModelReply
from modules.jobs.asking.stopped import FillStoppedError


class Turns:
    """Two models that cannot be loaded at once take turns. A call to the one out of turn
    waits; the turn passes when the one in turn has no call running or waiting and no question
    is still working towards one. The local runtime holds one model at a time, so answering
    with one model and checking with another would otherwise load a model twice a question."""

    def __init__(self, slots: int) -> None:
        self._slots = max(slots, 1)
        self._turn: str | None = None
        self._running = 0
        self._waiting: Counter[str] = Counter()
        # Questions under way and not waiting for a turn: between calls, or in one.
        self._working = 0
        self._halted = False
        self._lock = threading.Lock()
        # One condition a side, so a freed slot wakes only calls that may take it.
        self._ready: dict[str, threading.Condition] = {}

    def started(self) -> None:
        with self._lock:
            self._working += 1

    def finished(self) -> None:
        with self._lock:
            self._working -= 1
            self._pass()

    def halt(self) -> None:
        """Every call not yet running raises FillStoppedError from now on."""
        with self._lock:
            self._halted = True
            for ready in self._ready.values():
                ready.notify_all()

    def ask(self, side: str, call: Callable[[], ModelReply]) -> ModelReply:
        with self._lock:
            ready = self._ready.setdefault(side, threading.Condition(self._lock))
            self._working -= 1
            self._waiting[side] += 1
            self._pass()
            while not self._halted and not (
                self._turn == side and self._running < self._slots
            ):
                ready.wait()
            self._waiting[side] -= 1
            self._working += 1
            if self._halted:
                raise FillStoppedError("Stopped while questions were under way.")
            self._running += 1
        try:
            return call()
        finally:
            with self._lock:
                self._running -= 1
                self._pass()

    def _pass(self) -> None:
        """Held with the lock. The turn passes to a side that waits once nothing more can come
        of the side in turn; then as many calls of the side in turn wake as there are slots."""
        if self._turn is None or not (self._working or self._waiting[self._turn]):
            waiting = [side for side, count in self._waiting.items() if count]
            if waiting:
                self._turn = waiting[0]
        if self._turn is not None and self._running < self._slots:
            self._ready[self._turn].notify(self._slots - self._running)


class TurnModel:
    """A model whose calls wait for its side's turn."""

    def __init__(self, model: AnswerModel, turns: Turns, side: str) -> None:
        self._model = model
        self._turns = turns
        self._side = side
        self.name = model.name
        self.window = model.window
        self.concurrency = model.concurrency

    def ask(
        self, system: str, turns: list[tuple[str, str]], schema: dict, shared: int
    ) -> ModelReply:
        return self._turns.ask(
            self._side, lambda: self._model.ask(system, turns, schema, shared)
        )


def taking_turns(
    model: AnswerModel, checker: AnswerModel | None, take_turns: bool
) -> tuple[Turns | None, AnswerModel, AnswerModel | None]:
    """The turns, when the checker cannot be loaded beside the model, and the two models as a
    run asks them."""
    turns = Turns(model.concurrency) if take_turns and checker is not None else None
    if turns is None:
        return None, model, checker
    return (
        turns,
        TurnModel(model, turns, "answer"),
        TurnModel(checker, turns, "check"),  # type: ignore[arg-type]
    )
