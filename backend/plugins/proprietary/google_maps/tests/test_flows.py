"""Request flows of the scrape and reviews tools, against a fake Google.

Google is faked at the scraper's network seam, the shared transport's
``http.request`` (see ``google_seam``): each answer takes a short while and the
fake records when every request started and ended, and on which kept session,
so the tests can tell requests that overlap from ones in series.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest

from proprietary.google_maps import fetch
from proprietary.google_maps.reviews import scrape_reviews
from proprietary.google_maps.schemas import (
    GoogleMapsReviewsInput,
    GoogleMapsScrapeInput,
)
from proprietary.google_maps.scraper import scrape_places
from proprietary.google_maps.tests.google_seam import Page, answer_with
from proprietary.scraping import http, sessions

_LATENCY_S = 0.05


def place(number: int) -> list[Any]:
    """One place ``darray`` at the positions Maps puts its fields."""
    darray: list[Any] = [None] * 184
    darray[4] = [None] * 9
    darray[4][7], darray[4][8] = 4.5, 100 + number
    darray[10] = f"0x{number:x}:0x{number + 100:x}"
    darray[11] = f"Cafe {number}"
    darray[13] = ["Coffee shop"]
    darray[18] = f"Cafe {number}, {number} Main St"
    darray[39] = f"{number} Main St"
    darray[78] = f"ChIJplace{number}"
    darray[89] = f"/g/kg{number}"
    return darray


def review(number: int) -> list[Any]:
    raw: list[Any] = [None] * 45
    raw[1] = 5
    raw[2] = ["a week ago", None, "1790000000000"]
    raw[3] = ["Ada", None, "https://www.google.com/maps/contrib/42", 3, 0, [None, 1]]
    raw[5] = f"r{number}"
    raw[27] = f"Good coffee {number}"
    return raw


def rpc(body: Any) -> Page:
    return Page(")]}'\n" + json.dumps(body))


@dataclass
class Call:
    url: str
    start: float
    end: float
    cookies: dict[str, str]
    session: Any = None  # the job's kept session; None for a fresh exit
    timeout: tuple[float, float] | None = None

    def overlaps(self, other: "Call") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class Google:
    """Answers Maps' requests after a short delay; keeps every request's timing."""

    calls: list[Call] = field(default_factory=list)
    search_places: tuple[int, ...] = (1, 2, 3)
    review_pages: int = 1
    # A URL part -> how many more requests for it Google refuses with a 429,
    # or that die on the way (a dead exit); and how much slower it answers once.
    refuse: dict[str, int] = field(default_factory=dict)
    dead: dict[str, int] = field(default_factory=dict)
    slow: dict[str, float] = field(default_factory=dict)
    latency: float = _LATENCY_S
    hedges: int = 0  # requests sent as a hedge, won or cancelled

    async def get(self, url: str, **kwargs: Any) -> Page:
        if http.HEDGE_INDEX.get():
            self.hedges += 1
        return await self._answer(url, **kwargs)

    async def _answer(self, url: str, **kwargs: Any) -> Page:
        loop = asyncio.get_running_loop()
        start = loop.time()
        slower = next((s for m, s in self.slow.items() if m in unquote(url)), 0.0)
        self.slow = {m: s for m, s in self.slow.items() if m not in unquote(url)}
        await asyncio.sleep(self.latency + slower)
        self.calls.append(
            Call(
                url,
                start,
                loop.time(),
                kwargs.get("cookies") or {},
                kwargs.get("session"),
                kwargs.get("timeout"),
            )
        )
        if self._spend(self.dead, url):
            raise http.TransportError("Timeout", 28, 5000.0, "timed out")
        if self._spend(self.refuse, url):
            return Page("<html>Our systems have detected unusual traffic</html>", 429)
        return self.answer(url)

    @staticmethod
    def _spend(left: dict[str, int], url: str) -> bool:
        marker = next((m for m, n in left.items() if n and m in unquote(url)), None)
        if marker is None:
            return False
        left[marker] -= 1
        return True

    def answer(self, url: str) -> Page:
        if "tbm=map" in url and "pb=" in url:
            entries = [place(n) for n in self.search_places]
            rows = [[None, 0], *([None] * 14 + [d] for d in entries)]
            return rpc([[None, rows if "!8i0!" in url and entries else []]])
        if "tbm=map" in url:  # the lite map-search page
            return Page("<html>/maps/place/x/data=!1s0x9:0x6d</html>")
        if "/maps/preview/place" in url:
            number = int(re.search(r"!1s0x([0-9a-f]+):", unquote(url)).group(1), 16)
            return rpc([None] * 6 + [place(number)])
        if "GetLocalBoqProxy" in url:
            later = '"t1"' in unquote(url)
            token = "t1" if self.review_pages > 1 and not later else None
            numbers = (3, 4) if later else (1, 2)
            node = [None, None, [review(n) for n in numbers], None, None, None, token]
            return rpc([None, [None] * 10 + [node]])
        if url.startswith("https://www.google.com/maps?"):
            return Page("", cookies={"NID": "minted"})
        if "place_id:ChIJplace" in url:
            number = int(url.rsplit("ChIJplace", 1)[1])
            return Page(f"<html>[0x{number:x}:0x{number + 100:x}]</html>")
        return Page("<html>a JS shell with no fid</html>")

    def asked(self, marker: str) -> list[Call]:
        return [c for c in self.calls if marker in unquote(c.url)]


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> Google:
    answers = Google()
    answer_with(monkeypatch, answers.get)
    return answers


@pytest.mark.asyncio
async def test_reviews_ask_for_the_header_and_reviews_together(google: Google) -> None:
    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=2)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2"]
    (page,) = google.asked("place_id:ChIJplace7")
    (header,) = google.asked("/maps/preview/place")
    (reviews,) = google.asked("GetLocalBoqProxy")
    assert page.end <= header.start and page.end <= reviews.start
    assert header.overlaps(reviews)


@pytest.mark.asyncio
async def test_review_items_carry_the_place_kgmid_and_bare_address(
    google: Google,
) -> None:
    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=1)
    )

    assert items[0]["kgmid"] == "/g/kg7"
    assert items[0]["address"] == "7 Main St"
    assert items[0]["fid"] == "0x7:0x6b"


@pytest.mark.asyncio
async def test_a_name_only_url_is_one_search_then_the_reviews(google: Google) -> None:
    google.search_places = (9,)

    items = await scrape_reviews(
        GoogleMapsReviewsInput(
            startUrls=[{"url": "https://www.google.com/maps/place/Cafe+9/"}],
            maxReviews=2,
        )
    )

    assert [item["title"] for item in items] == ["Cafe 9", "Cafe 9"]
    assert items[0]["kgmid"] == "/g/kg9"
    asked = [c.url for c in google.calls]
    assert len(asked) == 2
    assert "tbm=map" in asked[0] and "q=Cafe%209" in asked[0]
    assert "GetLocalBoqProxy" in asked[1]
    assert not google.asked("/maps/place/Cafe")
    assert not google.asked("/maps/preview/place")


@pytest.mark.asyncio
async def test_a_name_only_url_searches_around_its_coordinates(google: Google) -> None:
    google.search_places = (9,)
    url = "https://www.google.com/maps/place/Cafe+9/@40.7484405,-73.9856644,17z"

    await scrape_reviews(GoogleMapsReviewsInput(startUrls=[{"url": url}], maxReviews=1))

    (search,) = google.asked("tbm=map")
    assert "!2d-73.9856644!3d40.7484405" in search.url


@pytest.mark.asyncio
async def test_a_name_search_that_finds_nothing_falls_back_to_the_lite_page(
    google: Google,
) -> None:
    google.search_places = ()

    items = await scrape_reviews(
        GoogleMapsReviewsInput(
            startUrls=[{"url": "https://www.google.com/maps/place/Cafe+9/"}],
            maxReviews=1,
        )
    )

    assert items and items[0]["fid"] == "0x9:0x6d"
    assert [("pb=" in c.url) for c in google.asked("tbm=map")] == [True, False]
    assert not google.asked("/maps/place/Cafe")


@pytest.mark.asyncio
async def test_scrape_of_a_name_only_url_skips_the_page_get(google: Google) -> None:
    google.search_places = (9,)

    items = await scrape_places(
        GoogleMapsScrapeInput(
            startUrls=[{"url": "https://www.google.com/maps/place/Cafe+9/"}]
        )
    )

    assert [item["title"] for item in items] == ["Cafe 9"]
    assert [("tbm=map" in c.url, "/preview/place" in c.url) for c in google.calls] == [
        (True, False),
        (False, True),
    ]


@pytest.mark.asyncio
async def test_no_nid_is_minted_by_default(google: Google) -> None:
    await scrape_places(GoogleMapsScrapeInput(placeIds=["ChIJplace7"], maxReviews=1))

    assert not google.asked("https://www.google.com/maps?")
    (header,) = google.asked("/maps/preview/place")
    assert "NID" not in header.cookies
    assert header.cookies == fetch.CONSENT_COOKIES


@pytest.mark.asyncio
async def test_the_kill_switch_brings_the_nid_mint_back(
    google: Google, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch, "_SKIP_NID_MINT", False)
    monkeypatch.setattr(
        fetch, "_nid_pool", [{"value": None, "at": 0.0} for _ in range(3)]
    )

    await scrape_places(GoogleMapsScrapeInput(placeIds=["ChIJplace7"]))

    (mint,) = google.asked("https://www.google.com/maps?")
    (header,) = google.asked("/maps/preview/place")
    assert mint.end <= header.start
    assert header.cookies["NID"] == "minted"


@pytest.mark.asyncio
async def test_scrape_of_a_place_fetches_detail_and_reviews_together(
    google: Google,
) -> None:
    items = await scrape_places(
        GoogleMapsScrapeInput(placeIds=["ChIJplace7"], maxReviews=2)
    )

    assert [r["reviewId"] for r in items[0]["reviews"]] == ["r1", "r2"]
    (header,) = google.asked("/maps/preview/place")
    (reviews,) = google.asked("GetLocalBoqProxy")
    assert header.overlaps(reviews)


@pytest.mark.asyncio
async def test_search_with_details_fetches_each_detail_and_reviews_together(
    google: Google,
) -> None:
    items = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["coffee"],
            maxCrawledPlacesPerSearch=2,
            scrapePlaceDetailPage=True,
            maxReviews=1,
        )
    )

    assert [item["title"] for item in items] == ["Cafe 1", "Cafe 2"]
    assert all(len(item["reviews"]) == 1 for item in items)
    for number in (1, 2):
        (header,) = google.asked(f"!1s0x{number:x}:")
        (reviews,) = google.asked(f'"0x{number:x}:')
        assert header.overlaps(reviews)


@pytest.mark.asyncio
async def test_a_place_from_search_needs_no_place_id_page_later(
    google: Google,
) -> None:
    await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["coffee"], maxCrawledPlacesPerSearch=3
        )
    )
    google.calls.clear()

    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace2"], maxReviews=1)
    )

    assert items[0]["fid"] == "0x2:0x66"
    assert not google.asked("place_id:")


@pytest.mark.asyncio
async def test_a_resolved_place_id_is_not_fetched_twice(google: Google) -> None:
    request = GoogleMapsReviewsInput(placeIds=["ChIJplace5"], maxReviews=1)

    await scrape_reviews(request)
    await scrape_reviews(request)

    assert len(google.asked("place_id:ChIJplace5")) == 1


def test_the_fid_cache_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch, "_FID_CACHE_SIZE", 2)

    fetch.remember_fid("a", "0x1:0x1")
    fetch.remember_fid("b", "0x2:0x2")
    assert fetch.cached_fid("a") == "0x1:0x1"  # now the most recent
    fetch.remember_fid("c", "0x3:0x3")

    assert fetch.cached_fid("b") is None
    assert fetch.cached_fid("a") == "0x1:0x1"
    assert fetch.cached_fid("c") == "0x3:0x3"
    fetch.remember_place([None] * 10)  # no ids: nothing to keep
    assert len(fetch._fid_by_place_id) == 2


# Stage B: one kept session per job, rotation on refusal, hedging, parallel
# sources and the fail-fast transport.


@pytest.mark.asyncio
async def test_a_job_s_requests_share_one_kept_session(google: Google) -> None:
    await scrape_reviews(GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=2))

    sessions = {id(c.session) for c in google.calls}
    assert len(google.calls) == 3
    assert len(sessions) == 1 and google.calls[0].session is not None


@pytest.mark.asyncio
async def test_places_run_side_by_side_each_on_its_own_session(
    google: Google,
) -> None:
    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace1", "ChIJplace2"], maxReviews=2)
    )

    assert [item["title"] for item in items] == ["Cafe 1"] * 2 + ["Cafe 2"] * 2
    (first,) = google.asked("place_id:ChIJplace1")
    (second,) = google.asked("place_id:ChIJplace2")
    assert first.overlaps(second)
    assert first.session is not second.session


@pytest.mark.asyncio
async def test_scrape_sources_run_side_by_side_in_input_order(
    google: Google,
) -> None:
    google.slow = {"place_id:ChIJplace7": 0.2}  # the first source is the slowest

    items = await scrape_places(
        GoogleMapsScrapeInput(
            placeIds=["ChIJplace7", "ChIJplace8"],
            searchStringsArray=["coffee"],
            maxCrawledPlacesPerSearch=1,
        )
    )

    assert [item["title"] for item in items] == ["Cafe 7", "Cafe 8", "Cafe 1"]
    (slow,) = google.asked("place_id:ChIJplace7")
    (search,) = google.asked("tbm=map")
    assert slow.overlaps(search)


@pytest.mark.asyncio
async def test_a_refused_request_is_sent_again_on_a_new_exit(google: Google) -> None:
    google.refuse = {"/maps/preview/place": 1}

    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=1)
    )

    assert items[0]["title"] == "Cafe 7"
    refused, retried = google.asked("/maps/preview/place")
    assert refused.session is not retried.session


@pytest.mark.asyncio
async def test_a_dead_exit_is_left_for_a_new_one(google: Google) -> None:
    google.dead = {"GetLocalBoqProxy": 1}

    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=2)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2"]
    assert len(google.asked("GetLocalBoqProxy")) == 2


@pytest.mark.asyncio
async def test_a_place_refused_on_every_exit_is_an_error_item_without_a_browser(
    google: Google, monkeypatch: pytest.MonkeyPatch
) -> None:
    rendered: list[str] = []

    class Browser:
        @staticmethod
        def fetch(url: str, **_: Any) -> None:
            rendered.append(url)

    monkeypatch.setattr(fetch, "StealthyFetcher", Browser)
    google.refuse = {"place_id:ChIJplace8": 99}

    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7", "ChIJplace8"], maxReviews=1)
    )

    assert items[0]["title"] == "Cafe 7"
    assert items[1]["input"] == "ChIJplace8"
    assert "status 429" in items[1]["error"]
    assert len(google.asked("place_id:ChIJplace8")) == fetch._ATTEMPTS
    assert not rendered


@pytest.mark.asyncio
async def test_a_later_reviews_page_refused_keeps_the_pages_read(
    google: Google,
) -> None:
    google.review_pages = 2
    google.refuse = {'"t1"': 99}

    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=10)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2"]


@pytest.mark.asyncio
async def test_pages_follow_the_continuation_token(google: Google) -> None:
    google.review_pages = 2

    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=10)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2", "r3", "r4"]


@pytest.mark.asyncio
async def test_a_slow_request_is_sent_again_on_a_fresh_exit(
    google: Google, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch, "_HEDGE_AFTER_S", 0.1)
    google.slow = {"/maps/preview/place": 5.0}
    started = asyncio.get_running_loop().time()

    items = await scrape_places(GoogleMapsScrapeInput(placeIds=["ChIJplace7"]))

    assert items[0]["title"] == "Cafe 7"
    assert asyncio.get_running_loop().time() - started < 2.0
    (hedge,) = google.asked("/maps/preview/place")  # the slow one was cancelled
    assert hedge.session is None


@pytest.mark.asyncio
async def test_every_request_fails_fast(google: Google) -> None:
    await scrape_reviews(GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=1))

    assert {c.timeout for c in google.calls} == {fetch._TIMEOUT}
    assert sum(fetch._TIMEOUT) <= 15


@pytest.mark.asyncio
async def test_warm_sessions_are_lent_to_the_next_call_only_behind_the_flag(
    google: Google, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=1)
    await scrape_reviews(request)
    await scrape_reviews(request)
    off = {id(c.session) for c in google.calls}
    google.calls.clear()
    monkeypatch.setattr(fetch, "_KEEP_IDLE", True)
    try:
        await scrape_reviews(request)
        first = google.calls[-1].session
        await scrape_reviews(request)
    finally:
        await sessions.close_idle()

    assert len(off) == 2  # one session per call
    assert all(c.session is first for c in google.calls)


@pytest.mark.asyncio
async def test_the_keep_alive_kill_switch_sends_each_request_on_a_fresh_exit(
    google: Google, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch, "_KEEP_ALIVE", False)

    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=1)
    )

    assert items
    assert all(c.session is None for c in google.calls)


@pytest.mark.asyncio
async def test_stages_reach_the_caller(google: Google) -> None:
    heard: list[str] = []

    async def hear(message: str) -> None:
        heard.append(message)

    await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=2), on_stage=hear
    )

    assert "page fetched" in heard
    assert "reviews fetched" in heard
    assert "2 reviews read" in heard


def test_rpc_bodies_decode_past_a_wrapper_and_fail_soft() -> None:
    wrapped = b'<html><body><p>)]}\'\n[1, ["a"], {"b": 2}]</p></body></html>'

    assert fetch._decode_rpc_body(wrapped) == [1, ["a"], {"b": 2}]
    assert fetch._decode_rpc_body(b")]}'\n[1, [2") is None
    assert fetch._decode_rpc_body(b"no json here") is None


# One refused fetch costs its own field, never the source's other items.


@pytest.mark.asyncio
async def test_a_search_keeps_a_place_whose_detail_is_refused(google: Google) -> None:
    google.refuse = {"!1s0x2:": 99}  # place 2's detail, on every exit

    items = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["coffee"],
            maxCrawledPlacesPerSearch=3,
            scrapePlaceDetailPage=True,
        )
    )

    assert [(item["title"], item["rank"]) for item in items] == [
        ("Cafe 1", 1),
        ("Cafe 2", 2),
        ("Cafe 3", 3),
    ]
    assert not any("error" in item for item in items)
    assert len(google.asked("!1s0x2:")) == fetch._ATTEMPTS


@pytest.mark.asyncio
async def test_a_search_keeps_a_place_whose_reviews_are_refused(
    google: Google,
) -> None:
    google.refuse = {'"0x2:': 99}  # place 2's review feed, on every exit

    items = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["coffee"],
            maxCrawledPlacesPerSearch=3,
            scrapePlaceDetailPage=True,
            maxReviews=1,
        )
    )

    assert [item["title"] for item in items] == ["Cafe 1", "Cafe 2", "Cafe 3"]
    assert [len(item["reviews"]) for item in items] == [1, 0, 1]
    assert items[1]["reviewsCount"] == 102  # from the detail, not the empty feed


@pytest.mark.asyncio
async def test_a_place_whose_reviews_are_refused_is_kept(google: Google) -> None:
    google.refuse = {"GetLocalBoqProxy": 99}

    items = await scrape_places(
        GoogleMapsScrapeInput(placeIds=["ChIJplace7"], maxReviews=2)
    )

    assert [item["title"] for item in items] == ["Cafe 7"]
    assert items[0]["reviews"] == []


@pytest.mark.asyncio
async def test_a_refused_header_keeps_the_reviews(google: Google) -> None:
    google.refuse = {"/maps/preview/place": 99}

    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJplace7"], maxReviews=2)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2"]
    assert all("error" not in item for item in items)


@pytest.mark.asyncio
async def test_a_place_whose_detail_is_refused_is_still_an_error_item(
    google: Google,
) -> None:
    google.refuse = {"/maps/preview/place": 99}

    items = await scrape_places(GoogleMapsScrapeInput(placeIds=["ChIJplace7"]))

    assert [item["input"] for item in items] == ["ChIJplace7"]


# Hedges are for slow exits: a request waiting for a stream is not slow.


@pytest.mark.asyncio
async def test_an_enriched_search_with_reviews_hedges_no_queued_request(
    google: Google, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every answer takes 0.2 s, under the 0.3 s hedge delay; a request that
    # first waited for one of the session's streams would pass it.
    monkeypatch.setattr(fetch, "_HEDGE_AFTER_S", 0.3)
    monkeypatch.setattr(fetch, "_REVIEWS_HEDGE_AFTER_S", 0.3)
    google.latency = 0.2
    google.search_places = tuple(range(1, 21))

    items = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["coffee"],
            maxCrawledPlacesPerSearch=20,
            scrapePlaceDetailPage=True,
            maxReviews=1,
        )
    )

    assert [item["rank"] for item in items] == list(range(1, 21))
    assert google.hedges == 0
    assert len(google.calls) == 1 + 2 * 20


@pytest.mark.asyncio
async def test_reviews_wait_longer_than_other_requests_before_a_hedge(
    google: Google, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch, "_HEDGE_AFTER_S", 0.1)
    monkeypatch.setattr(fetch, "_REVIEWS_HEDGE_AFTER_S", 0.5)
    google.slow = {"/maps/preview/place": 0.3, "GetLocalBoqProxy": 0.3}

    await scrape_places(GoogleMapsScrapeInput(placeIds=["ChIJplace7"], maxReviews=1))

    assert google.hedges == 1  # the place RPC's; the reviews were not slow yet
    assert all(c.session is not None for c in google.asked("GetLocalBoqProxy"))


def _most_at_once(calls: list[Call]) -> int:
    edges = sorted([(c.start, 1) for c in calls] + [(c.end, -1) for c in calls])
    now = most = 0
    for _, step in edges:
        now += step
        most = max(most, now)
    return most


@pytest.mark.asyncio
async def test_one_call_keeps_its_requests_under_the_call_bound(
    google: Google,
) -> None:
    google.search_places = tuple(range(1, 9))

    items = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["a", "b", "c", "d", "e", "f"],
            maxCrawledPlacesPerSearch=8,
            scrapePlaceDetailPage=True,
        )
    )

    assert len(items) == 48
    assert google.hedges == 0
    assert _most_at_once(google.calls) > fetch._MAX_STREAMS
    assert _most_at_once(google.calls) <= fetch._CALL_MAX_IN_FLIGHT


# What reads as a refusal.


def _response(
    body: str, *, url: str = "https://www.google.com/maps/preview/place?pb=x", **kw
) -> http.RawResponse:
    return http.RawResponse(
        status=kw.get("status", 200),
        url=url,
        headers=kw.get("headers", {}),
        cookies={},
        body=body.encode(),
        history=(),
        timings=http.Timings(True, 0.0, 0.0, 0.0, 0.0, 0),
    )


def test_review_text_quoting_a_wall_is_not_a_refusal() -> None:
    quoted = [["Sign in to continue? No, see consent.google.com"]]

    assert not fetch._refused(_response(")]}'\n" + json.dumps(quoted)))


def test_a_query_naming_the_sorry_page_is_not_a_refusal() -> None:
    url = (
        "https://www.google.com/search?tbm=map&q=google.com%2Fsorry+consent.google.com"
    )
    raw = "https://www.google.com/search?q=google.com/sorry consent.google.com"

    assert not fetch._refused(_response(")]}'\n[]", url=url))
    assert not fetch._refused(_response(")]}'\n[]", url=raw))


@pytest.mark.parametrize(
    ("url", "location"),
    [
        ("https://www.google.com/sorry/index?continue=x", None),
        ("https://consent.google.com/ml?continue=x", None),
        ("https://www.google.com/maps/preview/place", "/sorry/index?continue=x"),
        ("https://www.google.com/maps", "https://consent.google.com/m?continue=x"),
    ],
)
def test_the_sorry_and_consent_pages_are_refusals(
    url: str, location: str | None
) -> None:
    headers = {"location": location} if location else {}

    assert fetch._refused(_response("<html></html>", url=url, headers=headers))


def test_a_sign_in_page_is_still_a_refusal() -> None:
    page = "<html><title>Before you continue to Google</title></html>"

    assert fetch._refused(_response(page, url="https://www.google.com/maps"))


# The GMP-3 watch: a detail with reviews but without the fields the NID unlocked.


@pytest.mark.asyncio
async def test_a_detail_without_its_review_fields_is_logged(
    google: Google, caplog: pytest.LogCaptureFixture
) -> None:
    before = fetch._field_loss

    await scrape_places(GoogleMapsScrapeInput(placeIds=["ChIJplace7"]))

    assert fetch._field_loss == before + 1
    assert "a place with 107 reviews has no distribution or tags" in caplog.text
    # Which place the user looked up stays out of the log.
    assert "0x7:0x6b" not in caplog.text
    assert "ChIJplace7" not in caplog.text


def test_a_full_detail_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    fixture = Path(__file__).parent / "fixtures" / "place_787coffee_darray.json"
    before = fetch._field_loss

    fetch._watch_field_loss(json.loads(fixture.read_text(encoding="utf-8")))

    assert fetch._field_loss == before
    assert "field loss" not in caplog.text
