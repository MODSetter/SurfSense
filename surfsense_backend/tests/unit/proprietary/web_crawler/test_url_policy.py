"""Pure URL-helper behavior for the site spider (link surfacing + dedupe scope)."""

from __future__ import annotations

import pytest

from app.proprietary.web_crawler.url_policy import (
    extract_link_records,
    extract_links,
    host_of,
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


def test_extract_link_records_classifies_kinds_and_keeps_anchor_text() -> None:
    html = """
    <a href="/about">  About\n  us </a>
    <a href="https://other.com/x">External</a>
    <a href="https://www.linkedin.com/in/jane">Jane Doe</a>
    <a href="mailto:a@b.com?subject=hi">Mail</a>
    <a href="tel:+1-555-0100">Call</a>
    """
    records = {r["url"]: r for r in extract_link_records(html, "https://example.com/")}
    assert records["https://example.com/about"]["kind"] == "internal"
    assert records["https://example.com/about"]["text"] == "About us"  # collapsed ws
    assert records["https://other.com/x"]["kind"] == "external"
    assert records["https://www.linkedin.com/in/jane"] == {
        "url": "https://www.linkedin.com/in/jane",
        "text": "Jane Doe",
        "context": "",
        "rel": "",
        "kind": "social",
    }
    assert records["a@b.com"]["kind"] == "email"  # mailto query stripped
    assert records["+1-555-0100"]["kind"] == "tel"


def test_percent_encoded_tel_and_mailto_are_decoded() -> None:
    """Seen live: <a href="tel:+1%20408-629-1770"> must not leak %20."""
    html = """
    <a href="tel:+1%20408-629-1770">Call</a>
    <a href="mailto:hello%40acme.io">Email</a>
    """
    records = {r["kind"]: r for r in extract_link_records(html, "https://example.com/")}
    assert records["tel"]["url"] == "+1 408-629-1770"
    assert records["email"]["url"] == "hello@acme.io"


def test_icon_only_social_link_gets_ancestor_context() -> None:
    html = """
    <div class="team-card">
      <h3>Jane Doe</h3><p>General Partner</p>
      <a href="https://linkedin.com/in/jane"><svg></svg></a>
    </div>
    """
    (record,) = extract_link_records(html, "https://example.com/")
    assert record["text"] == ""
    assert record["context"] == "Jane Doe General Partner"


def test_icon_social_link_prefers_aria_label_over_context() -> None:
    html = '<div>Footer<a href="https://x.com/acme" aria-label="Acme on X"><svg></svg></a></div>'
    (record,) = extract_link_records(html, "https://example.com/")
    assert record["text"] == "Acme on X"
    assert record["context"] == ""


def test_extract_link_records_dedupes_keeping_first_nonempty_text() -> None:
    html = '<a href="/p"><img src="logo.png"/></a><a href="/p">Pricing</a>'
    records = extract_link_records(html, "https://example.com/")
    assert records == [
        {"url": "https://example.com/p", "text": "Pricing", "rel": "", "kind": "internal"}
    ]


def test_host_of_strips_www_and_lowercases() -> None:
    assert host_of("https://www.Example.com/x") == "example.com"
    assert host_of("https://Example.com/x") == "example.com"
