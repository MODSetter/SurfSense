"""Whether a quoted passage is really in a source: the check behind "no answer without a source".

Compared word for word after folding case, punctuation, quotes and Markdown marks, so a
quote copied from Word's text matches Docling's Markdown of it; digits and negations stay
words, so "72 hours" never matches "24 hours" and "not encrypted" never matches "encrypted".
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise, product

# "A ... B": each part must be in the same source, so a quote may skip words but not invent them.
_ELLIPSIS = re.compile(r"\s*(?:\.\s*\.\s*\.|…|\[\.\.\.\])\s*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# [text](target) and ![text](target) read as their text. A model that copies a sentence
# holding a link drops the target or mangles it: Qwen's quotes were not found 29% of the time
# when the deciding sentence held a link, against 8% otherwise. Bounded, so a line of many
# brackets costs a linear scan rather than a quadratic one. Its text may wrap a line: a
# source is folded whole, and the text keeps its line breaks.
_LINK = re.compile(r"!?\[([^\]]{0,300})\]\([^)\s]{0,1000}(?:\s+\"[^\"\n]{0,300}\")?\)")
# Words that turn a claim around: the words a "..." skips may hold none, and a hint may not
# add or drop one. "t" is what "isn't" and "don't" leave once their apostrophe falls away.
_NEGATIONS = frozenset(
    {
        "not",
        "no",
        "never",
        "none",
        "nor",
        "neither",
        "nothing",
        "nobody",
        "without",
        "cannot",
        "except",
        "unless",
        "t",
    }
)
# A line that stands alone in a paragraph: a list item, a table row, a heading or a quote.
_OWN_LINE = re.compile(r"\s*(?:[-*+|#>]|\d+[.)]\s)")
# Parts of a quote joined by "..." must sit this close, so distant fragments never make one claim.
WINDOW_WORDS = 300
# A part this short could match almost anywhere.
MIN_PART_WORDS = 3
# Places tried per part when a quote has several: the nearest first.
_TRIED = 20


@dataclass(frozen=True)
class Found:
    source: int  # index of the source text the quote was found in
    line: int  # 1-based line where it starts
    end_line: int = 0  # the line where its last part ends, or 0 when it is the first


def words(text: str) -> list[str]:
    """Letters and digits in runs, as a reader sees the text: Markdown's underscores and every
    mark fall away, and a link reads as its text."""
    folded = unicodedata.normalize("NFKC", _LINK.sub(r"\1", text)).casefold()
    return re.findall(r"[^\W_]+", folded)


def forget() -> None:
    """Let go of the sources a run read, so a long-lived worker does not keep every library."""
    _indexed.cache_clear()
    _sentences.cache_clear()


def nearest_sentence(quote: str, sources: list[str], least: float = 0.6) -> str | None:
    """The source sentence closest to a quote that is not there, as the source writes it, when it
    shares at least `least` of the longer one's words and the same negations and numbers: what a
    model that copied loosely most likely meant, and never the claim turned around. Small models
    paraphrase a real sentence for about one quoted answer in ten; shown it, they can copy it,
    and the copy is checked like any other."""
    quoted = words(quote)
    if len(quoted) < MIN_PART_WORDS:
        return None
    wanted, turning = Counter(quoted), _turning(quoted)
    best, best_share = None, least
    for text in sources:
        for sentence, bag, size, its_turning in _sentences(text):
            if its_turning != turning:
                continue
            share = sum((wanted & bag).values()) / max(len(quoted), size)
            if share >= best_share and (best is None or share > best_share):
                best, best_share = sentence, share
    return best


def _turning(found: list[str]) -> frozenset[str]:
    """The negations and numbers among some words."""
    return frozenset(w for w in found if w in _NEGATIONS or w.isdigit())


@lru_cache(maxsize=256)
def _sentences(text: str) -> tuple[tuple[str, Counter, int, frozenset[str]], ...]:
    """The text's sentences, a paragraph's lines joined first, since a PDF's text layer breaks
    its lines mid-sentence."""
    found = []
    for paragraph in _paragraphs(text):
        for sentence in _SENTENCE_END.split(paragraph):
            said = words(sentence)
            if said:
                found.append(
                    (sentence.strip(), Counter(said), len(said), _turning(said))
                )
    return tuple(found)


def _paragraphs(text: str) -> list[str]:
    """Runs of lines between blank ones, a list item, table row or heading starting its own."""
    paragraphs: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if not line.strip() or (_OWN_LINE.match(line) and current):
            if current:
                paragraphs.append(" ".join(current))
            current = []
        if line.strip():
            current.append(line.strip())
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


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
        found = _all_parts(parts, sources[index])
        if found is not None:
            return Found(index, *found)
    return None


def _all_parts(parts: list[list[str]], text: str) -> tuple[int, int] | None:
    """The line of the first part and of the last word a part ends on, where all the parts sit
    within WINDOW_WORDS of each other, in any order, and the words a "..." skips between them
    hold no negation: "data is ... encrypted at rest" is not in "data is not encrypted at
    rest"."""
    joined, lines, starts, tokens = _indexed(text)
    found = [_word_positions(joined, starts, " ".join(part)) for part in parts]
    if not all(found):
        return None
    for first in found[0]:
        near = [
            sorted(
                (p for p in positions if abs(p - first) <= WINDOW_WORDS),
                key=lambda p: abs(p - first),
            )[:_TRIED]
            for positions in found[1:]
        ]
        for chosen in product(*near):
            spans = sorted(
                [(first, len(parts[0]))]
                + [(at, len(part)) for at, part in zip(chosen, parts[1:], strict=True)]
            )
            if spans[-1][0] - spans[0][0] > WINDOW_WORDS:
                continue
            if not any(
                token in _NEGATIONS
                for (at, size), (following, _) in pairwise(spans)
                for token in tokens[at + size : following]
            ):
                last = max(at + size for at, size in spans) - 1
                return lines[first], lines[last] if len(parts) > 1 else 0
    return None


def _word_positions(haystack: str, starts: tuple[int, ...], needle: str) -> list[int]:
    """Where the needle starts, as word numbers, at every whole-word match."""
    positions = []
    start = 0
    while (at := haystack.find(needle, start)) >= 0:
        end = at + len(needle)
        if (at == 0 or haystack[at - 1] == " ") and (
            end == len(haystack) or haystack[end] == " "
        ):
            positions.append(bisect_left(starts, at))
        start = at + 1
    return positions


@lru_cache(maxsize=256)
def _indexed(
    text: str,
) -> tuple[str, tuple[int, ...], tuple[int, ...], tuple[str, ...]]:
    """The text's words joined by single spaces, each word's line and offset in that string,
    and the words: a run checks every quote against the same sources, so each is read once."""
    tokens: list[str] = []
    lines: list[int] = []
    # Links folded over the whole text first, so one that wraps a line still reads as its text.
    for number, line in enumerate(_LINK.sub(r"\1", text).splitlines(), start=1):
        for word in words(line):
            tokens.append(word)
            lines.append(number)
    starts: list[int] = []
    offset = 0
    for token in tokens:
        starts.append(offset)
        offset += len(token) + 1
    return " ".join(tokens), tuple(lines), tuple(starts), tuple(tokens)
