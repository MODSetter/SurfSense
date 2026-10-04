"""How long a rendered document is, in its format's own unit: pages for a PDF, paragraphs for Word."""

from modules.agent.previews.page_images import page_count


def document_size(format: str, primary: bytes, text: str) -> str:
    """A PDF's pages; for Word, which has no pages until laid out, its paragraphs.

    A Word table counts as one paragraph: the extracted text holds it as one block.
    """
    if format == "pdf":
        return _count(page_count(primary), "page")
    return _count(sum(1 for block in text.split("\n\n") if block.strip()), "paragraph")


def _count(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"
