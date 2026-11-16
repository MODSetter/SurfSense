"""A long Docling reading's turn on the one-thread ingest queue: a recording's
(audio/queue_turn.py), giving way to the sources waiting_work.py names and
queueing again at the priority its job came with."""

from functools import partial

from sqlalchemy.orm import Session

from modules.documents.models import Document
from worker.ingestion.audio.queue_turn import QueueTurn
from worker.ingestion.docling_batches.waiting_work import sources_to_give_way_to
from worker.ingestion.job_priority import job_priority

__all__ = ["reading_turn"]

YIELD_AFTER_SECONDS = 60.0


def reading_turn(session: Session, document: Document) -> QueueTurn:
    priority = job_priority()
    return QueueTurn(
        session,
        document,
        partial(sources_to_give_way_to, priority=priority),
        after_seconds=YIELD_AFTER_SECONDS,
        comes_back_at=priority,
    )
