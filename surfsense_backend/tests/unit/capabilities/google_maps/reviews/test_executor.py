"""``google_maps.reviews`` executor: verb input → actor input mapping → typed items.

Boundary mocked: the proprietary scraper (injected fake). NOT mocked: the verb's
own payload→GoogleMapsReviewsInput mapping and the dict→ReviewItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.google_maps.reviews.executor import build_reviews_executor
from app.capabilities.google_maps.reviews.schemas import ReviewsInput, ReviewsOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.google_maps import GoogleMapsReviewsInput
from app.proprietary.platforms.google_maps.scraper import SignInRequiredError

pytestmark = pytest.mark.unit


class _FakeScraper:
    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[GoogleMapsReviewsInput] = []

    async def __call__(self, actor_input: GoogleMapsReviewsInput) -> list[dict]:
        self.calls.append(actor_input)
        return self._items


async def test_maps_urls_to_start_urls_and_wraps_items():
    scraper = _FakeScraper([{"text": "Great place", "stars": 5.0}])
    execute = build_reviews_executor(scrape_fn=scraper)

    out = await execute(ReviewsInput(urls=["https://www.google.com/maps/place/x"]))

    assert isinstance(out, ReviewsOutput)
    assert len(out.items) == 1
    assert out.items[0].text == "Great place"
    assert out.items[0].stars == 5.0

    (actor_input,) = scraper.calls
    assert [u.url for u in actor_input.startUrls] == [
        "https://www.google.com/maps/place/x"
    ]


async def test_forwards_place_ids_and_options():
    scraper = _FakeScraper([])
    execute = build_reviews_executor(scrape_fn=scraper)

    await execute(
        ReviewsInput(
            place_ids=["ChIJx"],
            max_reviews=50,
            sort_by="highestRanking",
            language="fr",
            start_date="2024-01-01",
        )
    )

    (actor_input,) = scraper.calls
    assert actor_input.placeIds == ["ChIJx"]
    assert actor_input.maxReviews == 50
    assert actor_input.reviewsSort == "highestRanking"
    assert actor_input.language == "fr"
    assert actor_input.reviewsStartDate == "2024-01-01"


async def test_sign_in_required_maps_to_forbidden_403():
    async def _raise(_actor_input):
        raise SignInRequiredError("wall hit")

    execute = build_reviews_executor(scrape_fn=_raise)

    with pytest.raises(ForbiddenError) as exc_info:
        await execute(ReviewsInput(place_ids=["ChIJx"]))
    assert exc_info.value.status_code == 403


async def test_other_faults_propagate_for_the_door_to_map():
    async def _boom(_actor_input):
        raise RuntimeError("proxy exploded")

    execute = build_reviews_executor(scrape_fn=_boom)

    with pytest.raises(RuntimeError):
        await execute(ReviewsInput(place_ids=["ChIJx"]))
