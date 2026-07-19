from __future__ import annotations

from app.capabilities.walmart.reviews.executor import build_reviews_executor
from app.capabilities.walmart.reviews.schemas import ReviewsInput
from app.proprietary.platforms.walmart import WalmartReviewsInput


class _FakeScraper:
    def __init__(self) -> None:
        self.calls: list[tuple[WalmartReviewsInput, int | None]] = []

    async def __call__(
        self, input_model: WalmartReviewsInput, *, limit: int | None = None
    ) -> list[dict]:
        self.calls.append((input_model, limit))
        return [{"reviewId": "r1", "rating": 5}]


async def test_executor_maps_agent_input_to_scraper_input():
    scraper = _FakeScraper()
    execute = build_reviews_executor(scraper)

    output = await execute(
        ReviewsInput(
            urls=["https://www.walmart.com/ip/123456"],
            item_ids=["222"],
            max_reviews=50,
            sort_by="most-helpful",
        )
    )

    assert output.items[0].reviewId == "r1"
    input_model, limit = scraper.calls[0]
    assert input_model.itemIds == ["https://www.walmart.com/ip/123456", "222"]
    assert input_model.maxReviews == 50
    assert input_model.sort == "most-helpful"
    # limit is the pre-flight worst case: 2 sources * 50 reviews
    assert limit == 100
