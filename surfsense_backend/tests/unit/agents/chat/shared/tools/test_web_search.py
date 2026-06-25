"""Tests for the shared ``web_search`` tool's citable-result adaptation.

The tool's network path (SearXNG + live connectors) is out of scope here; these
cover the pure mapping from raw web results to renderable, citable documents and
the end-to-end registration of ``WEB_RESULT`` ``[n]`` labels.
"""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.agents.chat.multi_agent_chat.shared.document_render import render_web_results
from app.agents.chat.shared.tools.web_search import (
    _to_renderable_web_documents,
    _web_source_label,
)

pytestmark = pytest.mark.unit


def _raw_result(url: str, title: str, content: str) -> dict:
    return {
        "document": {"title": title, "metadata": {"url": url}},
        "content": content,
    }


def test_web_source_label_strips_scheme_and_www() -> None:
    assert _web_source_label("https://www.example.com/path") == "Web · example.com"
    assert _web_source_label("http://news.site.org/a/b") == "Web · news.site.org"
    assert _web_source_label("") == "Web"


def test_adapter_maps_each_result_to_one_web_passage() -> None:
    docs = _to_renderable_web_documents(
        [
            _raw_result("https://a.com/x", "Alpha", "alpha body"),
            _raw_result("https://b.com/y", "Beta", "beta body"),
        ]
    )

    assert [d.title for d in docs] == ["Alpha", "Beta"]
    passages = [p for d in docs for p in d.passages]
    assert all(p.source_type is CitationSourceType.WEB_RESULT for p in passages)
    assert passages[0].locator == {"url": "https://a.com/x"}
    assert passages[0].content == "alpha body"


def test_adapter_skips_results_without_url_or_content() -> None:
    docs = _to_renderable_web_documents(
        [
            _raw_result("", "No URL", "has content"),
            _raw_result("https://c.com/z", "Empty", "   "),
            _raw_result("https://d.com/w", "Good", "real content"),
        ]
    )

    assert [d.title for d in docs] == ["Good"]


def test_adapter_truncates_on_char_budget() -> None:
    big = "x" * 30
    docs = _to_renderable_web_documents(
        [
            _raw_result("https://a.com", "A", big),
            _raw_result("https://b.com", "B", big),
            _raw_result("https://c.com", "C", big),
        ],
        max_chars=50,
    )

    # First fits (30), second crosses 50 and stops the loop.
    assert [d.title for d in docs] == ["A"]


def test_end_to_end_registers_web_results_for_citation() -> None:
    registry = CitationRegistry()
    docs = _to_renderable_web_documents(
        [_raw_result("https://example.com/a", "Example", "the answer is 42")]
    )

    block = render_web_results(docs, registry)

    assert block is not None
    assert "[1] the answer is 42" in block
    entry = registry.resolve(1)
    assert entry is not None
    assert entry.source_type is CitationSourceType.WEB_RESULT
    assert entry.locator == {"url": "https://example.com/a"}
