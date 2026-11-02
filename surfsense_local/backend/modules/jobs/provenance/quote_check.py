"""Whether a quoted passage is really in a source: the check behind "no answer without a source".

Compared word for word after folding case, punctuation, quotes and Markdown marks, so a
quote copied from Word's text matches Docling's Markdown of it; digits and negations stay
words, so "72 hours" never matches "24 hours" and "not encrypted" never matches "encrypted".
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

# "A ... B": each part must be in the same source, so a quote may skip words but not invent them.
_ELLIPSIS = re.compile(r"\s*(?:\.\s*\.\s*\.|…|\[\.\.\.\])\s*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# [text](target) and ![text](target) read as their text. A model that copies a sentence
# holding a link drops the target or mangles it: Qwen's quotes were not found 29% of the time
# when the deciding sentence held a link, against 8% otherwise.
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)\s]*(?:\s+\"[^\"]*\")?\)")
_BARE_URL = re.compile(r"<?\bhttps?://[^\s>)]+>?")
# Parts of a quote joined by "..." must sit this close, so distant fragments never make one claim.
WINDOW_WORDS = 300
# A part this short could match almost anywhere.
MIN_PART_WORDS = 3


@dataclass(frozen=True)
class Found:
    source: int  # index of the source text the quote was found in
    line: int  # 1-based line where it starts


def words(text: str) -> list[str]:
    """Letters and digits in runs, as a reader sees the text: Markdown's underscores and every
    mark fall away, a link reads as its text and a bare address not at all."""
    rendered = _BARE_URL.sub(" ", _LINK.sub(r"\1", text))
    folded = unicodedata.normalize("NFKC", rendered).casefold()
    return re.findall(r"[^\W_]+", folded)


def nearest_sentence(quote: str, sources: list[str], least: float = 0.6) -> str | None:
    """The source sentence closest to a quote that is not there, as the source writes it, when it
    shares at least `least` of the longer one's words: what a model that copied loosely most
    likely meant. Small models paraphrase a real sentence for about one quoted answer in ten;
    shown it, they can copy it, and the copy is checked like any other."""
    wanted = Counter(words(quote))
    if sum(wanted.values()) < MIN_PART_WORDS:
        return None
    best, best_share = None, least
    for text in sources:
        for sentence, bag, size in _sentences(text):
            shared = sum((wanted & bag).values())
            share = shared / max(sum(wanted.values()), size)
            if share >= best_share and (best is None or share > best_share):
                best, best_share = sentence, share
    return best


@lru_cache(maxsize=256)
def _sentences(text: str) -> tuple[tuple[str, Counter, int], ...]:
    found = []
    for line in text.splitlines():
        for sentence in _SENTENCE_END.split(line.strip()):
            bag = Counter(words(sentence))
            if bag:
                found.append((sentence.strip(), bag, sum(bag.values())))
    return tuple(found)


def find_quote(
    quote: str, sources: list[str], prefer: int | None = None
) -> Found | None:
    """The source holding every part of the quote, the preferred one first; None if none does."""
    parts = [words(part) for part in _ELLIPSIS.split(quote) if part.strip()]
    parts = [part for part in parts if part]
    if not parts or any(len(part) < MIN_PART_WORDS for part in parts):
        return None
    order = list(range(len(sources)))
    if prefer is not None and 0 <= prefer < len(sources):
        order.remove(prefer)
        order.insert(0, prefer)
    for index in order:
        line = _all_parts(parts, sources[index])
        if line is not None:
            return Found(index, line)
    return None


def _all_parts(parts: list[list[str]], text: str) -> int | None:
    """The line of the first part, where every other part is within WINDOW_WORDS of it, in any order."""
    joined, lines = _indexed(text)
    found = [_word_positions(joined, " ".join(part)) for part in parts]
    if not all(found):
        return None
    for first in found[0]:
        if all(
            any(abs(other - first) <= WINDOW_WORDS for other in positions)
            for positions in found[1:]
        ):
            return lines[first]
    return None


def _word_positions(haystack: str, needle: str) -> list[int]:
    """Where the needle starts, as word numbers, at every whole-word match."""
    positions = []
    start = 0
    while (at := haystack.find(needle, start)) >= 0:
        end = at + len(needle)
        if (at == 0 or haystack[at - 1] == " ") and (
            end == len(haystack) or haystack[end] == " "
        ):
            positions.append(haystack.count(" ", 0, at))
        start = at + 1
    return positions


@lru_cache(maxsize=256)
def _indexed(text: str) -> tuple[str, tuple[int, ...]]:
    """The text's words joined by single spaces, and each word's line: a run checks every
    quote against the same sources, so each is read once."""
    tokens: list[str] = []
    lines: list[int] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for word in words(line):
            tokens.append(word)
            lines.append(number)
    return " ".join(tokens), tuple(lines)
