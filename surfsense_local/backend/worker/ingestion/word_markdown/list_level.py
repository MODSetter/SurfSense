"""Which list and level Word numbers a paragraph on: its own w:numPr, else its style's."""

from typing import Any

from worker.ingestion.word_markdown.numbering import ListNumbering
from worker.ingestion.word_markdown.ooxml_names import (
    ILVL,
    NUM_ID,
    NUM_PR,
    P_PR,
    P_STYLE,
    VAL,
    w,
)
from worker.ingestion.word_markdown.styles import ParagraphStyles

_MARK_PROPERTIES = w("rPr")
_REMOVED = frozenset({w("del"), w("moveFrom")})


def list_level(
    paragraph: Any, styles: ParagraphStyles, numbering: ListNumbering
) -> tuple[str | None, tuple[str, int] | None]:
    """The paragraph's w:pStyle, and its list and level if it is numbered."""
    properties = paragraph.find(P_PR)
    style_id = num_id = None
    ilvl: int | None = None
    if properties is not None:
        style = properties.find(P_STYLE)
        style_id = None if style is None else style.get(VAL)
        mark = properties.find(_MARK_PROPERTIES)
        if mark is not None and any(c.tag in _REMOVED for c in mark):
            # A tracked deletion of the paragraph itself: Word, accepting
            # the change, neither shows nor counts its number.
            return style_id, None
        num_pr = properties.find(NUM_PR)
        if num_pr is not None:
            num_id = _val(num_pr.find(NUM_ID))
            ilvl = _int(_val(num_pr.find(ILVL)))
    from_style = styles.numbering(style_id)
    if num_id is None:
        num_id = from_style.num_id
    if num_id is None or num_id == "0" or not numbering.exists(num_id):
        return style_id, None
    if ilvl is None:
        ilvl = from_style.ilvl
    if ilvl is None:
        # Word numbers such a paragraph at level 0 only when that level is
        # not tied to another style: Heading 3 on Heading 1's level shows none.
        tied = numbering.style_of_level(num_id, 0)
        if tied is not None and tied != styles.resolved_id(style_id):
            return style_id, None
    return style_id, (num_id, ilvl or 0)


def _val(element: Any | None) -> str | None:
    return None if element is None else element.get(VAL)


def _int(text: str | None) -> int | None:
    try:
        return int(text) if text is not None else None
    except ValueError:
        return None
