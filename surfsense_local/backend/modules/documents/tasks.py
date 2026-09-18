from shared.queue import ingest_queue


@ingest_queue.task(retries=2)
def ingest_document(document_id: int) -> None:
    """Parse, chunk, embed and index one document."""
    # Lazy: the body pulls in Docling and torch, which the API never needs.
    from worker.ingestion import run

    run(document_id)
