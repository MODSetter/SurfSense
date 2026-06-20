"""Convert char spans into document-relative line ranges.

Chunks store half-open char spans into ``source_markdown``; citations and the
editor speak in line numbers. This is the single shared conversion so search,
the resolve API, and highlighting all agree on what "lines X-Y" means.
"""

from __future__ import annotations


def char_span_to_line_range(text: str, start_char: int, end_char: int) -> tuple[int, int]:
    """Return the 1-based inclusive line range covering ``[start_char, end_char)``.

    Offsets are clamped to ``text`` bounds. An empty span resolves to the single
    line containing it.
    """
    n = len(text)
    start = max(0, min(start_char, n))
    end = max(start, min(end_char, n))
    start_line = text.count("\n", 0, start) + 1
    last_char_index = max(start, end - 1)
    end_line = text.count("\n", 0, last_char_index) + 1
    return start_line, end_line
