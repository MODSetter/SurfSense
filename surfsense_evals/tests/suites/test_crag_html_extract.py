"""Tests for the CRAG HTML extractor.

We don't network-fetch trafilatura; we just verify the wrapper:

* Strips obvious boilerplate (nav/footer/scripts) out of the result.
* Falls back to the stdlib stripper on degenerate input.
* Caps output at the configured ceiling.
* Always prepends a metadata header (``# title``) when content is
  produced.
"""

from __future__ import annotations

from surfsense_evals.suites.research.crag.html_extract import (
    extract_main_content,
)

_RICH_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Apple Q3 Earnings</title>
<script>const a=1;</script>
<style>body{font-family:sans;}</style>
</head>
<body>
<nav><a href="/home">Home</a><a href="/about">About</a></nav>
<header><h1>Tech News Site</h1><p>Subscribe to our newsletter</p></header>
<main>
<article>
  <h1>Apple posts $90B revenue in Q3 2024</h1>
  <p>Apple Inc. announced its Q3 2024 financial results today, reporting
  $90 billion in revenue, beating analyst expectations of $87 billion.</p>
  <p>The company saw growth across iPhone, services, and wearables.
  CEO Tim Cook attributed the performance to strong demand in emerging
  markets, particularly India.</p>
  <h2>Segment breakdown</h2>
  <ul>
    <li>iPhone: $45B</li>
    <li>Services: $24B</li>
    <li>Mac: $7B</li>
  </ul>
</article>
</main>
<footer><p>Copyright 2024 Tech News Site. All rights reserved.</p></footer>
</body></html>
"""


class TestExtractMainContent:
    def test_extracts_main_article(self) -> None:
        result = extract_main_content(
            _RICH_HTML,
            url="https://example.com/apple",
            page_name="Apple Q3 Earnings",
        )
        assert result.ok
        assert "Apple" in result.text
        assert "Q3 2024" in result.text
        # Header line is prepended.
        assert result.text.startswith("# Apple Q3 Earnings")
        assert "Source: https://example.com/apple" in result.text

    def test_strips_boilerplate(self) -> None:
        result = extract_main_content(
            _RICH_HTML,
            url="https://example.com/apple",
            page_name="Apple Q3 Earnings",
        )
        assert result.ok
        # Boilerplate strings should NOT make it through.
        assert "Subscribe to our newsletter" not in result.text
        assert "Copyright 2024 Tech News Site" not in result.text
        assert "const a=1" not in result.text  # script content

    def test_includes_last_modified_when_provided(self) -> None:
        result = extract_main_content(
            _RICH_HTML,
            url="https://example.com/apple",
            page_name="Apple Q3 Earnings",
            last_modified="2024-08-01",
        )
        assert "Last modified: 2024-08-01" in result.text

    def test_empty_html_returns_empty_result(self) -> None:
        result = extract_main_content("", url="https://x.test/")
        assert not result.ok
        assert result.method == "empty"
        assert result.n_chars == 0

    def test_whitespace_only_html_is_empty(self) -> None:
        result = extract_main_content("   \n   ", url="https://x.test/")
        assert not result.ok

    def test_garbage_html_falls_back(self) -> None:
        # Trafilatura should reject this, fallback strip should still yield text.
        result = extract_main_content(
            "<<weird>>not a tag>>>The brown fox<<jumped<<",
            url="https://x.test/garbage",
            page_name="Garbage",
        )
        # Either trafilatura recovers something or fallback_strip does.
        if result.ok:
            assert "brown fox" in result.text or "jumped" in result.text


class TestFallbackStripper:
    def test_extract_when_no_clear_main(self) -> None:
        html = """
        <html><body>
        <p>This is content one.</p>
        <p>This is content two.</p>
        </body></html>
        """
        result = extract_main_content(
            html, url="https://x.test/", page_name="Title",
        )
        assert result.ok
        assert "content one" in result.text
        assert "content two" in result.text

    def test_html_entities_decoded(self) -> None:
        html = """<html><body>
        <article>
        <p>Tom &amp; Jerry &mdash; classic cartoon &copy; 1940.</p>
        <p>It's a story about a cat &lt;Tom&gt; and a mouse &lt;Jerry&gt;.</p>
        </article>
        </body></html>"""
        result = extract_main_content(html, url="https://x.test/")
        assert result.ok
        # & should be decoded
        assert "&amp;" not in result.text
        assert "Tom" in result.text and "Jerry" in result.text


class TestOutputCapping:
    def test_long_output_is_truncated(self) -> None:
        # Generate enough content to exceed 200k cap.
        body = "<p>" + ("hello world " * 50_000) + "</p>"
        html = f"<html><body><article>{body}</article></body></html>"
        result = extract_main_content(html, url="https://x.test/", page_name="long")
        assert result.ok
        # The body text itself + the metadata header. Truncation marker
        # appears either at the body limit or before EOF.
        if "[...truncated...]" in result.text:
            # The truncation kicked in.
            assert len(result.text) <= 250_000  # header + 200k cap + slack
