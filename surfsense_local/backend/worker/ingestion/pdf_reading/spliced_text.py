"""A PDF's text from two readers: its text layer's pages, and Docling's markdown
in place of the pages only Docling could read."""

from collections.abc import Sequence

from worker.ingestion.docling_batches.page_runs import PageRun
from worker.ingestion.pdf_text_layer import TextLayer
from worker.ingestion.pdf_text_layer.reading import PAGE_BREAK


def spliced(layer: TextLayer, docling: Sequence[tuple[PageRun, str]]) -> str:
    """In page order, a blank line apart, as a text-read PDF's pages are."""
    by_first = {run.first: (run, markdown) for run, markdown in docling}
    parts: list[str] = []
    n = 1
    while n <= len(layer.pages):
        if n in by_first:
            run, markdown = by_first[n]
            parts.append(markdown)
            n = run.last + 1
        else:
            parts.append(layer.pages[n - 1].text or "")
            n += 1
    return PAGE_BREAK.join(parts)
