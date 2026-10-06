"""The body's paragraphs as they read now, and where a quote falls in them.

Inserted text reads, deleted text does not; tabs, breaks and no-break spaces are
whitespace, and any run of whitespace equals one space when matching.
"""

import re
from dataclasses import dataclass, field

from lxml import etree

from modules.artifacts.revised_copies.engines.word_xml import (
    FLD_CHAR,
    FLD_SIMPLE,
    NOT_TEXT,
    P,
    R,
    T,
    w,
)

_WHITESPACE = frozenset({w("tab"), w("ptab"), w("br"), w("cr")})
_HYPHEN = w("noBreakHyphen")


@dataclass(eq=False)
class Atom:
    """One character of running text and where it lives."""

    char: str
    run: etree._Element
    node: etree._Element
    offset: int
    in_field: bool


@dataclass(eq=False)
class Paragraph:
    element: etree._Element
    atoms: list[Atom] = field(default_factory=list)
    runs: list[etree._Element] = field(default_factory=list)
    text: str = ""
    # For each character of `text`, the first and last atom it stands for.
    spans: list[tuple[int, int]] = field(default_factory=list)


def paragraphs(body: etree._Element) -> list[Paragraph]:
    """Every paragraph of the body in reading order, tables and content controls included."""
    return _read(body)


def one_paragraph(element: etree._Element) -> Paragraph:
    """A single paragraph read on its own, as it reads now."""
    return _read([element])[0]


def _read(container) -> list[Paragraph]:
    found: list[Paragraph] = []
    depth = 0
    simple = 0

    def walk(element: etree._Element, current: Paragraph | None) -> None:
        nonlocal depth, simple
        for child in element:
            tag = child.tag
            if not isinstance(tag, str) or tag in NOT_TEXT:
                continue
            if tag == P:
                paragraph = Paragraph(child)
                found.append(paragraph)
                walk(child, paragraph)
            elif tag == R:
                if current is not None:
                    current.runs.append(child)
                    read_run(child, current)
            elif tag == FLD_SIMPLE:
                simple += 1
                walk(child, current)
                simple -= 1
            else:
                walk(child, current)

    def read_run(run: etree._Element, paragraph: Paragraph) -> None:
        nonlocal depth
        for node in run:
            tag = node.tag
            in_field = depth > 0 or simple > 0
            if tag == FLD_CHAR:
                kind = node.get(w("fldCharType"))
                if kind == "begin":
                    depth += 1
                elif kind == "end":
                    depth = max(0, depth - 1)
            elif tag == T:
                for offset, char in enumerate(node.text or ""):
                    paragraph.atoms.append(Atom(char, run, node, offset, in_field))
            elif tag in _WHITESPACE:
                paragraph.atoms.append(Atom(" ", run, node, 0, in_field))
            elif tag == _HYPHEN:
                paragraph.atoms.append(Atom("-", run, node, 0, in_field))

    walk(container, None)
    for paragraph in found:
        _normalize(paragraph)
    return found


def _normalize(paragraph: Paragraph) -> None:
    chars: list[str] = []
    for index, atom in enumerate(paragraph.atoms):
        if atom.char.isspace():
            if chars and chars[-1] == " ":
                paragraph.spans[-1] = (paragraph.spans[-1][0], index)
                continue
            chars.append(" ")
        else:
            chars.append(atom.char)
        paragraph.spans.append((index, index))
    paragraph.text = "".join(chars)


def normalize_quote(quote: str) -> str:
    return re.sub(r"\s+", " ", quote).strip()


@dataclass(frozen=True)
class Match:
    paragraph: Paragraph
    start: int
    end: int

    @property
    def atoms(self) -> list[Atom]:
        first = self.paragraph.spans[self.start][0]
        last = self.paragraph.spans[self.end - 1][1]
        return self.paragraph.atoms[first : last + 1]


class QuoteError(Exception):
    def __init__(self, code: str, values: dict[str, str | int], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.values = values
        self.message = message


def find(found: list[Paragraph], quote: str) -> Match:
    """The one place the quote reads in a single paragraph, or a QuoteError saying why not."""
    wanted = normalize_quote(quote)
    shown = quote if len(quote) <= 120 else quote[:117] + "..."
    matches = [
        Match(paragraph, start, start + len(wanted))
        for paragraph in found
        for start in _starts(paragraph.text, wanted)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise QuoteError(
            "QUOTE_AMBIGUOUS",
            {"quote": shown, "count": len(matches)},
            f"The quote occurs {len(matches)} times; quote more of the sentence so it occurs once.",
        )
    if wanted in " ".join(paragraph.text for paragraph in found):
        raise QuoteError(
            "QUOTE_CROSSES_PARAGRAPHS",
            {"quote": shown},
            "The quote spans two paragraphs; quote text from within one paragraph.",
        )
    raise QuoteError(
        "QUOTE_NOT_FOUND",
        {"quote": shown},
        "The quote is not in the document body as it reads now; copy it exactly, "
        "including case and punctuation.",
    )


def _starts(text: str, wanted: str) -> list[int]:
    starts = []
    at = text.find(wanted)
    while at != -1:
        starts.append(at)
        at = text.find(wanted, at + 1)
    return starts
