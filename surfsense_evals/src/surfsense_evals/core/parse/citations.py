"""Python port of the canonical citation parser.

Source of truth: ``surfsense_web/lib/citations/citation-parser.ts:20-21``.
The pattern is byte-for-byte identical to the TS export ``CITATION_REGEX``
so a SurfSense user reading the web client and a CUREv1 retrieval scorer
running here see the same chunk_ids extracted from the same answer.

The TS reference also handles a ``urlcite{N}`` placeholder produced by
``preprocessCitationMarkdown`` — that pre-processing step is web-only
(GFM autolink workaround), so the harness sees raw ``[citation:URL]``
tokens and ``parse_citations`` returns them as ``UrlCitation`` directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Pattern preserves the TS source verbatim:
#   /[\[【]\u200B?citation:\s*(https?:\/\/[^\]】\u200B]+|urlcite\d+|(?:doc-)?-?\d+(?:\s*,\s*(?:doc-)?-?\d+)*)\s*\u200B?[\]】]/g
#
# Notes:
# * Matches both ASCII ``[]`` and Chinese fullwidth ``【】`` brackets.
# * Allows an optional ZWSP (``\u200B``) just inside each bracket.
# * ``citation:`` then EITHER a URL (anything not ``]``, ``】``, or ZWSP),
#   OR a ``urlcite\d+`` placeholder, OR one or more comma-separated
#   chunk ids (each optionally prefixed with ``doc-`` and optionally
#   negative).
# * URL char class deliberately excludes the closing brackets so a
#   ``[citation:https://x.com]`` doesn't swallow the ``]``.
# The ZWSP must be the actual code-point — the original TS source uses
# the regex literal ``\u200B`` which the JS engine interprets as the
# character. Python's ``re`` doesn't process the ``\u`` escape inside
# the pattern source, so we splice the literal character in via an
# f-string. This keeps our pattern functionally identical to the TS
# reference and lets ``"\u200B" in CITATION_REGEX.pattern`` succeed.
_ZWSP = "\u200B"
CITATION_REGEX = re.compile(
    rf"[\[【]{_ZWSP}?citation:\s*("
    rf"https?://[^\]】{_ZWSP}]+|urlcite\d+|(?:doc-)?-?\d+(?:\s*,\s*(?:doc-)?-?\d+)*"
    rf")\s*{_ZWSP}?[\]】]"
)


@dataclass(frozen=True)
class ChunkCitation:
    chunk_id: int
    is_docs_chunk: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "chunk",
            "chunk_id": self.chunk_id,
            "is_docs_chunk": self.is_docs_chunk,
        }


@dataclass(frozen=True)
class UrlCitation:
    url: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "url", "url": self.url}


CitationToken = ChunkCitation | UrlCitation


def parse_citations(text: str, *, url_map: dict[str, str] | None = None) -> list[CitationToken]:
    """Return the citation tokens found in ``text`` in document order.

    ``url_map`` is the optional ``urlciteN -> URL`` lookup that the web
    client builds in its preprocessing step. The harness ordinarily
    doesn't preprocess (we don't render the markdown, we score it), so
    the default empty map means ``urlciteN`` placeholders are dropped
    rather than mis-resolved to a missing URL.

    Multi-id payloads like ``[citation:1, doc-2, -3]`` are flattened
    into separate ``ChunkCitation`` entries — same as the TS reference.
    """

    out: list[CitationToken] = []
    for match in CITATION_REGEX.finditer(text):
        captured = match.group(1)
        if captured.startswith("http://") or captured.startswith("https://"):
            out.append(UrlCitation(url=captured.strip()))
            continue
        if captured.startswith("urlcite"):
            if url_map and captured in url_map:
                out.append(UrlCitation(url=url_map[captured]))
            continue
        for raw_id in (s.strip() for s in captured.split(",")):
            is_docs_chunk = raw_id.startswith("doc-")
            number_part = raw_id[4:] if is_docs_chunk else raw_id
            try:
                chunk_id = int(number_part)
            except ValueError:
                continue
            out.append(ChunkCitation(chunk_id=chunk_id, is_docs_chunk=is_docs_chunk))
    return out


__all__ = [
    "CITATION_REGEX",
    "ChunkCitation",
    "UrlCitation",
    "CitationToken",
    "parse_citations",
]
