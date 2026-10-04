from shared.queue import ingest_queue


@ingest_queue.task(retries=2)
def ingest_document(document_id: int) -> None:
    """Parse, chunk, embed and index one document."""
    # Lazy: the body pulls in Docling and torch, which the API never needs.
    from worker.ingestion import run

    run(document_id)


# No retries: a failure is recorded in the figures index, and a second read of
# the same file would fail the same way.
@ingest_queue.task()
def extract_figures(document_id: int) -> None:
    """Keep the figures of a source ingested before figures were kept."""
    from worker.ingestion.figures.backfill import run

    run(document_id)
