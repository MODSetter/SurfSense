"""Whether ingest queues the figures-only pass for a PDF it did not keep figures
for, to run once nothing else waits: a PDF with image objects on its pages.

Not for drawing alone: no count of path segments told a chart from a table's
rules. Of 183 agent-run PDFs with no image, over 30 segments on a page caught
figures in 2 distinct documents and queued 97 files with none; over 40, none and
66. The pass loads Docling into the ingest worker, so those wait to be asked.
"""

from pathlib import Path

from modules.documents.models import Document
from modules.documents.source_figures.figures_pass import queue_figures_pass
from modules.documents.source_figures.layout import figures_dir, read_index
from modules.documents.tasks import PRIORITY_IDLE
from worker.ingestion.pdf_text_layer import TextLayer

# Longer files wait to be asked: the pass costs some 6 CPU-s a page.
IDLE_PASS_PAGES = 40


def queue_idle_figures_pass(
    document: Document, original: Path, layer: TextLayer
) -> None:
    """Ready without its figures; Docling keeps them once nothing else waits."""
    if not wants_idle_pass(layer):
        return
    if read_index(figures_dir(original.parent)) is None:
        queue_figures_pass(document.id, PRIORITY_IDLE)


def wants_idle_pass(layer: TextLayer) -> bool:
    return layer.images > 0 and len(layer.pages) <= IDLE_PASS_PAGES
