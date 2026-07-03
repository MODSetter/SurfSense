"""Manual functional e2e for the Google Maps scraper (app/proprietary/scrapers/google_maps).

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/e2e_google_maps_scraper.py
    # or: .\\.venv\\Scripts\\python.exe scripts/e2e_google_maps_scraper.py

NOT a pytest test (needs live network + optional proxy creds). It:
  Step 1 — scrapes a known place URL and prints the core fields.
  Step 2 — scrapes the same place by bare placeId (HTML -> fid -> RPC path).
  Step 3 — dumps the raw place darray (jd[6] of /maps/preview/place) to
      tests/unit/scrapers/google_maps/fixtures/ for the offline parser test.
  Step 4 — scrapes reviews via the Reviews endpoint (BOQ feed), checks fields.
  Step 5 — paginates past one page (maxReviews=15) and checks the count.
  Step 6 — place scrape with maxReviews>0 attaches inline reviews[].
  Step 7 — dumps a raw BOQ reviews page fixture for the offline parser test.
  Step 8 — search discovery (searchStringsArray + locationQuery), checks items.
  Step 9 — dumps a raw map-search response fixture for the offline parser test.
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# Windows consoles default to cp1252; reviews/ratings contain non-latin chars.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))
for _candidate in (_BACKEND_ROOT / ".env", _BACKEND_ROOT.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from app.proprietary.scrapers.google_maps import (  # noqa: E402
    GoogleMapsReviewsInput,
    GoogleMapsScrapeInput,
    scrape_places,
    scrape_reviews,
)
from app.proprietary.scrapers.google_maps.fetch import (  # noqa: E402
    build_search_url,
    fetch_place_darray,
    fetch_rpc_json,
    iter_reviews_pages,
)
from app.proprietary.scrapers.google_maps.url_resolver import extract_fid  # noqa: E402

# A well-known, stable place (the restaurant used in the Apify output example).
_PLACE_URL = (
    "https://www.google.com/maps/place/Kim's+Island/"
    "@40.5107736,-74.2482624,17z/data=!4m6!3m5!1s0x89c3ca9c11f90c25:"
    "0x6cc8dba851799f09!8m2!3d40.5107736!4d-74.2482624!16s%2Fg%2F1tmgdcj8?hl=en"
)

_FIXTURE_DIR = (
    _BACKEND_ROOT / "tests" / "unit" / "scrapers" / "google_maps" / "fixtures"
)


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{f' — {detail}' if detail else ''}")
    return ok


async def step1_place() -> bool:
    _hr("STEP 1 — scrape a known place URL")
    items = await scrape_places(GoogleMapsScrapeInput(startUrls=[{"url": _PLACE_URL}]))
    if not items:
        return _check("place scraped", False, "no items returned")
    it = items[0]
    print(json.dumps(it, indent=2, ensure_ascii=False)[:2500])
    ok = bool(it.get("title")) and it.get("placeId") is not None
    return _check(
        "place has title + placeId",
        ok,
        f"{it.get('title')!r} / {it.get('totalScore')}★ / {it.get('reviewsCount')} reviews",
    )


async def step2_place_id() -> bool:
    _hr("STEP 2 — scrape by bare placeId (HTML -> fid -> RPC path)")
    items = await scrape_places(
        GoogleMapsScrapeInput(placeIds=["ChIJJQz5EZzKw4kRCZ95UajbyGw"])
    )
    if not items:
        return _check("placeId scraped", False, "no items returned")
    it = items[0]
    return _check(
        "placeId resolves to same place",
        it.get("title") == "Kim's Island",
        f"{it.get('title')!r}",
    )


async def step3_dump_fixture() -> bool:
    _hr("STEP 3 — dump raw place darray fixture for offline test")
    fid = extract_fid(_PLACE_URL)
    if not fid:
        return _check("extracted fid from URL", False)
    darray = await fetch_place_darray(fid)
    if not darray:
        return _check("fetched place darray via RPC", False)
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (_FIXTURE_DIR / "place_darray.json").write_text(
        json.dumps(darray), encoding="utf-8"
    )
    return _check("dumped fixture", True, f"-> {_FIXTURE_DIR / 'place_darray.json'}")


async def step4_reviews() -> bool:
    _hr("STEP 4 — reviews endpoint (one page, newest first)")
    items = await scrape_reviews(
        GoogleMapsReviewsInput(startUrls=[{"url": _PLACE_URL}], maxReviews=5)
    )
    if not items:
        return _check("reviews returned", False, "no items")
    it = items[0]
    print(json.dumps(it, indent=2, ensure_ascii=False)[:1800])
    ok = (
        bool(it.get("name"))
        and it.get("stars") is not None
        and bool(it.get("reviewId"))
        and it.get("title") == "Kim's Island"  # place header stamped on
        and bool(it.get("publishedAtDate"))
    )
    return _check(
        "review has author/stars/id/place header",
        ok and len(items) == 5,
        f"{len(items)} reviews, first by {it.get('name')!r} ({it.get('stars')}★)",
    )


async def step5_pagination() -> bool:
    _hr("STEP 5 — pagination past one page (maxReviews=15)")
    items = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=["ChIJJQz5EZzKw4kRCZ95UajbyGw"], maxReviews=15)
    )
    dates = [i.get("publishedAtDate") for i in items[:3]]
    return _check(
        "got 15 reviews across >1 page",
        len(items) == 15,
        f"{len(items)} reviews; newest: {dates}",
    )


async def step6_inline_reviews() -> bool:
    _hr("STEP 6 — place scrape with maxReviews=3 attaches inline reviews[]")
    items = await scrape_places(
        GoogleMapsScrapeInput(startUrls=[{"url": _PLACE_URL}], maxReviews=3)
    )
    if not items:
        return _check("place scraped", False, "no items")
    reviews = items[0].get("reviews") or []
    return _check(
        "place item carries 3 inline reviews",
        len(reviews) == 3 and bool(reviews[0].get("name")),
        f"{len(reviews)} reviews inline",
    )


async def step7_dump_reviews_fixture() -> bool:
    _hr("STEP 7 — dump raw BOQ reviews page fixture for offline test")
    fid = extract_fid(_PLACE_URL)
    async for raw_page in iter_reviews_pages(fid, sort="newest", max_pages=1):
        _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        (_FIXTURE_DIR / "boq_reviews_page.json").write_text(
            json.dumps(raw_page), encoding="utf-8"
        )
        return _check(
            "dumped fixture",
            len(raw_page) > 0,
            f"{len(raw_page)} reviews -> {_FIXTURE_DIR / 'boq_reviews_page.json'}",
        )
    return _check("fetched a reviews page", False)


async def step8_search() -> bool:
    _hr("STEP 8 — search discovery (query + locationQuery)")
    items = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["coffee shop"],
            locationQuery="Seattle, WA",
            maxCrawledPlacesPerSearch=5,
        )
    )
    if not items:
        return _check("search returned items", False, "no items")
    it = items[0]
    print(json.dumps(it, indent=2, ensure_ascii=False)[:1500])
    ok = (
        len(items) == 5
        and all(i.get("title") and i.get("placeId") and i.get("fid") for i in items)
        and [i.get("rank") for i in items] == [1, 2, 3, 4, 5]
        and it.get("searchString") == "coffee shop"
    )
    return _check(
        "5 ranked places with title/placeId/fid",
        ok,
        f"first: {it.get('title')!r} ({it.get('totalScore')}★, {it.get('city')})",
    )


async def step9_dump_search_fixture() -> bool:
    _hr("STEP 9 — dump raw map-search response fixture for offline test")
    url = build_search_url("pizza new york")
    jd = await fetch_rpc_json(url)
    if not isinstance(jd, list):
        return _check("fetched search response", False)
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (_FIXTURE_DIR / "search_response.json").write_text(json.dumps(jd), encoding="utf-8")
    return _check("dumped fixture", True, f"-> {_FIXTURE_DIR / 'search_response.json'}")


async def main() -> int:
    results = [
        await step1_place(),
        await step2_place_id(),
        await step3_dump_fixture(),
        await step4_reviews(),
        await step5_pagination(),
        await step6_inline_reviews(),
        await step7_dump_reviews_fixture(),
        await step8_search(),
        await step9_dump_search_fixture(),
    ]
    _hr("SUMMARY")
    print(f"  {sum(results)}/{len(results)} steps passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
