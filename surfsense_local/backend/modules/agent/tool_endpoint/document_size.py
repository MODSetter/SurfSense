"""How long a rendered document is, in its format's own unit: pages, slides, sheets or paragraphs."""

from modules.agent.previews.office_counts import sheet_count, slide_count
from modules.agent.previews.page_images import page_count


def document_size(format: str, primary: bytes, text: str) -> str:
    """A PDF's pages, a deck's slides, a workbook's sheets; for Word, which has
    no pages until laid out, its paragraphs.

    A Word table counts as one paragraph: the extracted text holds it as one block.
    """
    if format == "pdf":
        return _count(page_count(primary), "page")
    if format == "pptx":
        return _count(slide_count(primary) or 0, "slide")
    if format == "xlsx":
        return _count(sheet_count(primary) or 0, "sheet")
    return _count(sum(1 for block in text.split("\n\n") if block.strip()), "paragraph")


def _count(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"
