from huey.exceptions import CancelExecution

from shared.queue import ingest_queue

# Higher runs first. A note written during a long folder copy is ready in
# seconds; the copy waits behind it.
PRIORITY_INTERACTIVE = 100
PRIORITY_CHANGED = 50
# A figures pass someone asked for: ahead of a folder import, but behind a note
# or an upload, since each pass is a Docling run and a draft asks for several.
PRIORITY_ASKED = 30
PRIORITY_BULK = 10
# Below every ingest and every figures pass someone asked for: work nobody
# waits on yet.
PRIORITY_IDLE = -10

# An upload of more files than this is a bulk copy.
BULK_UPLOAD_FILES = 20


@ingest_queue.task(retries=2, priority=PRIORITY_INTERACTIVE)
def ingest_document(document_id: int) -> None:
    """Parse, chunk, embed and index one document."""
    # Lazy: the body pulls in Docling and torch, which the API never needs.
    from worker.ingestion import run
    from worker.ingestion.audio.failures import RecordingRefusedError
    from worker.ingestion.parsing import UnreadableFileError

    try:
        run(document_id)
    except (UnreadableFileError, RecordingRefusedError) as refused:
        # Already failed with its reason; a retry would only refuse it again.
        raise CancelExecution(retry=False) from refused


# No retries: a failure is recorded in the figures index, and a second read of
# the same file would fail the same way.
@ingest_queue.task(priority=PRIORITY_ASKED)
def extract_figures(document_id: int) -> None:
    """Keep the figures of a ready source that ingest left without them: a PDF
    read from its text layer, a Word file read without Docling, or one ingested
    before figures were kept."""
    from worker.ingestion.figures.backfill import run

    run(document_id)
