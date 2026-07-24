"""Manual end-to-end check for the public Amazon scraper.

Run from the backend directory:

    uv run python scripts/e2e_amazon_scraper.py
    uv run python scripts/e2e_amazon_scraper.py --refresh-fixtures

The script requires live network access and the configured residential proxy.
The optional flag replaces the product and search parser fixtures with current
live responses. The script is intentionally excluded from pytest.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))
for _candidate in (_BACKEND_ROOT / ".env", _BACKEND_ROOT.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from app.proprietary.platforms.amazon import (  # noqa: E402
    AmazonScrapeInput,
    scrape_products,
)
from app.proprietary.platforms.amazon.fetch import fetch_page  # noqa: E402

_PRODUCT_URL = "https://www.amazon.com/dp/B09V3KXJPB"
_SEARCH_URL = "https://www.amazon.com/s?k=wireless+mouse"
_FIXTURE_DIR = _BACKEND_ROOT / "tests" / "unit" / "platforms" / "amazon" / "fixtures"


def _check(label: str, passed: bool) -> bool:
    print(f"[{'PASS' if passed else 'FAIL'}] {label}")
    return passed


async def main() -> int:
    product_items = await scrape_products(
        AmazonScrapeInput(categoryOrProductUrls=[{"url": _PRODUCT_URL}]),
        limit=1,
    )
    product = product_items[0] if product_items else {}
    print(json.dumps(product, indent=2, ensure_ascii=False)[:3000])
    product_ok = _check(
        "product detail has identity and title",
        bool(product.get("asin") and product.get("title")),
    )

    search_items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": _SEARCH_URL}],
            maxItemsPerStartUrl=3,
            scrapeProductDetails=False,
        )
    )
    search_ok = _check(
        "search returns product cards",
        bool(search_items)
        and all(
            item.get("asin") and item.get("categoryPageData") for item in search_items
        ),
    )
    fixture_ok = True
    if "--refresh-fixtures" in sys.argv:
        _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        for name, url in (("product.html", _PRODUCT_URL), ("search.html", _SEARCH_URL)):
            response = await fetch_page(url)
            saved = response is not None and response.status == 200
            if saved:
                (_FIXTURE_DIR / name).write_text(response.html, encoding="utf-8")
            fixture_ok &= _check(f"refreshed {name}", saved)
    return 0 if product_ok and search_ok and fixture_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
