"""``_build_result`` surfaces absolute page links for the spider to enqueue."""

from __future__ import annotations

import pytest

from app.proprietary.web_crawler import WebCrawlerConnector

pytestmark = pytest.mark.unit


def test_build_result_includes_absolute_links() -> None:
    html = (
        "<html><body>"
        '<a href="/a">A</a>'
        '<a href="https://example.com/b">B</a>'
        "</body></html>"
    )

    result = WebCrawlerConnector()._build_result(
        html,
        "https://example.com/",
        "scrapling-static",
        allow_raw_fallback=True,
    )

    assert result is not None
    assert "https://example.com/a" in result["links"]
    assert "https://example.com/b" in result["links"]
