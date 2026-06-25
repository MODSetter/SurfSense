"""Tests for the ``<web_results>`` wrapper around web-result excerpt documents."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.agents.chat.multi_agent_chat.shared.document_render import (
    RenderableDocument,
    RenderablePassage,
    render_web_results,
)

pytestmark = pytest.mark.unit


def _web_doc(url: str, title: str, content: str) -> RenderableDocument:
    return RenderableDocument(
        title=title,
        source=f"Web · {url.split('//', 1)[-1].split('/', 1)[0]}",
        passages=[
            RenderablePassage(
                content=content,
                locator={"url": url},
                source_type=CitationSourceType.WEB_RESULT,
            )
        ],
    )


def test_returns_none_when_nothing_to_show() -> None:
    registry = CitationRegistry()

    assert render_web_results([], registry) is None


def test_wraps_in_web_results_container() -> None:
    registry = CitationRegistry()

    block = render_web_results(
        [_web_doc("https://example.com/a", "Example", "the answer is 42")],
        registry,
    )

    assert block is not None
    assert block.startswith("<web_results>")
    assert block.endswith("</web_results>")
    assert "cite a result with its [n]" in block
    assert '<document title="Example" source="Web · example.com" view="excerpt">' in block
    assert "[1] the answer is 42" in block


def test_registers_each_result_as_web_result_with_url_locator() -> None:
    registry = CitationRegistry()

    render_web_results(
        [
            _web_doc("https://a.com/x", "A", "alpha"),
            _web_doc("https://b.com/y", "B", "beta"),
        ],
        registry,
    )

    first = registry.resolve(1)
    second = registry.resolve(2)
    assert first is not None and second is not None
    assert first.source_type is CitationSourceType.WEB_RESULT
    assert first.locator == {"url": "https://a.com/x"}
    assert second.locator == {"url": "https://b.com/y"}


def test_same_url_reuses_label_across_calls() -> None:
    registry = CitationRegistry()
    doc = _web_doc("https://example.com/a", "Example", "stable fact")

    render_web_results([doc], registry)
    render_web_results([doc], registry)

    assert registry.next_n == 2
