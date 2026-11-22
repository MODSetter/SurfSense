"""A paragraph that runs on past a batch's last page, joined as one reading would.

Docling's reading order joins a text that ends mid-sentence to the next one, on
the next page too (reading_order_rb.py, predict_merges); a batch never sees the
next batch's first page, so the join is made here, by the same rule. Without it
a budget volume read in 7-page batches split a paragraph at page 7.
"""

import re
from collections.abc import Iterator, Sequence
from typing import Any

__all__ = ["rejoin_split_paragraphs"]

# Docling's own patterns: an open end, then a word going on.
_OPEN_END = re.compile(r".+([a-z,\-\u00AD])(\s*)")
_GOES_ON = re.compile(r"(\s*[a-zA-Z\u00C0-\u024F])(.+)")


def rejoin_split_paragraphs(parts: Sequence[Any]) -> None:
    """Join, across each edge between consecutive batches' DoclingDocuments, a
    text Docling would have joined; the later batch loses the text it gives."""
    from docling_core.types.doc import DocItemLabel

    # What Docling looks past for the next text: page furniture, floats, notes.
    passed = {
        DocItemLabel.PAGE_HEADER,
        DocItemLabel.PAGE_FOOTER,
        DocItemLabel.TABLE,
        DocItemLabel.PICTURE,
        DocItemLabel.CAPTION,
        DocItemLabel.FOOTNOTE,
    }
    tail = None
    for part in parts:
        items = [item for item in _in_reading_order(part) if item.label not in passed]
        if not items:
            continue  # a batch with no text: the text before it goes on past it
        head = items[0]
        if tail is not None and _joins(tail, head, DocItemLabel.TEXT):
            _append(tail, head)
            part.delete_items(node_items=[head])
            items = items[1:]
        if items:
            tail = items[-1]


def _joins(tail: Any, head: Any, text_label: Any) -> bool:
    return (
        tail.label == text_label
        and head.label == text_label
        and _OPEN_END.fullmatch(tail.text) is not None
        and _GOES_ON.fullmatch(head.text) is not None
    )


def _append(item: Any, joined: Any) -> None:
    """As ReadingOrderModel._merge_elements: the text, its source and each place."""
    before = len(item.text)
    going_on = joined.text.lstrip()
    split_word = item.text.endswith("\u00ad") or (
        item.text.endswith("-") and going_on and going_on[0].islower()
    )
    if split_word:
        item.text = item.text[:-1] + joined.text
        item.orig = item.orig[:-1] + joined.orig
    else:
        item.text += f" {joined.text}"
        item.orig += f" {joined.orig}"
    # Docling counts a joined text's span from one past the text before it, and
    # each later span from where that text's start now lies.
    head, *rest = joined.prov
    item.prov.append(_moved(head, before + 1))
    shift = (before - 1) if split_word else (before + 1)
    item.prov.extend(_moved(place, shift) for place in rest)
    if item.hyperlink != joined.hyperlink:
        item.hyperlink = None


def _moved(place: Any, shift: int) -> Any:
    start, end = place.charspan
    return place.model_copy(update={"charspan": (start + shift, end + shift)})


def _in_reading_order(document: Any, node: Any = None) -> Iterator[Any]:
    """Each item Docling placed as a page element, in the order it read them; a
    table's or a picture's own items it placed with them, so they are not walked."""
    from docling_core.types.doc import DocItem, PictureItem, TableItem

    for ref in (node or document.body).children:
        child = ref.resolve(document)
        if isinstance(child, DocItem):
            yield child
        if not isinstance(child, PictureItem | TableItem):
            yield from _in_reading_order(document, child)
