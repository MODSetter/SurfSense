"""Where a model's words fall in a clause as the engine reads it, and the anchor the engine finds
once.

The engine matches a quote exactly, inside one paragraph; a model copies curly quotes as straight
ones, dashes as hyphens and a clause's number as if it were text. Those are forgiven here, and
the anchor handed to the engine is always the clause's own characters.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from modules.jobs.word_clauses.contract import Clause

OPEN_SINGLE, CLOSE_SINGLE = chr(0x2018), chr(0x2019)
OPEN_DOUBLE, CLOSE_DOUBLE = chr(0x201C), chr(0x201D)
_SINGLES = "".join(map(chr, (0x2018, 0x2019, 0x201A, 0x201B, 0x2032))) + "`"
_DOUBLES = "".join(map(chr, (0x201C, 0x201D, 0x201E, 0x201F, 0x2033)))
_DASHES = "".join(map(chr, (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212)))
_MARKS = str.maketrans(
    {
        **dict.fromkeys(_SINGLES, "'"),
        **dict.fromkeys(_DOUBLES, '"'),
        **dict.fromkeys(_DASHES, "-"),
    }
)
_TRAILING = ".;:,"
# Words, runs of space and single marks, as the engine splits a change to mark only what differs.
_TOKENS = re.compile(r"\s+|\w+|[^\w\s]")
_WRAPPING = "\"'" + OPEN_DOUBLE + CLOSE_DOUBLE + OPEN_SINGLE + CLOSE_SINGLE
# Where a quote mark opens rather than closes.
_OPENS_AFTER = " ([{-" + chr(0x2014)
# Words an anchor starts from when nothing narrower is asked for: enough to be unique in most
# clauses, few enough to stay clear of the other edits in them.
SEED_WORDS = 8


def locate(clause: Clause, wanted: str) -> tuple[int, int] | None:
    """The span of the clause's text that `wanted` stands for, or None when it is not there."""
    text = clause.text
    for candidate in _candidates(wanted, clause.label):
        for fold in (_marks, _cased):
            at = fold(text).find(fold(candidate))
            if at >= 0:
                return at, at + len(candidate)
    return None


def typeset(new: str, old: str, contract_text: str) -> str:
    """The new text in the contract's own marks: what it shares with the old text at either end
    as the contract writes it, so only the words that differ are marked as changed, and straight
    quotes curled where the contract curls them."""
    folded_old, folded_new = _marks(old), _marks(new)
    shared = min(len(old), len(new))
    head = 0
    while head < shared and folded_old[head] == folded_new[head]:
        head += 1
    tail = 0
    while tail < shared - head and folded_old[-1 - tail] == folded_new[-1 - tail]:
        tail += 1
    middle = new[head : len(new) - tail]
    if OPEN_DOUBLE in contract_text or CLOSE_DOUBLE in contract_text:
        middle = _curled(middle, '"', OPEN_DOUBLE, CLOSE_DOUBLE)
    if CLOSE_SINGLE in contract_text:
        middle = _curled(middle, "'", OPEN_SINGLE, CLOSE_SINGLE)
    return old[:head] + middle + old[len(old) - tail :]


def _curled(text: str, straight: str, opening: str, closing: str) -> str:
    return re.sub(
        re.escape(straight),
        lambda m: (
            opening
            if m.start() == 0 or text[m.start() - 1] in _OPENS_AFTER
            else closing
        ),
        text,
    )


def touches_field(clause: Clause, start: int, end: int) -> bool:
    return any(position in clause.in_field for position in range(start, end))


def unique_anchor(
    clause: Clause,
    texts: list[str],
    start: int | None = None,
    end: int | None = None,
    blocked: tuple[tuple[int, int], ...] = (),
) -> tuple[int, int] | None:
    """The span, or the clause's first words, grown a word at a time on either side, clear of
    fields and of the `blocked` spans other changes to the clause make, until it occurs once
    among `texts`: the contract's clauses and the text its changes add. A span of no width,
    where text goes in, starts as the words either side, else the words after it or before it,
    whichever keeps clear of another change. None when it cannot be placed."""
    text = clause.text
    if start is None or end is None:
        start, end = _first_words(clause)
    elif start == end:
        seed = _seed_around(clause, start, blocked)
        if seed is None:
            return None
        start, end = seed
    start, end = _trimmed(text, start, end)
    if (
        end <= start
        or touches_field(clause, start, end)
        or _crosses(start, end, blocked)
    ):
        return None
    while True:
        if occurrences(text[start:end], texts) == 1:
            return start, end
        left = _word_before(clause, start)
        if _crosses(left, end, blocked):
            left = start
        right = _word_after(clause, end)
        if _crosses(left, right, blocked):
            right = end
        if (left, right) == (start, end):
            return None
        start, end = left, right


