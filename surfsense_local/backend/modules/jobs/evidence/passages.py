"""A source's text cut into passages the model can cite by number, each knowing its lines and section."""

from __future__ import annotations

import re
from dataclasses import dataclass

# About a paragraph or two: long enough to hold a whole control, short enough to cite.
PASSAGE_CHARS = 900
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True)
class SourceText:
    document_id: int
    title: str
    text: str


@dataclass(frozen=True)
class Passage:
    source: int  # index into the job's sources
    title: str
    section: str  # the nearest heading above, or ""
    first_line: int
    last_line: int
    text: str


def passages_of(sources: list[SourceText]) -> list[Passage]:
    """Every source's passages in order: paragraphs joined up to PASSAGE_CHARS, never across a heading."""
    found: list[Passage] = []
    for index, source in enumerate(sources):
        section = ""
        block: list[str] = []
        start = 0
        for number, line in enumerate(source.text.splitlines(), start=1):
            heading = _HEADING.match(line)
            if heading:
                _close(found, index, source.title, section, block, start)
                block, section = [], heading.group(1).strip()
                block.append(line)
                start = number
                continue
            if not line.strip():
                if sum(len(b) for b in block) >= PASSAGE_CHARS:
                    _close(found, index, source.title, section, block, start)
                    block = []
                elif block:
                    block.append(line)
                continue
            # A PDF's text layer has no blank lines inside a page: cut at a line instead.
            if sum(len(b) for b in block) >= 2 * PASSAGE_CHARS:
                _close(found, index, source.title, section, block, start)
                block = []
            if not block:
                start = number
            block.append(line)
        _close(found, index, source.title, section, block, start)
    return found


def _close(
    found: list[Passage],
    index: int,
    title: str,
    section: str,
    block: list[str],
    start: int,
) -> None:
    while block and not block[-1].strip():
        block.pop()
    text = "\n".join(block).strip()
    if not text or _HEADING.fullmatch(text):
        return
    found.append(Passage(index, title, section, start, start + len(block) - 1, text))
