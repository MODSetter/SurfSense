"""Whether a quoted passage is really in a source: the check behind "no answer without a source".

Compared word for word after folding case, punctuation, quotes and Markdown marks, so a
quote copied from Word's text matches Docling's Markdown of it; digits and negations stay
words, so "72 hours" never matches "24 hours" and "not encrypted" never matches "encrypted".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# "A ... B": each part must be in the same source, so a quote may skip words but not invent them.
_ELLIPSIS = re.compile(r"\s*(?:\.\s*\.\s*\.|…|\[\.\.\.\])\s*")
# A part this short could match almost anywhere.
MIN_PART_WORDS = 3


@dataclass(frozen=True)
class Found:
    source: int  # index of the source text the quote was found in
    line: int  # 1-based line where it starts


def words(text: str) -> list[str]:
    """Letters and digits in runs; Markdown's underscores and every mark fall away."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"[^\W_]+", folded)


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
    tokens, lines = _tokens_with_lines(text)
    joined = " ".join(tokens)
    first_line = None
    for part in parts:
        needle = " ".join(part)
        at = _word_boundary_find(joined, needle)
        if at < 0:
            return None
        if first_line is None:
            first_line = lines[joined.count(" ", 0, at)]
    return first_line


def _word_boundary_find(haystack: str, needle: str) -> int:
    start = 0
    while (at := haystack.find(needle, start)) >= 0:
        end = at + len(needle)
        if (at == 0 or haystack[at - 1] == " ") and (
            end == len(haystack) or haystack[end] == " "
        ):
            return at
        start = at + 1
    return -1


def _tokens_with_lines(text: str) -> tuple[list[str], list[int]]:
    tokens: list[str] = []
    lines: list[int] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for word in words(line):
            tokens.append(word)
            lines.append(number)
    return tokens, lines
