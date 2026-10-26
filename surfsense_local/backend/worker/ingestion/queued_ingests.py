"""Which sources wait in the ingest queue at a priority or above: a long job gives
the one thread up only to work queued at least as high as its own, or a bulk copy
started after it would finish first."""

from shared.queue import ingest_queue

__all__ = ["ingests_queued_from"]

# As `cancel_ingest_job` revokes it.
_INGEST = "ingest_document"


def ingests_queued_from(priority: int) -> set[int]:
    """Their document ids. A revoked copy stays queued until it is taken, so the
    caller checks the row is still pending. Some 30 ms over 10,000 queued jobs,
    asked between batches of some 25 s."""
    return {
        task.args[0]
        for task in ingest_queue.pending()
        if task.name == _INGEST and (task.priority or 0) >= priority
    }
