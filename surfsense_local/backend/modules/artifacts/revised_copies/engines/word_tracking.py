"""Writing tracked changes: runs split at a quote's edges, w:del around old text, w:ins for new.

There is no untracked path: every function here marks what it changes with the
author and date of one Stamp.
"""

import copy
from collections.abc import Iterable
from datetime import UTC, datetime

from lxml import etree

from modules.artifacts.revised_copies.engines.word_text import Atom
from modules.artifacts.revised_copies.engines.word_xml import (
    DEL,
    DEL_INSTR,
    DEL_TEXT,
    INS,
    INSTR,
    MOVE_FROM,
    MOVE_TO,
    PPR,
    RPR,
    SECTPR,
    TAB,
    XML_SPACE,
    R,
    T,
    make,
    w,
)

_CONTAINERS = frozenset({INS, MOVE_TO})
_MARKS = (INS, DEL, MOVE_FROM, MOVE_TO)


class Stamp:
    """Author, date and the next free w:id for everything one apply writes."""

    def __init__(self, author: str, date: datetime | None, next_id: int) -> None:
        when = date or datetime.now(UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        self.author = author
        self.date = when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._next = next_id

    def new_id(self) -> str:
        value = self._next
        self._next += 1
        return str(value)

    def mark(self, tag: str) -> etree._Element:
        return make(tag, id=self.new_id(), author=self.author, date=self.date)


def _preserve(node: etree._Element) -> None:
    node.set(XML_SPACE, "preserve")


def _split(run: etree._Element, node: etree._Element, offset: int) -> etree._Element:
    """Move everything from `node[offset]` on into a new run after `run`; return the run starting there."""
    children = list(run)
    index = children.index(node)
    before = [c for c in children[:index] if c.tag != RPR]
    if offset == 0 and not before:
        return run
    right = etree.Element(R, attrib=dict(run.attrib))
    props = run.find(RPR)
    if props is not None:
        right.append(copy.deepcopy(props))
    if offset > 0:
        text = node.text or ""
        node.text = text[:offset]
        _preserve(node)
        tail = etree.SubElement(right, T)
        tail.text = text[offset:]
        _preserve(tail)
        moving = children[index + 1 :]
    else:
        moving = children[index:]
    for child in moving:
        right.append(child)
    run.addnext(right)
    return right


def run_starting_at(atom: Atom) -> etree._Element:
    return _split(atom.run, atom.node, atom.offset)


def run_ending_at(atom: Atom) -> etree._Element:
    """Split after the atom so its run ends there; the run keeps its element."""
    if atom.node.tag == T and atom.offset + 1 < len(atom.node.text or ""):
        _split(atom.run, atom.node, atom.offset + 1)
        return atom.run
    following = atom.node.getnext()
    if following is not None:
        _split(atom.run, following, 0)
    return atom.run


def isolate(first: Atom, last: Atom) -> tuple[etree._Element, etree._Element]:
    """Split runs so the text from `first` to `last` is exactly whole runs; returns the end runs."""
    same = first.run is last.run
    end = run_ending_at(last)
    start = run_starting_at(first)
    return start, start if same else end


def runs_between(
    runs: list[etree._Element], start: etree._Element, end: etree._Element
) -> list[etree._Element]:
    """The live runs from start to end in reading order, re-read after splitting."""
    return runs[runs.index(start) : runs.index(end) + 1]


def delete_runs(runs: Iterable[etree._Element], stamp: Stamp) -> list[etree._Element]:
    """Wrap runs in w:del, one per group of adjacent siblings; returns the w:del elements."""
    groups: list[list[etree._Element]] = []
    for run in runs:
        if groups and groups[-1][-1].getnext() is run:
            groups[-1].append(run)
        else:
            groups.append([run])
    wrappers = []
    for group in groups:
        wrapper = stamp.mark(DEL)
        group[0].addprevious(wrapper)
        for run in group:
            wrapper.append(run)
            for node in run:
                if node.tag == T:
                    node.tag = DEL_TEXT
                elif node.tag == INSTR:
                    node.tag = DEL_INSTR
        wrappers.append(wrapper)
    return wrappers


def new_run(text: str, props: etree._Element | None) -> etree._Element:
    """A run of plain text in the given run properties; tabs become w:tab."""
    run = etree.Element(R)
    if props is not None:
        kept = copy.deepcopy(props)
        for change in kept.findall(w("rPrChange")):
            kept.remove(change)
        run.append(kept)
    for index, piece in enumerate(text.split("\t")):
        if index:
            etree.SubElement(run, TAB)
        if piece:
            node = etree.SubElement(run, T)
            node.text = piece
            _preserve(node)
    return run


def insertion(text: str, props: etree._Element | None, stamp: Stamp) -> etree._Element:
    wrapper = stamp.mark(INS)
    wrapper.append(new_run(text, props))
    return wrapper


def _split_container(
    container: etree._Element, after: etree._Element, stamp: Stamp
) -> None:
    """Split another change's w:ins after a child, so new markup can sit between the halves."""
    rest = etree.Element(container.tag, attrib=dict(container.attrib))
    rest.set(w("id"), stamp.new_id())
    for child in list(after.itersiblings()):
        rest.append(child)
    container.addnext(rest)


def place_after(anchor: etree._Element, new: etree._Element, stamp: Stamp) -> None:
    """Put `new` right after `anchor`, outside any insertion or move it sits in."""
    parent = anchor.getparent()
    if parent.tag in _CONTAINERS:
        if anchor.getnext() is not None:
            _split_container(parent, anchor, stamp)
        place_after(parent, new, stamp)
        return
    anchor.addnext(new)


def place_before(anchor: etree._Element, new: etree._Element, stamp: Stamp) -> None:
    parent = anchor.getparent()
    if parent.tag in _CONTAINERS:
        previous = anchor.getprevious()
        if previous is None:
            place_before(parent, new, stamp)
            return
        _split_container(parent, previous, stamp)
        place_before(anchor.getparent(), new, stamp)
        return
    anchor.addprevious(new)


def mark_paragraph(paragraph: etree._Element, tag: str, stamp: Stamp) -> None:
    """Track the paragraph mark itself as inserted or deleted (w:pPr/w:rPr/w:ins|w:del)."""
    props = paragraph.find(PPR)
    if props is None:
        props = etree.Element(PPR)
        paragraph.insert(0, props)
    mark_props = props.find(RPR)
    if mark_props is None:
        mark_props = etree.Element(RPR)
        later = [c for c in props if c.tag in (SECTPR, w("pPrChange"))]
        if later:
            later[0].addprevious(mark_props)
        else:
            props.append(mark_props)
    # ins, del, moveFrom, moveTo lead CT_ParaRPr in that order.
    position = sum(1 for c in mark_props if c.tag in _MARKS[: _MARKS.index(tag)])
    mark_props.insert(position, stamp.mark(tag))


def paragraph_mark(paragraph: etree._Element, tag: str) -> etree._Element | None:
    return paragraph.find(f"{PPR}/{RPR}/{tag}")


def copied_paragraph_props(paragraph: etree._Element) -> etree._Element | None:
    """The anchor's paragraph properties without its section break or change history."""
    props = paragraph.find(PPR)
    if props is None:
        return None
    kept = copy.deepcopy(props)
    for tag in (SECTPR, w("pPrChange")):
        for found in kept.findall(tag):
            kept.remove(found)
    mark_props = kept.find(RPR)
    if mark_props is not None:
        for found in [c for c in mark_props if c.tag in (*_MARKS, w("rPrChange"))]:
            mark_props.remove(found)
    return kept
