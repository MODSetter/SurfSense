"""Unit tests for search_knowledge_base hit rendering.

The tool must surface the passage that actually matched (the RRF-ranked
chunk), not the top of the document, and annotate it with its line range
when the chunk carries a char span.
"""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.main_agent.tools.search_knowledge_base import (
    _format_hits,
)

pytestmark = pytest.mark.unit

_BODY = "Intro paragraph.\n\nMatched passage here.\n\nClosing paragraph."


def _hit() -> dict:
    intro = "Intro paragraph."
    matched = "Matched passage here."
    matched_start = _BODY.index(matched)
    return {
        "document": {"id": 7, "title": "note.md", "document_type": "NOTE"},
        "score": 0.42,
        "content": _BODY.replace("\n\n", "\n\n"),
        "matched_chunk_ids": [102],
        "chunks": [
            {
                "chunk_id": 101,
                "content": intro,
                "start_char": 0,
                "end_char": len(intro),
            },
            {
                "chunk_id": 102,
                "content": matched,
                "start_char": matched_start,
                "end_char": matched_start + len(matched),
            },
        ],
    }


def test_renders_matched_passage_not_top_of_doc() -> None:
    out = _format_hits([_hit()], paths={7: "/documents/note.md"}, bodies={7: _BODY}, query="q")
    assert "Matched passage here." in out
    # The intro chunk was not matched, so it must not be shown as the snippet.
    assert "Intro paragraph." not in out


def test_includes_line_range_when_spans_present() -> None:
    out = _format_hits([_hit()], paths={7: "/documents/note.md"}, bodies={7: _BODY}, query="q")
    # "Matched passage here." sits on line 3 of the body.
    assert "line 3" in out


def test_omits_line_range_when_spans_absent() -> None:
    hit = _hit()
    for chunk in hit["chunks"]:
        chunk["start_char"] = None
        chunk["end_char"] = None
    out = _format_hits([hit], paths={7: "/documents/note.md"}, bodies={7: _BODY}, query="q")
    assert "Matched passage here." in out
    assert "[line" not in out


def test_falls_back_to_content_when_no_matched_ids() -> None:
    hit = _hit()
    hit["matched_chunk_ids"] = []
    out = _format_hits([hit], paths={7: "/documents/note.md"}, bodies={7: _BODY}, query="q")
    assert "Intro paragraph." in out


def test_no_results_message() -> None:
    out = _format_hits([], paths={}, bodies={}, query="missing")
    assert "No knowledge-base matches" in out
