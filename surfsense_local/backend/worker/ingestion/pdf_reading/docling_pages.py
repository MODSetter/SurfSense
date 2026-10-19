"""Which pages of a PDF the text layer refused go to Docling: only those, or all."""

from worker.ingestion.docling_batches.page_runs import PageRun, runs_of
from worker.ingestion.pdf_text_layer import TextLayer
from worker.ingestion.pdf_text_layer.page_triage import PageKind

# With more of its pages flagged than this, a PDF is a scan: Docling reads it
# whole, as before, and keeps its figures as it reads.
MOST_PAGES = 0.5


def pages_for_docling(layer: TextLayer) -> list[PageRun] | None:
    """The runs of pages only Docling reads, or None when it reads the whole file:
    a filled form, a file pdfium cannot read, mostly flagged pages, or pages that
    pass with no running text among them."""
    flagged = [n for n, page in enumerate(layer.pages, start=1) if page.text is None]
    if not flagged or len(flagged) > MOST_PAGES * len(layer.pages):
        return None
    # Covers, titles and stamps alone: the content is in the flagged pages' pixels.
    if not any(
        page.kind is PageKind.TEXT for page in layer.pages if page.text is not None
    ):
        return None
    return runs_of(flagged)
