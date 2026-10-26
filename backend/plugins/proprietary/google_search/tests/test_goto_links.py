"""Offline checks for Google's ``/goto`` outbound-result redirects.

Regression guard for the Jul-2026 rollout that emptied ``organicResults``:
Google replaced every outbound result ``href`` with an opaque
``/goto?url=<encrypted blob>`` redirect, and the parser only accepted anchors
whose href started with ``http``, so it skipped every block on the page. The
handful of results that survived were Google's own properties, which are not
wrapped — hence the "empty, or 1-2 results" symptom.

Two halves are pinned here: the parser must *see* redirect anchors as result
links, and :mod:`~proprietary.google_search.goto` must turn them
back into destinations by following the 302 (the blob is encrypted with a key
only Google holds, so there is no offline shortcut).
"""

import asyncio
import threading

import pytest

from proprietary.google_search import goto
from proprietary.google_search.parsers import GOTO_PREFIX, parse_serp
from proprietary.scraping import http

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


def _response(url: str, status: int, location: str | None = None) -> http.RawResponse:
    """A one-hop answer as the shared transport returns it."""
    fields = {
        "status": status,
        "url": url,
        "headers": {"location": location} if location else {},
        "cookies": {},
        "body": b"",
        "history": (),
        "timings": http.Timings(False, 0, 0, 0, 0, 0),
    }
    blocked = goto._blocked(http.RawResponse(**fields))
    return http.RawResponse(**fields, blocked=blocked)


@pytest.fixture
def google_redirects(monkeypatch):
    """Stub the one-hop redirect fetch, recording every URL it was asked for."""
    asked: list[str] = []

    async def _get(url, h, *, attempt):
        asked.append(url)
        destination = _DESTINATIONS.get(url)
        if destination is None:
            return _response(url, 200)  # a link Google would not resolve
        return _response(url, 302, destination)

    monkeypatch.setattr(goto, "_get", _get)
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

    async def _boom(url, h, *, attempt):
        raise http.TransportError("Timeout", 28, 4000.0, "dead exit IP")

    monkeypatch.setattr(goto, "_get", _boom)

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


# An AI Overview citing a page through its own /goto link, besides the one it
# shares with the organic result.
_GOTO_C = "/goto?url=CAESfQHrOzAVccc"
_SERP_WITH_OWN_CITATION = _SERP.replace(
    "</li></ul>",
    f"""</li><li class="Ioqnib">
      <a class="vIWmYe" aria-label="Pie Facts. Opens in new tab." href="{_GOTO_C}"></a>
      <div class="jdxGff"><span>Pie Facts</span></div>
      <span class="hxIQcc">Facts about pie.</span>
    </li></ul>""",
).replace('li class="h7wxwc"', 'li class="Ioqnib"')


async def test_ai_sources_are_not_fetched_when_switched_off(
    google_redirects, monkeypatch
):
    """GOOGLE_SEARCH_GOTO_AI_SOURCES=0 brings back stage A's default.

    Fetching them was off until the waves shared a session and ran during the
    render; this test pinned that old default and now pins the switch.
    """
    monkeypatch.setattr(goto, "_RESOLVE_AI_SOURCES", False)
    item = parse_serp(_SERP_WITH_OWN_CITATION)
    shared, own = item.aiOverview.sources

    await goto.resolve_item_urls(item)

    assert GOTO_PREFIX + _GOTO_C.removeprefix("/goto?") not in google_redirects
    assert own.url == GOTO_PREFIX + _GOTO_C.removeprefix("/goto?")
    assert own.site == "Pie Facts" and own.description == "Facts about pie."
    # A citation sharing an organic result's link is rewritten for free.
    assert shared.url == "https://second.example/history"


async def test_ai_sources_are_fetched_by_default(google_redirects):
    assert goto._RESOLVE_AI_SOURCES
    item = parse_serp(_SERP_WITH_OWN_CITATION)

    await goto.resolve_item_urls(item)

    assert GOTO_PREFIX + _GOTO_C.removeprefix("/goto?") in google_redirects


_LINK = GOTO_PREFIX + "url=CAESfQHrOzAVaaa"


