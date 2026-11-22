"""One page as OCR read it, and whether its text can stand.

Every reader gives the same shape: lines of words with pixel boxes, top-left
origin. Tables stay with OCR: on the corpus's real scans RapidOCR's rows answered
better than Docling's Markdown (Haiku, 0.79 of 374 DocVQA questions against 0.60),
whose layout step drops text. Docling runs the same OCR inside, so only a page
OCR could not read at all is worth its try.
"""

import re
import statistics
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from worker.ingestion.pdf_text_layer.page_triage import GARBLED_ALNUM

# Fewer characters than this say nothing on their own: a stamp, a page number,
# or handwriting the engine could not read.
MIN_CHARS = 20
# Share of dark pixels below which a page with no text is blank paper.
BLANK_INK = 0.01
# A gap above a line this many median line pitches starts a paragraph, the
# text layer's own factor.
PARAGRAPH_PITCH = 1.3
# An engine's own confidence, a character's share of the page apiece: RapidOCR's
# was 0.85 or more on every upright real page of the corpus's forms, receipts,
# books and DocVQA (median 0.98-0.99), and 0.56 to 0.79 on sideways photos.
LOW_CONFIDENCE = 0.8
# With no confidence, the share of characters in words of 3 letters or more: no
# upright real page of the corpus fell below 0.32 as Vision read it, nor 0.36 as
# Windows OCR did; read sideways, pages gave 0 to 0.22, "O 00 o c".
WORD_SHARE = 0.3
# Characters a token, on average, with no confidence: 2.8 to 5.5 on real pages,
# 1.0 to 1.8 on a page read sideways, its letters' strokes one by one.
SIDEWAYS_TOKEN = 2.2
# Most of its text in boxes standing on end: a page turned a quarter round, which
# an engine may read confidently, every line across one row.
SIDEWAYS_VERTICAL = 0.5
_WORD = re.compile(r"[^\W\d_]{3,}")


@dataclass(frozen=True)
class Word:
    text: str
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Line:
    text: str
    words: tuple[Word, ...] = ()

    @property
    def box(self) -> tuple[float, float, float, float]:
        """x, y, right, bottom over its words."""
        if not self.words:
            return (0.0, 0.0, 0.0, 0.0)
        return (
            min(word.x for word in self.words),
            min(word.y for word in self.words),
            max(word.x + word.w for word in self.words),
            max(word.y + word.h for word in self.words),
        )


class PageVerdict(StrEnum):
    TEXT = "text"
    BLANK = "blank"
    TOO_LITTLE = "too little text"
    GARBLED = "garbled"


# What OCR's text stands for; a garbled page goes to Docling.
KEPT = frozenset({PageVerdict.TEXT, PageVerdict.BLANK, PageVerdict.TOO_LITTLE})


@dataclass(frozen=True)
class OcrPage:
    width: int
    height: int
    lines: tuple[Line, ...] = ()
    # Share of dark pixels, to tell blank paper from an unreadable page.
    ink: float = 0.0
    language: str | None = None
    # The engine's own, when it gives one: RapidOCR's; Vision's is not used.
    confidence: float | None = None
    # Share of its characters in boxes standing on end.
    vertical: float = 0.0

    @property
    def chars(self) -> int:
        return sum(len(line.text.strip()) for line in self.lines)

    def text(self) -> str:
        """Lines in reading order: a hyphen at a line end joins the next line's
        lowercase word, and a wide gap above a line starts a paragraph."""
        lines = [line for line in self.lines if line.text.strip()]
        if not lines:
            return ""
        breaks = _paragraph_starts(lines)
        out: list[str] = [lines[0].text.strip()]
        for index, line in enumerate(lines[1:], start=1):
            text = line.text.strip()
            if index in breaks:
                out.append("\n\n" + text)
            elif _hyphenated(out[-1]) and text[:1].islower():
                out[-1] = out[-1][:-1] + text
            else:
                out.append("\n" + text)
        return "".join(out)

    def verdict(self) -> PageVerdict:
        if self.chars < MIN_CHARS:
            return PageVerdict.BLANK if self.ink < BLANK_INK else PageVerdict.TOO_LITTLE
        letters = "".join(line.text for line in self.lines)
        visible = [c for c in letters if not c.isspace()]
        if sum(c.isalnum() for c in visible) < GARBLED_ALNUM * len(visible):
            return PageVerdict.GARBLED
        if self.confidence is not None:
            # A page of figures has few words; the engine knows what it read.
            if self.confidence < LOW_CONFIDENCE:
                return PageVerdict.GARBLED
        elif self.word_share() < WORD_SHARE:
            return PageVerdict.GARBLED
        return PageVerdict.TEXT

    def word_share(self) -> float:
        text = " ".join(line.text for line in self.lines)
        visible = sum(not c.isspace() for c in text)
        return sum(len(m.group()) for m in _WORD.finditer(text)) / max(1, visible)

    def looks_sideways(self) -> bool:
        """Read turned a quarter or half round: its lines standing on end, the
        engine unsure of its text, or, with no confidence given, one or two
        characters a token."""
        tokens = " ".join(line.text for line in self.lines).split()
        if self.chars < MIN_CHARS or not tokens:
            # Little text says nothing of which way up: a photo, a signature.
            return False
        if self.vertical > SIDEWAYS_VERTICAL:
            return True
        if self.confidence is not None:
            return self.confidence < LOW_CONFIDENCE
        return sum(map(len, tokens)) / len(tokens) < SIDEWAYS_TOKEN


def _hyphenated(text: str) -> bool:
    return len(text) > 1 and text.endswith("-") and text[-2].isalpha()


def _paragraph_starts(lines: list[Line]) -> set[int]:
    """Indexes of lines with a wide gap above, or that jump back up: a new column."""
    tops = [line.box[1] for line in lines]
    pitches = [b - a for a, b in pairwise(tops) if b > a]
    if len(pitches) < 3 or not any(line.words for line in lines):
        return set()
    pitch = statistics.median(pitches)
    starts: set[int] = set()
    for index in range(1, len(lines)):
        step = tops[index] - tops[index - 1]
        if step < 0 or step > PARAGRAPH_PITCH * pitch:
            starts.add(index)
    return starts


def spread_words(text: str, x: float, y: float, w: float, h: float) -> tuple[Word, ...]:
    """A line an engine boxed whole, its words placed by character count."""
    if w <= 0 or not text:
        return ()
    per_char = w / len(text)
    words: list[Word] = []
    at = x
    for piece in text.split(" "):
        if piece:
            words.append(Word(piece, at, y, per_char * len(piece), h))
        at += per_char * (len(piece) + 1)
    return tuple(words)
