from __future__ import annotations

from app.capabilities.amazon.scrape.executor import build_scrape_executor
from app.capabilities.amazon.scrape.schemas import MAX_AMAZON_RESULTS, ScrapeInput
from app.proprietary.platforms.amazon import AmazonScrapeInput


class _FakeScraper:
    def __init__(self) -> None:
        self.calls: list[tuple[AmazonScrapeInput, int | None]] = []

    async def __call__(
        self, input_model: AmazonScrapeInput, *, limit: int | None = None
    ) -> list[dict]:
        self.calls.append((input_model, limit))
        return [{"asin": "B09V3KXJPB", "title": "Product"}]


async def test_executor_maps_agent_input_to_scraper_input():
    scraper = _FakeScraper()
    execute = build_scrape_executor(scraper)

    output = await execute(
        ScrapeInput(
            search_terms=["wireless mouse"],
            urls=["https://www.amazon.com/dp/B09V3KXJPB"],
            max_items=5,
            max_offers=2,
            include_sellers=True,
            zip_code="10001",
            country_code="US",
        )
    )

    assert output.items[0].asin == "B09V3KXJPB"
    input_model, limit = scraper.calls[0]
    assert input_model.categoryOrProductUrls == [
        {"url": "https://www.amazon.com/dp/B09V3KXJPB"},
        {"url": "https://www.amazon.com/s?k=wireless+mouse"},
    ]
    assert input_model.maxItemsPerStartUrl == 5
    assert input_model.maxOffers == 2
    assert input_model.scrapeSellers is True
    assert input_model.zipCode == "10001"
    assert limit == MAX_AMAZON_RESULTS
