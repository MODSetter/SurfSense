"""A run's batches as one DoclingDocument, as one conversion of the run reads it."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from worker.ingestion.docling_batches.edge_paragraphs import rejoin_split_paragraphs
from worker.ingestion.docling_batches.page_runs import PageRun

__all__ = ["JoinedReading", "joined"]


@dataclass(frozen=True)
class JoinedReading:
    document: Any  # a DoclingDocument
    # Every batch held exactly its pages. Joining numbers each batch's pages on
    # from where the last ended, so a page Docling dropped would move every
    # later picture to the wrong page, and its crop with it.
    pages_kept: bool


def joined(batches: Sequence[tuple[PageRun, Any]]) -> JoinedReading:
    """Batches of consecutive pages, in page order."""
    kept = all(set(document.pages) == set(batch.pages) for batch, document in batches)
    documents = [document for _batch, document in batches]
    if len(documents) == 1:
        return JoinedReading(documents[0], kept)
    from docling_core.types.doc import DoclingDocument

    rejoin_split_paragraphs(documents)
    return JoinedReading(DoclingDocument.concatenate(documents), kept)