def narrowed(text: str, start: int, end: int, new: str) -> tuple[int, int, str]:
    """The span of `text` and its replacement cut to the words that differ, as the engine marks
    a change, so a change quoting most of a paragraph claims only the words it alters."""
    before, after = _TOKENS.findall(text[start:end]), _TOKENS.findall(new)
    shared = min(len(before), len(after))
    head = 0
    while head < shared and before[head] == after[head]:
        head += 1
    tail = 0
    while tail < shared - head and before[-1 - tail] == after[-1 - tail]:
        tail += 1
    cut_start = start + sum(len(token) for token in before[:head])
    cut_end = end - sum(len(token) for token in before[len(before) - tail :])
    return cut_start, cut_end, "".join(after[head : len(after) - tail])


def _seed_around(
    clause: Clause, point: int, blocked: tuple[tuple[int, int], ...]
) -> tuple[int, int] | None:
    """Words that hold the point where text goes in, clear of fields and other changes."""
    before, after = _word_before(clause, point), _word_after(clause, point)
    for seed in ((before, after), (point, after), (before, point)):
        start, end = _trimmed(clause.text, *seed)
        if (
            start < end
            and start <= point <= end
            and not touches_field(clause, start, end)
            and not _crosses(start, end, blocked)
        ):
            return start, end
    return None


def _crosses(start: int, end: int, blocked: tuple[tuple[int, int], ...]) -> bool:
    """Whether the span takes in a blocked span, or the point where another change puts text."""
    return any(
        (first < end and last > start) or (first == last and start < first < end)
        for first, last in blocked
    )


def occurrences(snippet: str, texts: Iterable[str], most: int = 2) -> int:
    """How many times the snippet reads in the texts, overlaps counted, up to `most`."""
    count = 0
    for text in texts:
        at = text.find(snippet)
        while at != -1:
            count += 1
            if count >= most:
                return count
            at = text.find(snippet, at + 1)
    return count


def _candidates(wanted: str, label: str) -> list[str]:
    plain = re.sub(r"\s+", " ", wanted).strip()
    found = [plain]
    if label and plain.startswith(label):
        found.append(plain[len(label) :].strip())
    for text in list(found):
        found.append(text.rstrip(_TRAILING).strip())
        found.append(text.strip(_WRAPPING).strip())
    return [c for c in dict.fromkeys(found) if c]


def _marks(text: str) -> str:
    return text.translate(_MARKS)


def _cased(text: str) -> str:
    """Lower case where it keeps a character one character, so positions stay put."""
    return "".join(
        lower if len(lower := c.lower()) == 1 else c for c in text.translate(_MARKS)
    )


def _first_words(clause: Clause) -> tuple[int, int]:
    text, start = clause.text, 0
    while start < len(text) and (text[start] == " " or start in clause.in_field):
        start += 1
    end, words = start, 0
    while end < len(text) and words < SEED_WORDS and end not in clause.in_field:
        end = _word_end(text, end)
        words += 1
    return start, end


def _word_end(text: str, at: int) -> int:
    while at < len(text) and text[at] == " ":
        at += 1
    while at < len(text) and text[at] != " ":
        at += 1
    return at


def _word_before(clause: Clause, start: int) -> int:
    text, at = clause.text, start
    while at > 0 and text[at - 1] == " ":
        at -= 1
    while at > 0 and text[at - 1] != " ":
        at -= 1
    return start if touches_field(clause, at, start) else at


def _word_after(clause: Clause, end: int) -> int:
    at = _word_end(clause.text, end)
    return end if touches_field(clause, end, at) else at


def _trimmed(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start] == " ":
        start += 1
    while end > start and text[end - 1] == " ":
        end -= 1
    return start, end
