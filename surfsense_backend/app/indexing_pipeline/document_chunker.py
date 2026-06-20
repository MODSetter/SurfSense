import re
from dataclasses import dataclass

from app.config import config

# Regex that matches a Markdown table block (header + separator + one or more rows)
# A table block starts with a | at the beginning of a line and ends when a
# non-table line (or end of string) is encountered. The final row may end at EOF
# without a trailing newline, so the whole table stays one slice.
_TABLE_BLOCK_RE = re.compile(
    r"(?:(?:^|\n)(?=[ \t]*\|)(?:[ \t]*\|[^\n]*(?:\n|$))+)",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class ChunkSlice:
    """A chunk paired with its half-open char span into the source markdown.

    Invariant: ``markdown[start_char:end_char] == text``.
    """

    text: str
    start_char: int
    end_char: int


def chunk_text(text: str, use_code_chunker: bool = False) -> list[str]:
    """Chunk a text string using the configured chunker and return the chunk texts."""
    chunker = (
        config.code_chunker_instance if use_code_chunker else config.chunker_instance
    )
    return [c.text for c in chunker.chunk(text)]


def chunk_markdown_with_spans(
    text: str, use_code_chunker: bool = False
) -> list[ChunkSlice]:
    """Chunk markdown into a lossless, contiguous partition of char-addressed slices.

    Tables stay whole (issue #1334) and every slice is an exact substring of
    ``text``, so ``"".join(s.text) == text`` and ``text[s:e] == s.text``. This is
    the offset record citations resolve against.
    """
    if not text:
        return []

    slices: list[ChunkSlice] = []
    cursor = 0

    for match in _TABLE_BLOCK_RE.finditer(text):
        if match.start() > cursor:
            slices.extend(
                _segment_slices(text, cursor, match.start(), use_code_chunker)
            )
        slices.append(ChunkSlice(match.group(0), match.start(), match.end()))
        cursor = match.end()

    if len(text) > cursor:
        slices.extend(_segment_slices(text, cursor, len(text), use_code_chunker))

    return slices


def _segment_slices(
    text: str, start: int, end: int, use_code_chunker: bool
) -> list[ChunkSlice]:
    """Sub-chunk one non-table segment into contiguous, char-addressed slices."""
    chunker = (
        config.code_chunker_instance if use_code_chunker else config.chunker_instance
    )
    segment = text[start:end]
    chunks = chunker.chunk(segment)

    slices: list[ChunkSlice] = []
    local = 0
    for chunk in chunks:
        # Use the chunker's end offset only as a cut point, then re-slice the
        # segment ourselves so the result is an exact, gap-free substring.
        local_end = min(max(chunk.end_index, local), len(segment))
        if local_end <= local:
            continue
        slices.append(
            ChunkSlice(segment[local:local_end], start + local, start + local_end)
        )
        local = local_end

    if local < len(segment):
        if slices:
            last = slices[-1]
            slices[-1] = ChunkSlice(text[last.start_char : end], last.start_char, end)
        else:
            slices.append(ChunkSlice(segment[local:], start + local, end))

    return slices
