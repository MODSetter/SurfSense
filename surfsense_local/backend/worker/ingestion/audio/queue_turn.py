"""A recording's turn on the one-thread ingest queue. An hour at 11.5x real time
holds it for some 5 minutes, so once a minute has passed and another source
waits, the job gives the queue up and carries on later from its checkpoint: a
PDF added midway starts within about a minute. A long Docling reading takes its
turn the same way, giving way to the sources its own rule names."""

import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from modules.documents.models import Document
from modules.documents.tasks import PRIORITY_BULK
from worker.ingestion.audio.waiting_work import other_sources_pending
from worker.jobs import JobYieldedError, raise_if_cancelled

__all__ = ["QueueTurn"]

YIELD_AFTER_SECONDS = 60.0


class QueueTurn:
    """`gives_way_to` says whether a source waits that the job gives way to;
    `comes_back_at` is the priority its job queues again at."""

    def __init__(
        self,
        session: Session,
        document: Document,
        gives_way_to: Callable[[Session], bool] = other_sources_pending,
        *,
        after_seconds: float | None = None,
        comes_back_at: int = PRIORITY_BULK,
    ) -> None:
        self._session = session
        self._document = document
        self._gives_way_to = gives_way_to
        self._after_seconds = after_seconds
        self._comes_back_at = comes_back_at
        self._started = time.monotonic()

    def check_cancelled(self) -> None:
        """Raises JobCancelledError; holds no write lock past the check."""
        raise_if_cancelled(self._session, self._document)

    def give_way(self) -> None:
        """Raises JobYieldedError once this run has had its minute and a source
        waits that it gives way to: for a recording, one that is not a recording."""
        after = (
            YIELD_AFTER_SECONDS if self._after_seconds is None else self._after_seconds
        )
        if time.monotonic() - self._started < after:
            return
        if self._gives_way_to(self._session):
            # A cancel landed meanwhile ends the job, files and all, instead.
            self.check_cancelled()
            raise JobYieldedError(self._comes_back_at)
