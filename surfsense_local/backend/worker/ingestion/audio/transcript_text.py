"""A recording's transcript as its content: one header line, then a paragraph
per window starting with its time. The chunker splits at blank lines, so while
a window's paragraph stays under a chunk, every chunk opens with when it was
said, and the agent can quote times. CJK text has no `. ` to split at either."""

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from worker.ingestion.audio.language_names import english_name

__all__ = [
    "HeardWindow",
    "header_language",
    "majority_language",
    "paragraph_lines",
    "transcript_markdown",
]

_GUIDE = "[hh:mm:ss] marks where each passage starts."
_NOT_IDENTIFIED = "language not identified"
_LOWER_ACCURACY = "lower accuracy with this model"


@dataclass(frozen=True)
class HeardWindow:
    start_s: float
    end_s: float
    text: str
    # A language code, or None when nothing said which.
    language: str | None


def transcript_markdown(
    *,
    title: str,
    seconds: float,
    windows: Sequence[HeardWindow],
    language: str,
    model: str,
) -> str:
    header = (
        f"Transcript of {title} · {_length(seconds)} · {language} · {model}. {_GUIDE}"
    )
    paragraphs = [
        f"[{_timestamp(w.start_s)}] {' '.join(w.text.split())}"
        for w in windows
        if w.text
    ]
    return "\n\n".join([header, *paragraphs]) + "\n"


def paragraph_lines(windows: Sequence[HeardWindow]) -> list[int | None]:
    """The line each window's paragraph is on, counted from 1 as chunks count
    theirs; None for a window with nothing written."""
    lines: list[int | None] = []
    line = 3  # the header, then a blank line
    for window in windows:
        if window.text:
            lines.append(line)
            line += 2
        else:
            lines.append(None)
    return lines


def header_language(
    windows: Sequence[HeardWindow], pinned: str | None, listed: Collection[str]
) -> str:
    """The language the user set, else the one most windows were heard in."""
    if pinned is not None:
        return english_name(pinned)
    code = majority_language(windows)
    if code is None:
        return _NOT_IDENTIFIED
    if code in listed:
        return f"{english_name(code)} (detected)"
    return f"{english_name(code)} (detected) · {_LOWER_ACCURACY}"


def majority_language(windows: Sequence[HeardWindow]) -> str | None:
    """Most windows with text, then most seconds of them."""
    counts: Counter[str] = Counter()
    seconds: Counter[str] = Counter()
    for window in windows:
        if window.text and window.language is not None:
            counts[window.language] += 1
            seconds[window.language] += window.end_s - window.start_s
    if not counts:
        return None
    return max(counts, key=lambda code: (counts[code], seconds[code]))


def _length(seconds: float) -> str:
    hours, minutes, rest = _clock(seconds)
    return f"{hours}:{minutes:02}:{rest:02}" if hours else f"{minutes}:{rest:02}"


def _timestamp(seconds: float) -> str:
    hours, minutes, rest = _clock(seconds)
    return f"{hours:02}:{minutes:02}:{rest:02}"


def _clock(seconds: float) -> tuple[int, int, int]:
    whole = int(seconds)
    return whole // 3600, whole // 60 % 60, whole % 60
