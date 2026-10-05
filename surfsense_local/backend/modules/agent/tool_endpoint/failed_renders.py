"""The three-failures stop: after a turn's third failed render, the render tool refuses until the next turn.

Every failure tells the model to stop at three; small models did not (Qwen3.5
9B rendered 21 times in one turn, Gemma 8), so the tool holds the rule itself.
"""

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.tool import ToolCallError

if TYPE_CHECKING:
    from modules.agent.tool_endpoint.turn_scope import TurnScope

FAILED_RUNS = 3
STOPPED = (
    f"{FAILED_RUNS} renders failed in this request, so no more renders run until "
    "the user's next message. Stop now: tell the user what failed and what you tried."
)

Run = Callable[[Session, "TurnScope", dict[str, Any]], str]

_guard = threading.Lock()
# Failed runs in each thread's current turn. A success does not reset it: a
# model that fixes one error and makes the next is still looping. A new turn
# drops the list, so a run still going from the last one counts toward that.
_failed: dict[int, list[int]] = {}


class FailedRunError(ToolCallError):
    """A render whose run failed: one of the turn's three."""


def begin_turn(thread_id: int) -> None:
    """A new turn of the thread: its renders may run again."""
    with _guard:
        _failed.pop(thread_id, None)


def stop_after_three_failures(run: Run) -> Run:
    """`run`, refused once its thread's turn has had FAILED_RUNS failed runs."""

    def guarded(session: Session, scope: "TurnScope", arguments: dict[str, Any]) -> str:
        with _guard:
            failed = _failed.setdefault(scope.thread_id, [0])
            if failed[0] >= FAILED_RUNS:
                raise ToolCallError(STOPPED)
        try:
            return run(session, scope, arguments)
        except FailedRunError:
            with _guard:
                failed[0] += 1
            raise

    return guarded
