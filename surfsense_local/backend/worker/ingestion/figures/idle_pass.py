"""Whether ingest queues the figures-only pass for a PDF it did not keep figures
for, to run once nothing else waits: a PDF with pictures in it, raster or drawn."""

from pathlib import Path

from modules.documents.models import Document
from modules.documents.source_figures.figures_pass import queue_figures_pass
from modules.documents.source_figures.layout import figures_dir, read_index
from modules.documents.tasks import PRIORITY_IDLE
from worker.ingestion.pdf_text_layer import TextLayer

# A page drawing more path segments than this may hold a chart drawn as paths.
# No count tells a chart from a table's rules: of 183 agent-run PDFs with no
# image, the 36 the pass found figures in drew 9-39 segments on that page, the
# 147 with none 0-186. Over 30 queues 28 of the 36 (27 are one report written
# again and again), and 97 of the 147, at about 0.9 s a page of idle time;
# over 40 would queue none. The budget volumes' drawn charts drew 59-1128.
CHART_SEGMENTS = 30
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
    if len(layer.pages) > IDLE_PASS_PAGES:
        return False
    return layer.images > 0 or any(
        page.segments > CHART_SEGMENTS for page in layer.pages
    )
