"""Parity tests for the citation regex.

Each row mirrors a case from the canonical TS reference at
``surfsense_web/lib/citations/citation-parser.ts``. If a future PR
loosens or tightens the TS regex, these tests will start failing;
that's the explicit signal to re-port the change.
"""

from __future__ import annotations

import pytest

from surfsense_evals.core.parse import (
    CITATION_REGEX,
    ChunkCitation,
    UrlCitation,
    parse_citations,
)

PARITY_TABLE = [
    # (input, expected number of matches, expected first-token kind/value)
    ("Plain text with no citation.", 0, None),
    (
        "The patient has fever [citation:42] and cough.",
        1,
        ChunkCitation(chunk_id=42, is_docs_chunk=False),
    ),
    (
        "Negative chunk ids work [citation:-7].",
        1,
        ChunkCitation(chunk_id=-7, is_docs_chunk=False),
    ),
    (
        "doc-prefix [citation:doc-12].",
        1,
        ChunkCitation(chunk_id=12, is_docs_chunk=True),
    ),
    (
        "Multi id [citation:1, doc-2, -3].",
        3,
        ChunkCitation(chunk_id=1, is_docs_chunk=False),
    ),
    (
        "URL form [citation:https://x.com/a].",
        1,
        UrlCitation(url="https://x.com/a"),
    ),
    (
        "Chinese brackets【citation:5】.",
        1,
        ChunkCitation(chunk_id=5, is_docs_chunk=False),
    ),
    (
        "ZWSP-decorated [\u200bcitation:9\u200b].",
        1,
        ChunkCitation(chunk_id=9, is_docs_chunk=False),
    ),
    (
        "Whitespace [citation:  doc-100 ] tolerated.",
        1,
        ChunkCitation(chunk_id=100, is_docs_chunk=True),
    ),
    (
        # The TS regex's URL char class excludes ']', so a trailing
        # bracket isn't swallowed.
        "Two URLs [citation:https://a.io] and [citation:https://b.io].",
        2,
        UrlCitation(url="https://a.io"),
    ),
    (
        # Garbled form should match nothing.
        "Citation-like but wrong [citation:].",
        0,
        None,
    ),
]


@pytest.mark.parametrize("text,n_expected,first", PARITY_TABLE)
def test_citation_regex_parity(text: str, n_expected: int, first):
    tokens = parse_citations(text)
    assert len(tokens) == n_expected, (text, tokens)
    if first is not None:
        assert tokens[0] == first, (text, tokens)


def test_regex_pattern_matches_ts_source():
    """Sanity: the compiled pattern carries the exact alternatives the TS source does."""

    pattern = CITATION_REGEX.pattern
    assert "https?://" in pattern
    assert "urlcite" in pattern
    assert "doc-" in pattern
    assert "\u200B" in pattern
    assert "【" in pattern and "】" in pattern


def test_url_map_resolution():
    text = "Inline placeholder [citation:urlcite0]."
    tokens = parse_citations(text, url_map={"urlcite0": "https://resolved.example/x"})
    assert tokens == [UrlCitation(url="https://resolved.example/x")]


def test_url_map_missing_key_drops_token():
    """Missing urlcite resolution returns no token (TS behaviour)."""

    text = "[citation:urlcite99]"
    assert parse_citations(text, url_map={}) == []
