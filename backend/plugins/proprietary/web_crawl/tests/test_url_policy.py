"""Pure URL-helper behavior for the site spider (link surfacing + dedupe scope)."""

from __future__ import annotations

import pytest

from proprietary.web_crawl import url_policy
from proprietary.web_crawl.url_policy import (
    canonical_url,
    extract_link_records,
    extract_links,
    host_of,
    link_inventory,
)

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
        {
            "url": "https://example.com/p",
            "text": "Pricing",
            "rel": "",
            "kind": "internal",
        }
    ]


def test_host_of_strips_www_and_lowercases() -> None:
    assert host_of("https://www.Example.com/x") == "example.com"
    assert host_of("https://Example.com/x") == "example.com"


def test_links_resolve_against_base_href() -> None:
    html = '<head><base href="/en/latest/"></head><a href="user/install/">Install</a>'
    links = extract_links(html, "https://requests.readthedocs.io/")
    assert links == ["https://requests.readthedocs.io/en/latest/user/install/"]
    (record,) = extract_link_records(html, "https://requests.readthedocs.io/")
    assert record["url"] == "https://requests.readthedocs.io/en/latest/user/install/"


def test_code_host_repo_links_are_external_not_social() -> None:
    html = """
    <a href="https://github.com/jane">Jane</a>
    <a href="https://github.com/python/cpython/issues/1">gh-1</a>
    <a href="https://github.com/features">Features</a>
    """
    kinds = {r["url"]: r["kind"] for r in extract_link_records(html, "https://e.com/")}
    assert kinds == {
        "https://github.com/jane": "social",
        "https://github.com/python/cpython/issues/1": "external",
        "https://github.com/features": "external",
    }


def test_link_inventory_caps_records_site_pages_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """13k anchors (the changelog page): 200 records kept, the rest counted.

    Labels are computed only for kept records; they were most of the cost.
    """
    anchors = [f'<a href="https://other{i}.com/">o{i}</a>' for i in range(6000)]
    anchors += [f'<a href="/p{i}">p{i}</a>' for i in range(7000)]
    anchors.append('<a href="https://www.linkedin.com/in/jane">Jane</a>')
    html = "<html><body>" + "".join(anchors) + "</body></html>"
    labels = {"n": 0}
    real_label = url_policy._anchor_label

    def counting_label(anchor):
        labels["n"] += 1
        return real_label(anchor)

    monkeypatch.setattr(url_policy, "_anchor_label", counting_label)

    records, total = link_inventory(html, "https://e.com/", max_records=200)

    assert total == 13001
    assert len(records) == 200
    assert {r["kind"] for r in records} == {"internal"}
    assert records[0]["url"] == "https://e.com/p0"  # page order kept
    assert labels["n"] == 200
    # The frontier is never capped.
    assert len(extract_links(html, "https://e.com/")) == 13001


def test_link_inventory_keeps_profiles_ahead_of_external_links() -> None:
    html = (
        '<a href="https://a.com/">a</a><a href="https://b.com/">b</a>'
        '<a href="https://x.com/acme">X</a><a href="/home">Home</a>'
    )
    records, total = link_inventory(html, "https://e.com/", max_records=2)
    assert total == 4
    assert [r["url"] for r in records] == ["https://x.com/acme", "https://e.com/home"]


def test_canonical_url_matches_a_crawl_visit() -> None:
    assert canonical_url("HTTPS://Requests.ReadTheDocs.io#top") == (
        "https://requests.readthedocs.io/"
    )
    assert canonical_url("https://e.com/a?b=1#c") == "https://e.com/a?b=1"
