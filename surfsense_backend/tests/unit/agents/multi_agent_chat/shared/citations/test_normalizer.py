"""Tests for rewriting model ``[n]`` ordinals into frontend citation markers."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations.models import CitationSourceType
from app.agents.chat.multi_agent_chat.shared.citations.normalizer import (
    normalize_citations,
)
from app.agents.chat.multi_agent_chat.shared.citations.registry import CitationRegistry

pytestmark = pytest.mark.unit


def _registry_with_chunks(*chunk_ids: int) -> CitationRegistry:
    registry = CitationRegistry()
    for chunk_id in chunk_ids:
        registry.register(CitationSourceType.KB_CHUNK, {"chunk_id": chunk_id})
    return registry


def test_single_ordinal_is_rewritten() -> None:
    registry = _registry_with_chunks(42)

    assert normalize_citations("We shipped it [1].", registry) == (
        "We shipped it [citation:42]."
    )


def test_adjacent_brackets_are_each_rewritten() -> None:
    registry = _registry_with_chunks(42, 7)

    assert normalize_citations("Both agree [1][2].", registry) == (
        "Both agree [citation:42][citation:7]."
    )


def test_comma_separated_brackets_are_each_rewritten() -> None:
    registry = _registry_with_chunks(42, 7)

    assert normalize_citations("Both agree [1], [2].", registry) == (
        "Both agree [citation:42], [citation:7]."
    )


def test_unknown_ordinal_is_dropped() -> None:
    registry = _registry_with_chunks(42)

    assert normalize_citations("Maybe [9] is real.", registry) == "Maybe  is real."


def test_unknown_ordinal_among_known_is_dropped() -> None:
    registry = _registry_with_chunks(42)

    assert normalize_citations("See [1][9].", registry) == "See [citation:42]."


def test_web_result_rewrites_to_url() -> None:
    registry = CitationRegistry()
    registry.register(CitationSourceType.WEB_RESULT, {"url": "https://example.com"})

    assert normalize_citations("Per the docs [1].", registry) == (
        "Per the docs [citation:https://example.com]."
    )


def test_index_expression_is_left_alone() -> None:
    registry = _registry_with_chunks(42)

    assert normalize_citations("Read arr[1] carefully.", registry) == (
        "Read arr[1] carefully."
    )


def test_ordinals_inside_inline_code_are_untouched() -> None:
    registry = _registry_with_chunks(42)

    assert normalize_citations("Use `list[1]` here [1].", registry) == (
        "Use `list[1]` here [citation:42]."
    )


def test_ordinals_inside_fenced_code_are_untouched() -> None:
    registry = _registry_with_chunks(42)
    text = "Before [1].\n```\nx = a[1]\n```\nAfter [1]."

    assert normalize_citations(text, registry) == (
        "Before [citation:42].\n```\nx = a[1]\n```\nAfter [citation:42]."
    )


def test_empty_text_is_returned_unchanged() -> None:
    assert normalize_citations("", _registry_with_chunks(42)) == ""
