"""Manual end-to-end check for the public Walmart scraper.

Run from the backend directory:

    uv run python scripts/e2e_walmart_scraper.py

The script requires live network access and the configured residential proxy
(US exit). It is intentionally excluded from pytest.
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

from app.proprietary.platforms.walmart import (  # noqa: E402
    WalmartReviewsInput,
    WalmartScrapeInput,
    scrape_products,
    scrape_reviews,
)

_PRODUCT_URL = "https://www.walmart.com/ip/212092810"
_SEARCH_URL = "https://www.walmart.com/search?q=air+fryer"


def _check(label: str, passed: bool) -> bool:
    print(f"[{'PASS' if passed else 'FAIL'}] {label}")
    return passed


async def main() -> int:
    ok = True

    product_items = await scrape_products(
        WalmartScrapeInput(startUrls=[_PRODUCT_URL]), limit=1
    )
    product = product_items[0] if product_items else {}
    print(json.dumps(product, indent=2, ensure_ascii=False)[:2500])
    ok &= _check(
        "product detail has id and name",
        bool(product.get("usItemId") and product.get("name")),
    )

    search_items = await scrape_products(
        WalmartScrapeInput(
            startUrls=[_SEARCH_URL], maxItemsPerStartUrl=3, includeDetails=False
        ),
        limit=3,
    )
    ok &= _check(
        "search returns product cards",
        bool(search_items) and any("name" in item for item in search_items),
    )

    item_id = product.get("usItemId") or "212092810"
    reviews = await scrape_reviews(
        WalmartReviewsInput(itemIds=[item_id], maxReviews=15), limit=15
    )
    ok &= _check(
        "reviews returned with rating and text",
        bool(reviews) and any(r.get("rating") and r.get("text") for r in reviews),
    )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
