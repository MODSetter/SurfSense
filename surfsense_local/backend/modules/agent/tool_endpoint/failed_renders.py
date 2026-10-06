"""The three-failures stop: after a turn's third failed run of one kind, that tool refuses until the next turn.

Every failure tells the model to stop at three; small models did not (Qwen3.5
9B rendered 21 times in one turn, Gemma 8), so the tool holds the rule itself.
Renders and analyses count apart: a fixed analysis must not use up the renders.
"""

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.tool import ToolCallError, ToolResult

if TYPE_CHECKING:
    from modules.agent.tool_endpoint.turn_scope import TurnScope

FAILED_RUNS = 3

Run = Callable[[Session, "TurnScope", dict[str, Any]], str | ToolResult]

_guard = threading.Lock()
# Failed runs in each thread's current turn, by kind. A success does not reset
# it: a model that fixes one error and makes the next is still looping. A new
# turn drops the thread's counts, so a run still going from the last one counts
# toward that.
_failed: dict[tuple[str, int], list[int]] = {}


class FailedRunError(ToolCallError):
    """A run that failed: one of the turn's three for its kind."""


def begin_turn(thread_id: int) -> None:
    """A new turn of the thread: its renders and analyses may run again."""
    with _guard:
        for key in [key for key in _failed if key[1] == thread_id]:
            del _failed[key]


def stopped(runs: str) -> str:
    """The refusal once a turn has had FAILED_RUNS failed `runs`."""
    return (
        f"{FAILED_RUNS} {runs} failed in this request, so no more {runs} run until "
        "the user's next message. Stop now: tell the user what failed and what you "
        "tried."
    )


def stop_after_three_failures(run: Run, runs: str = "renders") -> Run:
    """`run`, refused once its thread's turn has had FAILED_RUNS failed `runs`."""

    def guarded(
        session: Session, scope: "TurnScope", arguments: dict[str, Any]
    ) -> str | ToolResult:
        with _guard:
            failed = _failed.setdefault((runs, scope.thread_id), [0])
            if failed[0] >= FAILED_RUNS:
                raise ToolCallError(stopped(runs))
        try:
            return run(session, scope, arguments)
        except FailedRunError:
            with _guard:
                failed[0] += 1
            raise

    return guarded