async def test_a_slow_exit_is_hedged_on_a_fresh_one(monkeypatch):
    """GS-3: the first answer wins, so one slow exit no longer sets the tail."""
    monkeypatch.setattr(goto, "_HEDGE_AFTER_S", 0.05)
    calls: list[bool] = []

    async def _get(url, h, *, attempt):
        calls.append(h is not None)
        if h is not None:  # the wave's session sits on a slow exit
            await asyncio.sleep(5)
        return _response(url, 302, "https://fresh.example/")

    monkeypatch.setattr(goto, "_get", _get)

    started = asyncio.get_running_loop().time()
    assert await goto.resolve_links([_LINK]) == {_LINK: "https://fresh.example/"}
    assert asyncio.get_running_loop().time() - started < 2
    # The wave's session first, then the hedge on a new gateway connection.
    assert calls == [True, False]


async def test_a_refused_link_retries_once_on_a_fresh_exit(monkeypatch):
    """A 403, or a redirect to /sorry, is a refusal: one more try, new exit."""
    calls: list[tuple[bool, int]] = []

    async def _get(url, h, *, attempt):
        calls.append((h is not None, attempt))
        if attempt == 0:
            return _response(url, 302, "https://www.google.com/sorry/index?x")
        return _response(url, 302, "https://dest.example/")

    monkeypatch.setattr(goto, "_get", _get)

    assert await goto.resolve_links([_LINK]) == {_LINK: "https://dest.example/"}
    assert calls == [(True, 0), (False, 1)]


@pytest.mark.parametrize(
    ("location", "refused"),
    [
        ("https://www.google.com/sorry/index?continue=x", True),
        ("https://ipv4.google.com/sorry/index?continue=x", True),
        ("/sorry/index?continue=x", True),  # relative: the /goto's own host
        ("https://www.merriam-webster.com/dictionary/sorry", False),
        ("https://example.com/sorry/", False),
        ("https://example.com/?next=https://www.google.com/sorry/index", False),
        ("http://[malformed/sorry", False),
    ],
)
def test_only_google_s_sorry_page_is_a_refusal(location, refused):
    """The Location is the result's real destination, which can be any site."""
    assert _response(_LINK, 302, location).blocked is refused


async def test_attempts_stop_at_two(monkeypatch):
    calls: list[int] = []

    async def _get(url, h, *, attempt):
        calls.append(attempt)
        return _response(url, 403)

    monkeypatch.setattr(goto, "_get", _get)

    assert await goto.resolve_links([_LINK, _LINK]) == {_LINK: None}
    assert calls == [0, 1]  # one link, deduplicated; no hedge on a fast refusal


def test_the_goto_request_fails_fast():
    """GS-1: (connect, read) of (4, 6), each request one attempt."""
    assert goto._TIMEOUT == (4.0, 6.0)
    assert goto._ATTEMPTS == 2


async def test_links_fed_during_the_render_are_not_fetched_again(google_redirects):
    """The render feeds its links from the browser loop's thread; the parse
    then finds them resolved and fetches nothing more."""
    prefetch = goto.GotoPrefetch()
    feeder = threading.Thread(
        target=prefetch.feed, args=(["/goto?url=CAESfQHrOzAVaaa"],)
    )
    feeder.start()
    feeder.join()
    for _ in range(100):  # the wave starts on this loop, while "rendering"
        if google_redirects:
            break
        await asyncio.sleep(0.01)
    assert google_redirects == [_LINK]

    item = parse_serp(_SERP)
    prefetch.feed(["/goto?url=CAESfQHrOzAVbbb"])  # the post-expansion feed
    assert await goto.resolve_item_urls(item, prefetch=prefetch) == 2

    assert sorted(google_redirects) == sorted(_DESTINATIONS)  # each link once
    assert item.organicResults[0].url == "https://example.com/blog/pie"
    assert item.aiOverview.sources[0].url == "https://second.example/history"


async def test_a_link_that_failed_in_the_prefetch_keeps_its_redirect(monkeypatch):
    """It had its attempts during the render; retrying it after the parse
    would put its tail back on the critical path."""
    asked: list[str] = []

    async def _get(url, h, *, attempt):
        asked.append(url)
        return _response(url, 200)

    monkeypatch.setattr(goto, "_get", _get)
    prefetch = goto.GotoPrefetch()
    prefetch.feed(["/goto?url=CAESfQHrOzAVaaa"])

    item = parse_serp(_SERP)
    await goto.resolve_item_urls(item, prefetch=prefetch)

    assert asked.count(_LINK) == 2  # its two attempts, during the "render"
    assert item.organicResults[0].url == _LINK


