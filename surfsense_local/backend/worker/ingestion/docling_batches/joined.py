"""A run's batches as one DoclingDocument, as one conversion of the run reads it."""

from collections.abc import Sequence
from typing import Any

from worker.ingestion.docling_batches.edge_paragraphs import rejoin_split_paragraphs
from worker.ingestion.docling_batches.lost_pages import with_every_page
from worker.ingestion.docling_batches.page_runs import PageRun

__all__ = ["joined"]


def joined(batches: Sequence[tuple[PageRun, Any]]) -> Any:
    """Batches of consecutive pages, in page order: every picture on its page."""
    documents = [with_every_page(document, batch.pages) for batch, document in batches]
    if len(documents) == 1:
        return documents[0]
    from docling_core.types.doc import DoclingDocument

    rejoin_split_paragraphs(documents)
    return DoclingDocument.concatenate(documents)
