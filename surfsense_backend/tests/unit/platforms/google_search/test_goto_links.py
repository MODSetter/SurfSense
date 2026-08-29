"""Offline checks for Google's ``/goto`` outbound-result redirects.

Regression guard for the Jul-2026 rollout that emptied ``organicResults``:
Google replaced every outbound result ``href`` with an opaque
``/goto?url=<encrypted blob>`` redirect, and the parser only accepted anchors
whose href started with ``http``, so it skipped every block on the page. The
handful of results that survived were Google's own properties, which are not
wrapped — hence the "empty, or 1-2 results" symptom.

Two halves are pinned here: the parser must *see* redirect anchors as result
links, and :mod:`~app.proprietary.platforms.google_search.goto` must turn them
back into destinations by following the 302 (the blob is encrypted with a key
only Google holds, so there is no offline shortcut).
"""

import pytest

from app.proprietary.platforms.google_search import goto
from app.proprietary.platforms.google_search.parsers import GOTO_PREFIX, parse_serp

pytestmark = pytest.mark.unit

# Blobs are base64url protobuf in the wild; their content is irrelevant here
# because only Google can decrypt them — all we rely on is the href shape.
_GOTO_A = "/goto?url=CAESfQHrOzAVaaa"
_GOTO_B = "/goto?url=CAESfQHrOzAVbbb"

# A SERP in the post-rollout shape: outbound links are /goto, Google's own
# property is a bare https link, and the PAA/AI-Overview citations are /goto too.
_SERP = f"""
<html><body>
  <div id="rso">
    <div class="tF2Cxc">
      <a href="{_GOTO_A}"><h3>Redirected Result</h3>
        <cite>https://example.com<span> > Blog</span></cite></a>
      <div class="VwiC3b">A snippet.</div>
    </div>
    <div class="tF2Cxc">
      <a href="{_GOTO_B}"><h3>Another Redirected Result</h3></a>
    </div>
    <div class="tF2Cxc">
      <a href="https://developers.google.com/search/docs"><h3>Google's Own</h3></a>
    </div>
  </div>
  <div class="related-question-pair" data-q="What is pie?">
    <span class="hgKElc">A baked dish.</span>
    <a href="{_GOTO_A}"><h3>Pie - Example</h3></a>
  </div>
  <div id="m-x-content">
    <div class="n6owBd">Pie is a classic dessert.</div>
    <ul><li class="h7wxwc">
      <a aria-label="Pie History. Opens in new tab." href="{_GOTO_B}"></a>
      <span class="vhJ6Pe">A short history of pie.</span>
    </li></ul>
  </div>
</body></html>
"""

_DESTINATIONS = {
    GOTO_PREFIX + "url=CAESfQHrOzAVaaa": "https://example.com/blog/pie",
    GOTO_PREFIX + "url=CAESfQHrOzAVbbb": "https://second.example/history",
}


class _Response:
    def __init__(self, headers):
        self.headers = headers
        self.status = 302


@pytest.fixture
def google_redirects(monkeypatch):
    """Stub the one-hop redirect fetch, recording every URL it was asked for."""
    asked: list[str] = []

    async def _get(url, **kwargs):
        asked.append(url)
        destination = _DESTINATIONS.get(url)
        if destination is None:
            return _Response({})  # a link Google would not resolve
        return _Response({"location": destination})

    monkeypatch.setattr(goto.AsyncFetcher, "get", _get)
    return asked


def test_parser_reads_redirect_anchors_as_result_links():
    """The bug itself: every block must survive, not just Google's own."""
    item = parse_serp(_SERP)

    assert [r.title for r in item.organicResults] == [
        "Redirected Result",
        "Another Redirected Result",
        "Google's Own",
    ]
    # Redirects are emitted absolute (so goto.py can fetch them); a plain http
    # href is passed through untouched.
    assert item.organicResults[0].url == GOTO_PREFIX + "url=CAESfQHrOzAVaaa"
    assert item.organicResults[2].url == "https://developers.google.com/search/docs"
    # The rest of the block still parses off the same anchor.
    assert item.organicResults[0].displayedUrl == "https://example.com"
    assert item.organicResults[0].description == "A snippet."

    # A /goto URL lives on google.com but is always an outbound link, so the
    # "skip Google's own chrome" filters must not swallow these citations.
    assert item.peopleAlsoAsk[0].url == GOTO_PREFIX + "url=CAESfQHrOzAVaaa"
    assert item.peopleAlsoAsk[0].title == "Pie - Example"
    assert item.aiOverview.sources[0].url == GOTO_PREFIX + "url=CAESfQHrOzAVbbb"


async def test_resolve_rewrites_every_carrier_from_one_lookup(google_redirects):
    item = parse_serp(_SERP)

    assert await goto.resolve_item_urls(item) == 2

    assert [r.url for r in item.organicResults] == [
        "https://example.com/blog/pie",
        "https://second.example/history",
        "https://developers.google.com/search/docs",  # never a redirect
    ]
    # Citations resolve too, and the duplicate link shared with an organic
    # result is fetched once, not once per carrier.
    assert item.peopleAlsoAsk[0].url == "https://example.com/blog/pie"
    assert item.aiOverview.sources[0].url == "https://second.example/history"
    assert sorted(google_redirects) == sorted(_DESTINATIONS)


async def test_unresolvable_link_keeps_its_redirect_instead_of_vanishing(monkeypatch):
    """Degrade the url field, never drop the result."""

    async def _boom(url, **kwargs):
        raise TimeoutError("dead exit IP")

    monkeypatch.setattr(goto.AsyncFetcher, "get", _boom)

    item = parse_serp(_SERP)
    assert await goto.resolve_item_urls(item) == 0
    assert len(item.organicResults) == 3
    assert item.organicResults[0].url.startswith(GOTO_PREFIX)


async def test_resolve_is_free_when_no_redirects_are_present(google_redirects):
    item = parse_serp(
        '<html><body><div id="rso"><div class="tF2Cxc">'
        '<a href="https://x.example/a"><h3>Direct</h3></a>'
        "</div></div></body></html>"
    )
    assert await goto.resolve_item_urls(item) == 0
    assert google_redirects == []
