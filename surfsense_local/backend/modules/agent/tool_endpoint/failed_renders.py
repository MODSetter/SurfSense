"""The three-failures stop: after a turn's third failed run toward one limit, its tools refuse until the next turn.

Every failure tells the model to stop at three; small models did not (Qwen3.5
9B rendered 21 times in one turn, Gemma 8), so the tool holds the rule itself.
Renders and revisions share a limit, as both make Studio versions; analyses
keep their own, so a fixed analysis does not use up the renders.
"""

import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
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

_guard = threading.Lock()
# Failed runs in each thread's current turn, by limit, in the order they failed.
# A success does not reset it: a model that fixes one error and makes the next
# is still looping. A new turn drops the thread's counts, so a run still going
# from the last one counts toward that.
_failed: dict[tuple[str, int], list[Runs]] = {}


class FailedRunError(ToolCallError):
    """A run that failed: one of the turn's three for its limit."""


def begin_turn(thread_id: int) -> None:
    """A new turn of the thread: its renders, revisions and analyses may run again."""
    with _guard:
        for key in [key for key in _failed if key[1] == thread_id]:
            del _failed[key]


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
        with _guard:
            failed = _failed.setdefault((runs.limit, scope.thread_id), [])
            if len(failed) >= FAILED_RUNS:
                raise ToolCallError(stopped(failed))
        try:
            return run(session, scope, arguments)
        except FailedRunError:
            with _guard:
                failed.append(runs)
            raise

    return guarded
