"""Blank lines where a page's paragraphs end, found from where its lines sit.

pdfium ends every line alike, so the chunker could cut a long page only at an
arbitrary line: it cut a paper's Table 1 from its caption and header.
"""

import ctypes
import re
import statistics
from typing import Any

import pypdfium2.raw as pdfium_c

# A gap this many times the line spacing on both sides of it ends a paragraph. Word's
# 8 pt after a paragraph and LaTeX's parskip measured 1.49 to 1.5; 1.2 to 1.4 retrieved
# alike on the gate's corpora.
PARAGRAPH_GAP = 1.3
# Lines nearer than this share of the page's spacing are one line split at a subscript.
SAME_LINE = 0.5

_CAPTION = re.compile(
    r"\s*(?:table|figure|fig\.|exhibit)\s+\d+(?:\.\d+)*\s*[.:\N{EN DASH}\N{EM DASH}-]",
    re.IGNORECASE,
)
_LINE_END = "\r\n"


def with_paragraph_breaks(textpage: Any, text: str) -> str:
    """The page's get_text_range() with "\\n" added after each line end that closes a
    paragraph, and nothing else changed. Hold shared.pdfium.lock."""
    lines = text.split(_LINE_END)
    gaps = _gaps(textpage, text, lines)
    # A point or less: pdfium split one line, as at a superscript.
    spacings = [gap for gap in gaps if gap is not None and gap > 1.0]
    if len(spacings) < 2:
        return text
    usual = statistics.median(spacings)
    breaks = _gap_breaks(gaps, usual)
    _place_captions(lines, gaps, breaks)
    _join_lone_lines(breaks)
    out = [lines[0]]
    for index in range(1, len(lines)):
        out.append(_LINE_END)
        if index in breaks and lines[index - 1].strip() and lines[index].strip():
            out.append("\n")
        out.append(lines[index])
    return "".join(out)


def _gaps(textpage: Any, text: str, lines: list[str]) -> list[float | None]:
    """How far each line's baseline sits below the line before it; None where unknown."""
    baselines = _Baselines(textpage, text)
    tops: list[float | None] = []
    bottoms: list[float | None] = []
    start = 0
    for line in lines:
        first, last = _ends(line)
        top = None if first is None else baselines.at(start + first)
        # The last letter, not the first: a word pdfium joined at a hyphen carries the
        # line on to the next visual line.
        bottom = top if last == first else baselines.at(start + last)
        tops.append(top)
        bottoms.append(bottom)
        start += len(line) + len(_LINE_END)
    gaps: list[float | None] = [None]
    for above, below in zip(bottoms, tops[1:], strict=False):
        gaps.append(None if above is None or below is None else above - below)
    return gaps


def _gap_breaks(gaps: list[float | None], usual: float) -> set[int]:
    """The lines that start a paragraph. Measured against the wider spacing beside the
    gap, a table's evenly spaced rows and the rule under its header stay one block."""
    breaks = set()
    for index, gap in enumerate(gaps):
        if gap is None:
            continue
        if gap < -PARAGRAPH_GAP * usual:  # up to the next column or a box above
            breaks.add(index)
        elif gap > SAME_LINE * usual:
            beside = max(
                _spacing(gaps, index - 1, usual), _spacing(gaps, index + 1, usual)
            )
            if gap > PARAGRAPH_GAP * beside:
                breaks.add(index)
    return breaks


def _spacing(gaps: list[float | None], index: int, usual: float) -> float:
    gap = gaps[index] if 0 <= index < len(gaps) else None
    return gap if gap is not None and gap > SAME_LINE * usual else usual


def _place_captions(
    lines: list[str], gaps: list[float | None], breaks: set[int]
) -> None:
    """A caption goes with the nearer block: the table under it in a paper, the one
    above it in a spec. Left to the gaps, a paper's caption was cut from its table."""
    for index, line in enumerate(lines):
        if not index or not _CAPTION.match(line):
            continue
        end = next((n for n in range(index + 1, len(lines)) if n in breaks), None)
        above = gaps[index]
        below = gaps[end] if end is not None else None
        if above is not None and above > 0 and (below is None or not 0 < below < above):
            breaks.discard(index)
        else:
            breaks.add(index)
            if end is not None:
                breaks.discard(end)


def _join_lone_lines(breaks: set[int]) -> None:
    """A line on its own, such as a heading, goes with the block after it: on its own
    the chunker could leave it at the end of the passage before."""
    starts = sorted(breaks)
    for before, start in zip([0, *starts], starts, strict=False):
        if start - before == 1:
            breaks.discard(start)


def _ends(line: str) -> tuple[int | None, int | None]:
    """The line's first and last letter or digit, which sit on its baseline, or else
    its first visible character."""
    first = next((n for n, char in enumerate(line) if char.isalnum()), None)
    if first is None:
        first = next((n for n, char in enumerate(line) if not char.isspace()), None)
        return first, first
    last = next(n for n in range(len(line) - 1, first - 1, -1) if line[n].isalnum())
    return first, last


class _Baselines:
    """Where a character of the page's text sits. On Windows pdfium's text index
    counts UTF-16 units, so a character past U+FFFF moves every later index by one;
    elsewhere it may count code points. Both are tried, and the character checked."""

    def __init__(self, textpage: Any, text: str) -> None:
        self._textpage = textpage
        self._text = text
        self._wide_before: list[int] | None = None
        if any(ord(char) > 0xFFFF for char in text):
            self._wide_before = []
            wide = 0
            for char in text:
                self._wide_before.append(wide)
                wide += ord(char) > 0xFFFF
        self._x = ctypes.c_double()
        self._y = ctypes.c_double()

    def at(self, index: int) -> float | None:
        code = ord(self._text[index])
        readings = [index]
        if self._wide_before is not None and self._wide_before[index]:
            readings.insert(0, index + self._wide_before[index])
        for text_index in readings:
            char = pdfium_c.FPDFText_GetCharIndexFromTextIndex(
                self._textpage, text_index
            )
            if char < 0 or not _same(
                pdfium_c.FPDFText_GetUnicode(self._textpage, char), code
            ):
                continue
            if pdfium_c.FPDFText_GetCharOrigin(self._textpage, char, self._x, self._y):
                return self._y.value
        return None


def _same(unicode: int, code: int) -> bool:
    # Past U+FFFF, pdfium may hold the character as its two UTF-16 halves.
    high = 0xD800 + ((code - 0x10000) >> 10)
    return unicode == code or (code > 0xFFFF and unicode == high)
