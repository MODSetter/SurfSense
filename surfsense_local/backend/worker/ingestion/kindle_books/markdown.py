from pathlib import Path

from modules.documents.kindle_books.container import KindleBookError
from worker.ingestion.figures.store import keep_no_figures
from worker.ingestion.html_line_breaks import without_left_breaks
from worker.ingestion.kindle_books.reading import book_html
from worker.ingestion.parsing import UnreadableFileError, convert_html


def book_markdown(path: Path) -> str:
    """A MOBI or AZW3 book as markdown: its HTML, read by Docling's HTML reader."""
    try:
        html = book_html(path.read_bytes())
    except KindleBookError as refused:
        # Damage and DRM fail the same way on every retry.
        raise UnreadableFileError(str(refused)) from refused
    # Its pictures are records Docling cannot reach from the HTML; none are kept.
    keep_no_figures(path)
    return without_left_breaks(convert_html(html, path.stem).export_to_markdown())
