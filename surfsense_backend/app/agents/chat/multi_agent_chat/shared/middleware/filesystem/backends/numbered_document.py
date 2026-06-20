"""Read preamble for canonical (numbered ``source_markdown``) KB reads.

The KB read tool numbers the body lines ``cat -n`` style, so serving the raw
``source_markdown`` makes those line numbers line up exactly with the chunk
char spans and the editor highlight. This module renders the small header the
agent sees above that body: document identity plus the matched line ranges to
seek to, and a concrete reminder of the line-citation token shape.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.utils.text_spans import char_span_to_line_range


def _format_range(start: int, end: int) -> str:
    return f"{start}" if start == end else f"{start}-{end}"


def compute_matched_line_ranges(
    source_markdown: str,
    chunks: Iterable[tuple[int, int | None, int | None]],
    matched_chunk_ids: set[int],
) -> list[tuple[int, int]]:
    """Map matched chunks to sorted, de-duplicated 1-based line ranges.

    ``chunks`` are ``(chunk_id, start_char, end_char)`` triples. Chunks without
    spans (legacy rows) are skipped — they have no resolvable location.
    """
    ranges: set[tuple[int, int]] = set()
    for chunk_id, start_char, end_char in chunks:
        if chunk_id not in matched_chunk_ids:
            continue
        if start_char is None or end_char is None:
            continue
        ranges.add(char_span_to_line_range(source_markdown, start_char, end_char))
    return sorted(ranges)


def build_read_preamble(
    *,
    document_id: int,
    document_type: str,
    title: str,
    url: str,
    matched_line_ranges: list[tuple[int, int]],
) -> str:
    """Render the metadata header shown above a numbered ``source_markdown`` body.

    ``matched_line_ranges`` are 1-based inclusive line ranges (already derived
    from chunk char spans) to point the agent at the relevant lines.
    """
    lines = [
        "<document_metadata>",
        f"  <document_id>{document_id}</document_id>",
        f"  <document_type>{document_type}</document_type>",
        f"  <title><![CDATA[{title}]]></title>",
        f"  <url><![CDATA[{url}]]></url>",
    ]
    if matched_line_ranges:
        ranges = ", ".join(_format_range(s, e) for s, e in matched_line_ranges)
        lines.append(f"  <matched_lines>{ranges}</matched_lines>")
    lines.append("</document_metadata>")
    lines.append(
        f"Cite lines from this document as [citation:d{document_id}#L<start>-<end>] "
        "using the line numbers shown below."
    )
    lines.append("")
    return "\n".join(lines)


__all__ = ["build_read_preamble", "compute_matched_line_ranges"]
