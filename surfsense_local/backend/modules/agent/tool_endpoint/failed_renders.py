"""The three-failures stop: after a turn's third failed run toward one limit, its tools refuse until the next turn.

Every failure tells the model to stop at three; small models did not (Qwen3.5
9B rendered 21 times in one turn, Gemma 8), so the tool holds the rule itself.
Renders and revisions share a limit, as both make Studio versions; analyses
keep their own, so a fixed analysis does not use up the renders.
"""

import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.tool import ToolCallError, ToolResult

if TYPE_CHECKING:
    from modules.agent.tool_endpoint.turn_scope import TurnScope

FAILED_RUNS = 3

Run = Callable[[Session, "TurnScope", dict[str, Any]], str | ToolResult]


@dataclass(frozen=True)
class Runs:
    """A tool's runs as the refusal names them, and the limit they count toward."""

    one: str
    many: str
    limit: str  # every kind of run the limit stops, as the refusal says it


RENDERS = Runs("render", "renders", "renders or revisions")
REVISIONS = Runs("revision", "revisions", "renders or revisions")
ANALYSES = Runs("analysis run", "analysis runs", "analysis runs")
IMAGES = Runs("picture", "pictures", "pictures")

_guard = threading.Condition()


@dataclass
class _Turn:
    """One limit's runs in a thread's current turn."""

    # In the order they failed. A success does not reset it: a model that fixes
    # one error and makes the next is still looping.
    failed: list[Runs] = field(default_factory=list)
    # Runs under way, each of which may yet fail.
    running: int = 0
    # Artifacts still being made when their call answered: no call sees them fail.
    queued: set[int] = field(default_factory=set)


# A new turn drops the thread's entries, so a run still going from the last one
# counts toward that.
_turns: dict[tuple[str, int], _Turn] = {}


class FailedRunError(ToolCallError):
    """A run that failed: one of the turn's three for its limit."""


def begin_turn(thread_id: int) -> None:
    """A new turn of the thread: its renders, revisions and analyses may run again."""
    with _guard:
        for key in [key for key in _turns if key[1] == thread_id]:
            del _turns[key]
        _guard.notify_all()


def note_queued(runs: Runs, thread_id: int, artifact_id: int) -> None:
    """A run whose call answered before it ended, to settle with `settle_queued`."""
    with _guard:
        _turns.setdefault((runs.limit, thread_id), _Turn()).queued.add(artifact_id)


def queued_runs(runs: Runs, thread_id: int) -> frozenset[int]:
    with _guard:
        turn = _turns.get((runs.limit, thread_id))
        return frozenset(turn.queued) if turn is not None else frozenset()


def settle_queued(runs: Runs, thread_id: int, artifact_id: int, failed: bool) -> None:
    """A queued run has ended; one that failed counts as if its call had seen it."""
    with _guard:
        turn = _turns.get((runs.limit, thread_id))
        if turn is None or artifact_id not in turn.queued:
            return
        turn.queued.discard(artifact_id)
        if failed:
            turn.failed.append(runs)
        _guard.notify_all()


def stopped(failed: list[Runs]) -> str:
    """The refusal once a turn's limit is spent, naming what failed: "2 renders and 1 revision"."""
    counts = Counter(failed)
    named = [f"{n} {runs.one if n == 1 else runs.many}" for runs, n in counts.items()]
    which = named[0] if len(named) == 1 else f"{', '.join(named[:-1])} and {named[-1]}"
    return (
        f"{which} failed in this request, so no more {failed[0].limit} run until "
        "the user's next message. Stop now: tell the user what failed and what you "
        "tried."
    )


def stop_after_three_failures(run: Run, runs: Runs) -> Run:
    """`run`, refused once its thread's turn has had FAILED_RUNS failed runs toward its limit."""

    def guarded(
        session: Session, scope: "TurnScope", arguments: dict[str, Any]
    ) -> str | ToolResult:
        key = (runs.limit, scope.thread_id)
        with _guard:
            # opencode runs a step's calls at once: no more run than may still fail.
            while True:
                turn = _turns.setdefault(key, _Turn())
                if len(turn.failed) >= FAILED_RUNS:
                    raise ToolCallError(stopped(turn.failed))
                if len(turn.failed) + turn.running < FAILED_RUNS:
                    break
                _guard.wait()
            turn.running += 1
        failed = False
        try:
            return run(session, scope, arguments)
        except FailedRunError:
            failed = True
            raise
        finally:
            with _guard:
                turn.running -= 1
                if failed:
                    turn.failed.append(runs)
                _guard.notify_all()

    return guarded
