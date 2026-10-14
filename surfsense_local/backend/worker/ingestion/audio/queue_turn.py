"""A recording's turn on the one-thread ingest queue. An hour at 11.5x real time
holds it for some 5 minutes, so once a minute has passed and another source
waits, the job gives the queue up and carries on later from its checkpoint: a
PDF added midway starts within about a minute."""

import time

from sqlalchemy.orm import Session

from modules.documents.models import Document
from worker.ingestion.audio.waiting_work import other_sources_pending
from worker.jobs import JobYieldedError, raise_if_cancelled

__all__ = ["QueueTurn"]

YIELD_AFTER_SECONDS = 60.0


class QueueTurn:
    def __init__(self, session: Session, document: Document) -> None:
        self._session = session
        self._document = document
        self._started = time.monotonic()

    def check_cancelled(self) -> None:
        """Raises JobCancelledError; holds no write lock past the check."""
        raise_if_cancelled(self._session, self._document)

    def give_way(self) -> None:
        """Raises JobYieldedError once this run has had its minute and a source
        that is not a recording waits."""
        if time.monotonic() - self._started < YIELD_AFTER_SECONDS:
            return
        if other_sources_pending(self._session):
            # A cancel landed meanwhile ends the job, files and all, instead.
            self.check_cancelled()
            raise JobYieldedError
