"""Finding a quote in a slide's DrawingML paragraphs and replacing it in place
(ECMA-376 Part 1, 21.1.2.2: a:p holds a:r runs, a:br breaks and a:fld fields).

A quote never crosses paragraphs. Inside one run the run keeps its
formatting; across runs the replacement takes the first run's.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from lxml import etree

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
# Office reads mc:Choice; the fallback copy of the same text is for older readers.
_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
_RUN, _BREAK, _FIELD = f"{{{A}}}r", f"{{{A}}}br", f"{{{A}}}fld"
# Proofing and editing marks that do not change how a run looks.
_INVISIBLE = {"lang", "altLang", "dirty", "err", "noProof", "smtClean", "smtId"}


@dataclass
class _Piece:
    element: etree._Element
    start: int
    text: str


@dataclass
class Match:
    paragraph: etree._Element
    pieces: list[_Piece]
    start: int
    end: int

    @property
    def touched(self) -> list[_Piece]:
        return [
            p
            for p in self.pieces
            if p.start < self.end and p.start + len(p.text) > self.start
        ]

    @property
    def in_field(self) -> bool:
        return any(p.element.tag == _FIELD for p in self.touched)

    @property
    def merges_formatting(self) -> bool:
        runs = [p for p in self.touched if p.element.tag == _RUN]
        return len({_look(p.element) for p in runs}) > 1

    @property
    def text(self) -> str:
        return "".join(p.text for p in self.pieces)[self.start : self.end]


@dataclass(frozen=True)
class Search:
    matches: list[Match]
    crosses_paragraphs: bool


def normalize(text: str) -> str:
    """Whitespace runs as one space; a quote's leading or trailing space still counts."""
    return re.sub(r"\s+", " ", text)


def find(container: etree._Element, quote: str) -> Search:
    """Every place the quote occurs, whitespace runs counting as one space."""
    wanted = normalize(quote)
    matches: list[Match] = []
    bodies: dict[etree._Element, list[str]] = {}
    for paragraph in container.iter(f"{{{A}}}p"):
        if any(ancestor.tag == _FALLBACK for ancestor in paragraph.iterancestors()):
            continue
        pieces = _pieces(paragraph)
        raw = "".join(p.text for p in pieces)
        squeezed, spans = _squeeze(raw)
        bodies.setdefault(paragraph.getparent(), []).append(squeezed)
        at = squeezed.find(wanted)
        while at != -1:
            start = spans[at][0]
            end = spans[at + len(wanted) - 1][1]
            matches.append(Match(paragraph, pieces, start, end))
            at = squeezed.find(wanted, at + 1)
    crosses = not matches and any(
        wanted in normalize(" ".join(texts)) for texts in bodies.values()
    )
    return Search(matches, crosses)


def replace(match: Match, text: str) -> None:
    touched = [p for p in match.touched if p.element.tag == _RUN]
    first, last = touched[0], touched[-1]
    head = first.text[: max(0, match.start - first.start)]
    tail = last.text[max(0, match.end - last.start) :]
    lines = (
        text.replace("\r\n", "\n").replace("\r", "\n").replace("\v", "\n").split("\n")
    )

    for piece in match.touched:
        if piece is not first and piece is not last:
            piece.element.getparent().remove(piece.element)
    if last is not first:
        if tail:
            _set_text(last.element, tail)
        else:
            last.element.getparent().remove(last.element)
        tail = ""

    _set_text(first.element, head + lines[0] + (tail if len(lines) == 1 else ""))
    anchor = first.element
    for number, line in enumerate(lines[1:], start=1):
        anchor.addnext(_break_like(first.element))
        anchor = anchor.getnext()
        run = copy.deepcopy(first.element)
        _set_text(run, line + (tail if number == len(lines) - 1 else ""))
        anchor.addnext(run)
        anchor = run
    if not (head + lines[0]) and len(lines) == 1 and not tail:
        first.element.getparent().remove(first.element)


def _pieces(paragraph: etree._Element) -> list[_Piece]:
    pieces, at = [], 0
    for child in paragraph:
        if child.tag in (_RUN, _FIELD):
            text = child.findtext(f"{{{A}}}t") or ""
        elif child.tag == _BREAK:
            text = "\n"
        else:
            continue
        pieces.append(_Piece(child, at, text))
        at += len(text)
    return pieces


def _squeeze(raw: str) -> tuple[str, list[tuple[int, int]]]:
    """The text with whitespace runs as one space, and each character's span in the raw text."""
    out: list[str] = []
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(raw):
        if raw[index].isspace():
            end = index
            while end < len(raw) and raw[end].isspace():
                end += 1
            out.append(" ")
            spans.append((index, end))
            index = end
        else:
            out.append(raw[index])
            spans.append((index, index + 1))
            index += 1
    return "".join(out), spans


def _set_text(run: etree._Element, text: str) -> None:
    node = run.find(f"{{{A}}}t")
    if node is None:
        node = etree.SubElement(run, f"{{{A}}}t")
    node.text = text


def _break_like(run: etree._Element) -> etree._Element:
    line_break = etree.Element(_BREAK)
    properties = run.find(f"{{{A}}}rPr")
    if properties is not None:
        line_break.append(copy.deepcopy(properties))
    return line_break


def _look(run: etree._Element) -> bytes:
    properties = run.find(f"{{{A}}}rPr")
    if properties is None:
        return b""
    visible = copy.deepcopy(properties)
    for name in _INVISIBLE:
        visible.attrib.pop(name, None)
    return etree.tostring(visible, method="c14n")
