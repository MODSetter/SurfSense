"""How far a run has got, written beside its record while its questions are answered, for the
Jobs screen to poll.

Each write is one statement in a short session of its own: the run's session is never touched,
so a write skipped for a lock never expires the objects the question threads read.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from shared.db import is_locked

# Often enough for a progress bar; each write takes the write lock for a moment.
PROGRESS_SECONDS = 2.0

_WRITE = text(
    "UPDATE artifacts SET artifact_metadata = json_set(artifact_metadata, "
    "'$.job_run.progress', json_object('done', :done, 'total', :total)) WHERE id = :id"
)


def write_progress(engine: Engine, artifact_id: int, done: int, total: int) -> bool:
    """Whether the count was written; a lock held past the busy wait skips it."""
    with Session(engine) as session:
        try:
            session.execute(_WRITE, {"done": done, "total": total, "id": artifact_id})
            session.commit()
        except OperationalError as error:
            session.rollback()
            if not is_locked(error):
                raise
            return False
    return True


class RunProgress:
    """The runner's `on_row`: the total at once, then the count at most every
    PROGRESS_SECONDS, a write that was skipped tried again at the next row. `last` keeps the
    latest count, written or not, for the run's final write."""

    def __init__(
        self,
        write: Callable[[int, int], bool],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._write = write
        self._clock = clock
        self._written_at: float | None = None
        self.last: dict[str, int] | None = None

    def on_row(self, done: int, total: int) -> None:
        self.last = {"done": done, "total": total}
        now = self._clock()
        if (
            done
            and self._written_at is not None
            and now - self._written_at < PROGRESS_SECONDS
        ):
            return
        if self._write(done, total):
            self._written_at = now
