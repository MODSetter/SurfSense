"""``google_maps.scrape`` executor: verb input → actor input mapping → typed items.

Boundary mocked: the proprietary scraper (injected fake). NOT mocked: the verb's
own payload→GoogleMapsScrapeInput mapping and the dict→PlaceItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.google_maps.scrape.executor import build_scrape_executor
from app.capabilities.google_maps.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.google_maps import GoogleMapsScrapeInput
from app.proprietary.platforms.google_maps.scraper import SignInRequiredError

pytestmark = pytest.mark.unit


class _FakeScraper:
    """Records the actor input it was called with and returns canned items."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[GoogleMapsScrapeInput] = []

    async def __call__(self, actor_input: GoogleMapsScrapeInput) -> list[dict]:
        self.calls.append(actor_input)
        return self._items


async def test_maps_queries_and_wraps_items():
    scraper = _FakeScraper([{"title": "Blue Bottle", "placeId": "abc"}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(search_queries=["coffee"], location="Austin"))

    assert isinstance(out, ScrapeOutput)
    assert len(out.items) == 1
    assert out.items[0].title == "Blue Bottle"
    assert out.items[0].placeId == "abc"

    (actor_input,) = scraper.calls
    assert actor_input.searchStringsArray == ["coffee"]
    assert actor_input.locationQuery == "Austin"


async def test_maps_urls_and_place_ids():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(
        ScrapeInput(
            urls=["https://www.google.com/maps/place/x"],
            place_ids=["ChIJxxxx"],
        )
    )

    (actor_input,) = scraper.calls
    assert [u.url for u in actor_input.startUrls] == [
        "https://www.google.com/maps/place/x"
    ]
    assert actor_input.placeIds == ["ChIJxxxx"]


async def test_max_places_maps_to_per_search_cap():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(ScrapeInput(search_queries=["x"], max_places=25))

    (actor_input,) = scraper.calls
    assert actor_input.maxCrawledPlacesPerSearch == 25


async def test_forwards_detail_review_and_image_options():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(
        ScrapeInput(
            search_queries=["x"],
            include_details=True,
            max_reviews=5,
            max_images=3,
            language="fr",
        )
    )

    (actor_input,) = scraper.calls
    assert actor_input.scrapePlaceDetailPage is True
    assert actor_input.maxReviews == 5
    assert actor_input.maxImages == 3
    assert actor_input.language == "fr"


async def test_sign_in_required_maps_to_forbidden_403():
    async def _raise(_actor_input):
        raise SignInRequiredError("wall hit")

    execute = build_scrape_executor(scrape_fn=_raise)

    with pytest.raises(ForbiddenError) as exc_info:
        await execute(ScrapeInput(search_queries=["x"]))
    assert exc_info.value.status_code == 403


async def test_other_faults_propagate_for_the_door_to_map():
    async def _boom(_actor_input):
        raise RuntimeError("proxy exploded")

    execute = build_scrape_executor(scrape_fn=_boom)

    with pytest.raises(RuntimeError):
        await execute(ScrapeInput(search_queries=["x"]))
