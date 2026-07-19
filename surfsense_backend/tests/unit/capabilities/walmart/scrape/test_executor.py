from __future__ import annotations

from app.capabilities.walmart.scrape.executor import build_scrape_executor
from app.capabilities.walmart.scrape.schemas import MAX_WALMART_RESULTS, ScrapeInput
from app.proprietary.platforms.walmart import WalmartScrapeInput


class _FakeScraper:
    def __init__(self) -> None:
        self.calls: list[tuple[WalmartScrapeInput, int | None]] = []

    async def __call__(
        self, input_model: WalmartScrapeInput, *, limit: int | None = None
    ) -> list[dict]:
        self.calls.append((input_model, limit))
        return [{"usItemId": "123", "name": "Product"}]


async def test_executor_maps_agent_input_to_scraper_input():
    scraper = _FakeScraper()
    execute = build_scrape_executor(scraper)

    output = await execute(
        ScrapeInput(
            search_terms=["air fryer"],
            urls=["https://www.walmart.com/ip/123456"],
            max_items=5,
            include_details=False,
            include_reviews_sample=False,
        )
    )

    assert output.items[0].usItemId == "123"
    input_model, limit = scraper.calls[0]
    assert input_model.startUrls == [
        "https://www.walmart.com/ip/123456",
        "https://www.walmart.com/search?q=air+fryer",
    ]
    assert input_model.maxItemsPerStartUrl == 5
    assert input_model.includeDetails is False
    assert input_model.includeReviewsSample is False
    assert limit == MAX_WALMART_RESULTS
