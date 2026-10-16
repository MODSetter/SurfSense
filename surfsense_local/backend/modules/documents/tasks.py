from typing import Any

from huey.exceptions import CancelExecution

from shared.queue import ingest_queue

# Higher runs first. A note written during a long folder copy is ready in
# seconds; the copy waits behind it.
PRIORITY_INTERACTIVE = 100
PRIORITY_CHANGED = 50
PRIORITY_BULK = 10
# Below every ingest and every figures pass someone asked for: work nobody
# waits on yet.
PRIORITY_IDLE = -10

# An upload of more files than this is a bulk copy.
BULK_UPLOAD_FILES = 20


# Huey hands the task itself in: a long reading gives way only to work queued as
# high as its own, and queues again at it.
@ingest_queue.task(retries=2, context=True, priority=PRIORITY_INTERACTIVE)
def ingest_document(document_id: int, task: Any = None) -> None:
    """Parse, chunk, embed and index one document."""
    # Lazy: the body pulls in Docling and torch, which the API never needs.
    from worker.ingestion import run
    from worker.ingestion.audio.failures import RecordingRefusedError
    from worker.ingestion.parsing import UnreadableFileError

    try:
        run(document_id, PRIORITY_INTERACTIVE if task is None else task.priority)
    except (UnreadableFileError, RecordingRefusedError) as refused:
        # Already failed with its reason; a retry would only refuse it again.
        raise CancelExecution(retry=False) from refused


# No retries: a failure is recorded in the figures index, and a second read of
# the same file would fail the same way. Interactive unless queued otherwise:
# whoever asks for figures is waiting on them. Huey hands the task itself in,
# so a pass that gives the queue up queues again at the priority it came with.
@ingest_queue.task(context=True, priority=PRIORITY_INTERACTIVE)
def extract_figures(document_id: int, task: Any = None) -> None:
    """Keep the figures of a ready source that ingest left without them: a PDF
    read from its text layer or partly from it, a Word file read without
    Docling, or one ingested before figures were kept."""
    from worker.ingestion.figures.backfill import run

    run(document_id, PRIORITY_INTERACTIVE if task is None else task.priority)
