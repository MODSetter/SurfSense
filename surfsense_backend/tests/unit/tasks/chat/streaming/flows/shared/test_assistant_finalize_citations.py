"""Behavior tests for finalize-time citation resolution.

The finalize step is the single server-side seam that turns the model's bare
``[n]`` ordinals into renderer-ready ``[citation:<payload>]`` markers, using the
registry captured from the run's final state. These tests pin that contract:
known ordinals resolve, unknown ones drop, foreign markers survive, and a
serialized (dict) registry is accepted just like a live one.
"""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.tasks.chat.streaming.flows.shared.assistant_finalize import _resolve_citations


def _registry_with_chunk(chunk_id: int = 42) -> CitationRegistry:
    registry = CitationRegistry()
    registry.register(
        CitationSourceType.KB_CHUNK, {"document_id": 1, "chunk_id": chunk_id}
    )
    return registry


def _text(value: str) -> list[dict]:
    return [{"type": "text", "text": value}]


def test_known_ordinal_resolves_to_chunk_marker():
    payload = _resolve_citations(
        _text("Launch is March 10 [1]."), _registry_with_chunk(42)
    )

    assert payload[0]["text"] == "Launch is March 10 [citation:42]."


def test_unknown_ordinal_is_dropped():
    payload = _resolve_citations(
        _text("Unsupported claim [9]."), _registry_with_chunk(42)
    )

    assert payload[0]["text"] == "Unsupported claim ."


def test_foreign_citation_marker_is_preserved():
    payload = _resolve_citations(
        _text("From the web [citation:https://example.com]."),
        _registry_with_chunk(42),
    )

    assert payload[0]["text"] == "From the web [citation:https://example.com]."


def test_serialized_registry_is_accepted():
    serialized = _registry_with_chunk(7).model_dump()

    payload = _resolve_citations(_text("See [1]."), serialized)

    assert payload[0]["text"] == "See [citation:7]."


def test_empty_registry_leaves_text_untouched():
    payload = _resolve_citations(_text("No sources here [1]."), CitationRegistry())

    assert payload[0]["text"] == "No sources here [1]."


def test_missing_registry_is_a_noop():
    payload = _resolve_citations(_text("Nothing to resolve [1]."), None)

    assert payload[0]["text"] == "Nothing to resolve [1]."


def test_non_text_parts_are_left_alone():
    parts = [
        {"type": "tool_call", "name": "search_knowledge_base", "args": {"q": "[1]"}},
        {"type": "text", "text": "Result [1]."},
    ]

    payload = _resolve_citations(parts, _registry_with_chunk(5))

    assert payload[0]["args"]["q"] == "[1]"
    assert payload[1]["text"] == "Result [citation:5]."
