"""Pure URL-helper behavior for the site spider (link surfacing + dedupe scope)."""

from __future__ import annotations

import pytest

from app.proprietary.web_crawler.url_policy import (
    canonicalize_url,
    extract_links,
    host_of,
    same_site,
)

pytestmark = pytest.mark.unit

_HTML = """
<html><body>
  <a href="/about">About (relative)</a>
  <a href="https://example.com/contact">Contact (absolute)</a>
  <a href="https://other.com/x">External</a>
  <a href="#top">Anchor only</a>
  <a href="mailto:a@b.com">Mail</a>
  <a href="javascript:void(0)">JS</a>
  <a href="/about">Duplicate about</a>
</body></html>
"""


def test_extract_links_absolutizes_relative_hrefs() -> None:
    links = extract_links(_HTML, "https://example.com/home")
    assert "https://example.com/about" in links
    assert "https://example.com/contact" in links


def test_extract_links_keeps_only_http_schemes() -> None:
    links = extract_links(_HTML, "https://example.com/home")
    assert all(link.startswith(("http://", "https://")) for link in links)
    assert not any("mailto" in link or "javascript" in link for link in links)


def test_extract_links_drops_pure_anchor() -> None:
    links = extract_links(_HTML, "https://example.com/home")
    assert "https://example.com/home" not in links  # bare "#top" resolves to self


def test_extract_links_dedupes_preserving_first_occurrence() -> None:
    links = extract_links(_HTML, "https://example.com/home")
    assert links.count("https://example.com/about") == 1


def test_extract_links_strips_fragments() -> None:
    assert extract_links('<a href="/p#sec">x</a>', "https://e.com") == [
        "https://e.com/p"
    ]


def test_extract_links_on_empty_or_blank_html_is_empty() -> None:
    assert extract_links("", "https://e.com") == []
    assert extract_links("   ", "https://e.com") == []
    assert extract_links(None, "https://e.com") == []


def test_canonicalize_lowercases_host_sorts_query_and_drops_fragment() -> None:
    assert (
        canonicalize_url("https://E.com/a?b=2&a=1#frag") == "https://e.com/a?a=1&b=2"
    )


def test_canonicalize_collapses_fragment_and_empty_query_to_one_key() -> None:
    # The three forms must dedupe to the same visited-set key.
    canonical = canonicalize_url("https://e.com/a")
    assert canonicalize_url("https://e.com/a#frag") == canonical
    assert canonicalize_url("https://e.com/a?") == canonical


def test_canonicalize_keeps_nondefault_port() -> None:
    assert canonicalize_url("https://e.com:8443/x") == "https://e.com:8443/x"


def test_host_of_strips_www_and_lowercases() -> None:
    assert host_of("https://www.Example.com/x") == "example.com"
    assert host_of("https://Example.com/x") == "example.com"


def test_same_site_matches_on_normalized_host() -> None:
    allowed = {"example.com"}
    assert same_site("https://www.example.com/a", allowed) is True
    assert same_site("https://example.com/b", allowed) is True
    assert same_site("https://other.com/c", allowed) is False
