"""The text of the Word file or PDF a script wrote: its body, and proof it opens."""

from io import BytesIO

import docx
import pypdfium2
from docx.table import Table
from docx.text.paragraph import Paragraph


class UnreadableDocumentError(ValueError):
    """The bytes do not open as the format they were meant to be."""


def word_text(data: bytes) -> str:
    """Paragraphs and table rows in body order, with headings marked as Markdown."""
    try:
        document = docx.Document(BytesIO(data))
    # A file that is not a Word package fails as a zip, package, key or value error.
    except Exception as error:
        raise UnreadableDocumentError from error
    blocks = (_block_text(block) for block in document.iter_inner_content())
    return "\n\n".join(block for block in blocks if block)


def pdf_text(data: bytes) -> str:
    """Each page's text layer, pages apart; a page of only drawings adds nothing."""
    try:
        pdf = pypdfium2.PdfDocument(data)
    except pypdfium2.PdfiumError as error:
        raise UnreadableDocumentError from error
    try:
        if len(pdf) == 0:
            raise UnreadableDocumentError
        pages = [
            page.get_textpage().get_text_range().replace("\r\n", "\n").strip()
            for page in pdf
        ]
    finally:
        pdf.close()
    return "\n\n".join(page for page in pages if page)


def _block_text(block: Paragraph | Table) -> str:
    if isinstance(block, Table):
        # A merged cell is the same object in every column it spans.
        return "\n".join(
            " | ".join(cell.text.strip() for cell in dict.fromkeys(row.cells))
            for row in block.rows
        )
    text = block.text.strip()
    level = _heading_level(block)
    return f"{'#' * level} {text}" if text and level else text


def _heading_level(paragraph: Paragraph) -> int:
    name = paragraph.style.name if paragraph.style is not None else ""
    if name == "Title":
        return 1
    level = name.removeprefix("Heading ")
    return int(level) if level != name and level.isdigit() else 0
