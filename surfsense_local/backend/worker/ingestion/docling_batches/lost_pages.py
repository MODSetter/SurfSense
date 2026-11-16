"""A page Docling could not read, kept in its reading as an empty page.

Joining readings numbers each one's pages on from where the last ended
(DoclingDocument.concatenate), so a page missing at a batch's edge would move
every later picture, and its crop, onto the page before its own. One reading of
the whole file lacks that page the same way, with every other page in place.
"""

from typing import Any

__all__ = ["with_every_page"]


def with_every_page(document: Any, pages: range) -> Any:
    """`document`, a DoclingDocument of `pages`, with any it lacks added empty."""
    missing = [n for n in pages if n not in document.pages]
    if not missing:
        return document
    from docling_core.types.doc import Size

    # Only the page's number matters: crops are measured on the PDF's own page.
    size = next(iter(document.pages.values())).size if document.pages else Size()
    for n in missing:
        document.add_page(page_no=n, size=size)
    document.pages = dict(sorted(document.pages.items()))
    return document
