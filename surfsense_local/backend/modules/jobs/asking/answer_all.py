"""Every item of a run asked of the model, several at once: a question of a workbook, a review
point of a contract. A stop is honoured between items, one item's failed call goes to a person,
and failures that are the connection's fail the run."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from modules.jobs.asking.stopped import FillStoppedError
from modules.jobs.asking.turns import Turns

logger = logging.getLogger(__name__)

# Items whose calls may fail outright before the run itself is taken to be failing, and
# only while they stay under a tenth of the items.
MAX_FAILED_ROWS = 3
# Items under way at once while two models take turns, so each turn has many calls.
TURN_ROWS = 128
# How often a run whose items are all under way checks for a cancel.
STOP_POLL_SECONDS = 2.0


def answer_all[Item, Result](
    rows: list[Item],
    one: Callable[[Item], Result],
    failed: Callable[[Item, Exception], Result],
    workers: int,
    on_row: Callable[[int, int], None] | None,
    stop: Callable[[], bool] | None,
    turns: Turns | None = None,
    *,
    named: Callable[[Item], str] = str,
    counted: str = "questions",
) -> list[Result]:
    """Results in the items' order. A stop is checked on this thread, which alone may read what
    it reads, between items and while they are under way; a call already made is let finish.
    `named` says which item failed in the log; `counted` is what the items are, for a stop."""
    results: dict[int, Result] = {}
    failures = 0

    def in_turn(row: Item) -> Result:
        try:
            return one(row)
        finally:
            turns.finished()  # type: ignore[union-attr]

    def stopped() -> bool:
        if stop is None or not stop():
            return False
        if turns is not None:
            turns.halt()  # items under way raise at their next call
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending: dict[Future, int] = {}
        queue = list(enumerate(rows))
        try:
            while queue or pending:
                while queue and len(pending) < workers:
                    if stopped():
                        queue.clear()
                        break
                    index, row = queue.pop(0)
                    if turns is None:
                        pending[pool.submit(one, row)] = index
                    else:
                        # Counted before its thread starts, so no turn passes while it waits.
                        turns.started()
                        pending[pool.submit(in_turn, row)] = index
                if not pending:
                    break
                done, _ = wait(
                    pending, timeout=STOP_POLL_SECONDS, return_when=FIRST_COMPLETED
                )
                if not done or turns is not None:
                    # Taking turns, every item is under way at once: the stop is read
                    # here, not only before an item starts.
                    if stopped():
                        queue.clear()
                    if not done:
                        continue
                for future in done:
                    index = pending.pop(future)
                    try:
                        results[index] = future.result()
                    except FillStoppedError:
                        raise
                    except Exception as error:
                        # One item's call failing goes to a person; many failing is the
                        # connection itself, which the run reports instead of a sheet of blanks.
                        logger.warning("%s failed", named(rows[index]), exc_info=error)
                        failures += 1
                        every = failures == len(rows)
                        if every or (
                            failures >= MAX_FAILED_ROWS and failures * 10 > len(rows)
                        ):
                            raise
                        results[index] = failed(rows[index], error)
                    if on_row is not None:
                        on_row(len(results), len(rows))
        except BaseException:
            # Items waiting for a turn would otherwise run on to the end of theirs.
            if turns is not None:
                turns.halt()
            raise
    if len(results) < len(rows):
        raise FillStoppedError(
            f"Stopped after {len(results)} of {len(rows)} {counted}."
        )
    return [results[i] for i in range(len(rows))]
