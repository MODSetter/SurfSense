"""Accepting or rejecting every tracked change in one story, whoever made it.

Accepting keeps insertions and drops deletions; rejecting does the opposite and
restores the properties a format change recorded. A paragraph whose mark goes
joins the paragraph after it, as in Word.
"""

from typing import Literal

from lxml import etree

from modules.artifacts.revised_copies.engines.word_xml import (
    BLOCKS,
    DEL,
    DEL_INSTR,
    DEL_TEXT,
    INS,
    INSTR,
    MOVE_FROM,
    MOVE_TO,
    PPR,
    RANGE_MARKS,
    RPR,
    SECTPR,
    P,
    R,
    T,
    w,
)

Decision = Literal["accept", "reject"]

_TRPR, _NUMPR = w("trPr"), w("numPr")
_PROPERTY_PARENTS = frozenset({RPR, _TRPR, _NUMPR})
_CHANGES = tuple(
    w(tag)
    for tag in (
        "rPrChange",
        "pPrChange",
        "sectPrChange",
        "tblPrChange",
        "tblPrExChange",
        "trPrChange",
        "tcPrChange",
        "tblGridChange",
        "numberingChange",
    )
)
# Elements a recorded format change does not describe, so rejecting it keeps them.
_NOT_IN_CHANGE = frozenset(
    {
        INS,
        DEL,
        MOVE_FROM,
        MOVE_TO,
        RPR,
        SECTPR,
        w("headerReference"),
        w("footerReference"),
        w("cellIns"),
        w("cellDel"),
    }
)
_LEADING = frozenset(
    {INS, DEL, MOVE_FROM, MOVE_TO, w("headerReference"), w("footerReference")}
)
_RANGE_ENDS = tuple(
    w(tag)
    for tag in (
        "moveFromRangeStart",
        "moveFromRangeEnd",
        "moveToRangeStart",
        "moveToRangeEnd",
        "customXmlInsRangeStart",
        "customXmlInsRangeEnd",
        "customXmlDelRangeStart",
        "customXmlDelRangeEnd",
        "customXmlMoveFromRangeStart",
        "customXmlMoveFromRangeEnd",
        "customXmlMoveToRangeStart",
        "customXmlMoveToRangeEnd",
    )
)


def decide_all(root: etree._Element, decision: Decision) -> bool:
    """Accept or reject every revision in this story; True when anything changed."""
    kept, dropped = (INS, MOVE_TO), (DEL, MOVE_FROM)
    if decision == "reject":
        kept, dropped = dropped, kept
    changed = False
    marks: list[etree._Element] = []
    for element in list(root.iter(*dropped)):
        parent = element.getparent()
        if parent is None:
            continue
        changed = True
        if (
            parent.tag == RPR
            and parent.getparent() is not None
            and parent.getparent().tag == PPR
        ):
            marks.append(element)
        elif parent.tag == _TRPR:
            row = parent.getparent()
            row.getparent().remove(row)
        elif parent.tag == _NUMPR:
            parent.getparent().remove(parent)
        elif parent.tag in _PROPERTY_PARENTS:
            parent.remove(element)
        else:
            _remove_keeping_marks(element)
    for element in list(root.iter(*kept)):
        parent = element.getparent()
        if parent is None:
            continue
        changed = True
        if parent.tag in _PROPERTY_PARENTS:
            parent.remove(element)
        else:
            _unwrap(element)
    for element in list(root.iter(w("cellIns"), w("cellDel"))):
        changed = True
        goes = (element.tag == w("cellDel")) == (decision == "accept")
        cell_props = element.getparent()
        if goes:
            cell = cell_props.getparent()
            cell.getparent().remove(cell)
        else:
            cell_props.remove(element)
    changed = _drop_emptied_tables(root) or changed
    for element in list(root.iter(*_CHANGES)):
        changed = True
        if decision == "accept":
            element.getparent().remove(element)
        else:
            _restore(element)
    for element in list(root.iter(*_RANGE_ENDS)):
        changed = True
        element.getparent().remove(element)
    for mark in reversed(marks):
        paragraph = mark.getparent().getparent().getparent()
        mark.getparent().remove(mark)
        _join_next(paragraph)
    if decision == "reject":
        for node in root.iter(DEL_TEXT, DEL_INSTR):
            if not any(a.tag in (DEL, MOVE_FROM) for a in node.iterancestors()):
                node.tag = T if node.tag == DEL_TEXT else INSTR
    return changed


def _drop_emptied_tables(root: etree._Element) -> bool:
    """Word repairs a row without cells and a table without rows, so they go whole."""
    dropped = False
    for row in list(root.iter(w("tr"))):
        if next(row.iter(w("tc")), None) is None:
            row.getparent().remove(row)
            dropped = True
    for table in list(root.iter(w("tbl"))):
        if next(table.iter(w("tr")), None) is None:
            table.getparent().remove(table)
            dropped = True
    return dropped


def _remove_keeping_marks(element: etree._Element) -> None:
    """Remove a change's content but keep bookmarks, comment ranges and references in place."""
    for kept in [
        el for el in element.iter() if el.tag in RANGE_MARKS or _is_reference_run(el)
    ]:
        if any(a is not element and a.tag == R for a in kept.iterancestors()):
            continue
        element.addprevious(kept)
    element.getparent().remove(element)


def _unwrap(element: etree._Element) -> None:
    parent = element.getparent()
    index = parent.index(element)
    for offset, child in enumerate(list(element)):
        parent.insert(index + offset, child)
    parent.remove(element)


def _restore(change: etree._Element) -> None:
    """Put back the properties a format change recorded as before."""
    owner = change.getparent()
    old = next(iter(change), None)
    owner.remove(change)
    if old is None:
        return
    for child in [c for c in owner if c.tag not in _NOT_IN_CHANGE]:
        owner.remove(child)
    position = sum(1 for c in owner if c.tag in _LEADING)
    for offset, child in enumerate(list(old)):
        owner.insert(position + offset, child)


def _is_reference_run(element: etree._Element) -> bool:
    """A run that only holds a comment's reference mark."""
    return (
        element.tag == R
        and element.find(w("commentReference")) is not None
        and all(c.tag in (RPR, w("commentReference")) for c in element)
    )


def _has_text(paragraph: etree._Element) -> bool:
    return any(
        child.tag != PPR
        and child.tag not in RANGE_MARKS
        and not _is_reference_run(child)
        for child in paragraph
    )


def _block(siblings) -> etree._Element | None:
    """The nearest block (paragraph, table, content control) or section properties."""
    return next((s for s in siblings if s.tag in BLOCKS or s.tag == SECTPR), None)


def _join_next(paragraph: etree._Element) -> None:
    """The paragraph's mark is gone: its content joins the next paragraph, or it goes if empty."""
    following = _block(paragraph.itersiblings())
    content = [c for c in paragraph if c.tag != PPR]
    if following is not None and following.tag == P:
        props = following.find(PPR)
        start = following.index(props) + 1 if props is not None else 0
        for offset, child in enumerate(content):
            following.insert(start + offset, child)
        paragraph.getparent().remove(paragraph)
        return
    previous = _block(paragraph.itersiblings(preceding=True))
    if _has_text(paragraph) or previous is None or previous.tag != P:
        return
    for child in content:
        previous.append(child)
    paragraph.getparent().remove(paragraph)