async def test_a_discarded_render_s_links_are_dropped(monkeypatch):
    """A walled or failed render's waves are cancelled, its late feeds ignored."""
    started = asyncio.Event()

    async def _get(url, h, *, attempt):
        started.set()
        await asyncio.sleep(5)
        return _response(url, 302, "https://never.example/")

    monkeypatch.setattr(goto, "_get", _get)
    prefetch = goto.GotoPrefetch()
    prefetch.feed(["/goto?url=CAESfQHrOzAVaaa"])
    await asyncio.wait_for(started.wait(), 1)
    stale = prefetch._render
    prefetch.discard()
    prefetch._start([_LINK], stale)  # a feed the discarded render queued

    assert await asyncio.wait_for(prefetch.results(), 1) == {}


async def test_a_feed_after_close_starts_no_wave(monkeypatch):
    """A render still feeding as its call ends must not send /goto requests
    for a call that is over; a discard, by contrast, keeps taking feeds."""
    asked: list[str] = []

    async def _get(url, h, *, attempt):
        asked.append(url)
        return _response(url, 302, "https://dest.example/")

    monkeypatch.setattr(goto, "_get", _get)
    prefetch = goto.GotoPrefetch()
    prefetch.discard()
    prefetch.feed(["/goto?url=CAESfQHrOzAVaaa"])
    await asyncio.sleep(0)
    assert len(prefetch._waves) == 1  # the next render's feed still runs

    prefetch.close()
    prefetch.feed(["/goto?url=CAESfQHrOzAVbbb"])  # lands after the call ended
    await asyncio.sleep(0)
    assert len(prefetch._waves) == 1
    await asyncio.gather(*prefetch._waves, return_exceptions=True)
    assert GOTO_PREFIX + "url=CAESfQHrOzAVbbb" not in asked


async def test_the_wave_session_can_be_switched_off(monkeypatch):
    """GOOGLE_SEARCH_GOTO_WAVE_SESSION=0: each link one-off on a fresh exit."""
    holders: list[bool] = []

    async def _get(url, h, *, attempt):
        holders.append(h is not None)
        return _response(url, 302, "https://dest.example/")

    def no_holder(*args, **kwargs):
        raise AssertionError("no wave session when switched off")

    monkeypatch.setattr(goto, "_WAVE_SESSION", False)
    monkeypatch.setattr(goto, "_get", _get)
    monkeypatch.setattr(goto.sessions, "holder", no_holder)

    links = [GOTO_PREFIX + "url=a", GOTO_PREFIX + "url=b"]
    assert await goto.resolve_links(links) == dict.fromkeys(
        links, "https://dest.example/"
    )
    assert holders == [False, False]


class _Holder:
    """The wave's session; ``refuse`` makes its exit answer with /sorry."""

    def __init__(self, refuse: bool, destination: str = "https://dest.example/"):
        self.refuse = refuse
        self.destination = destination
        self.rotations = 0
        self.rotated: list[tuple[str, int | None]] = []

    async def request(self, method, url, *, stage, **kw):
        if self.refuse:
            return _response(url, 302, "https://www.google.com/sorry/index?x")
        return _response(url, 302, self.destination)

    async def rotate(self, reason, *, seen=None):
        self.rotated.append((reason, seen))


@pytest.mark.parametrize("refuse", [True, False])
async def test_a_refused_exit_rotates_the_wave_s_session(refuse):
    """The other links of the wave must not keep hitting the refusing IP."""
    h = _Holder(refuse)
    response = await goto._get(_LINK, h, attempt=0)
    assert response.blocked is refuse
    assert h.rotated == ([("blocked", 0)] if refuse else [])


async def test_a_destination_at_a_sorry_path_keeps_the_wave_s_exit():
    """A result's own /sorry page is an answer: no rotation, the link resolves."""
    h = _Holder(False, "https://www.merriam-webster.com/dictionary/sorry")
    response = await goto._get(_LINK, h, attempt=0)
    assert goto._answered(response)
    assert h.rotated == []
