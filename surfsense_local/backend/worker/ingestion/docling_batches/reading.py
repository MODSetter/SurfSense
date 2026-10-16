"""Docling's reading of a PDF's pages, a batch at a time, as ingest's parse step.

The ingest queue has one thread, and a 100-page scan holds Docling some 10
minutes: between batches the job checks for a cancel, and gives the queue up
as a recording does once it has had its minute and an upload waits at its
priority or above.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlalchemy.orm import object_session

from modules.documents.docling_batches.layout import batches_dir, docling_dir
from modules.documents.models import Document
from worker.ingestion import parsing
from worker.ingestion.audio.queue_turn import QueueTurn
from worker.ingestion.docling_batches.checkpoint import ReadingCheckpoint
from worker.ingestion.docling_batches.page_runs import PageRun
from worker.ingestion.docling_batches.queue_turn import reading_turn
from worker.jobs import JobYieldedError

__all__ = ["read_batches"]


def read_batches(
    document: Document, original: Path, batches: Sequence[PageRun]
) -> list[Any]:
    """Each batch's DoclingDocument, in order. Raises JobYieldedError to give the
    queue up with the batches read kept; a cancel or a failure drops them."""
    if len(batches) == 1:
        return [parsing.convert(original, page_range=_pages(batches[0]))]
    # The original lies alone in the document's own folder.
    folder = original.parent
    checkpoint = ReadingCheckpoint(
        batches_dir(folder), original, root=docling_dir(folder)
    )
    # The ingest job's own session; a reading outside one has nothing to give way to.
    session = object_session(document)
    turn = reading_turn(session, document) if session is not None else None
    try:
        readings = _read(original, batches, checkpoint, turn)
    except JobYieldedError:
        raise
    except Exception:
        # Not on a shutdown: the row stays processing, a retry carries on.
        checkpoint.drop()
        raise
    checkpoint.drop()
    return readings


def _read(
    original: Path,
    batches: Sequence[PageRun],
    checkpoint: ReadingCheckpoint,
    turn: QueueTurn | None,
) -> list[Any]:
    readings: list[Any] = []
    kept = True  # every batch this run read is on disk, so giving way loses none
    read_here = False
    for batch in batches:
        done = checkpoint.done(_name(batch))
        if done is not None:
            readings.append(done[0])
            continue
        if read_here and turn is not None:
            turn.check_cancelled()
            if kept:
                turn.give_way()
        reading = parsing.convert(original, page_range=_pages(batch))
        kept = checkpoint.keep(_name(batch), reading) and kept
        readings.append(reading)
        read_here = True
    return readings


def _pages(batch: PageRun) -> tuple[int, int]:
    return batch.first, batch.last


def _name(batch: PageRun) -> str:
    return f"pages-{batch.first}-{batch.last}"
