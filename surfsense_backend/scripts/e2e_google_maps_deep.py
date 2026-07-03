"""Deep functional verification for the Google Maps scraper (live network).

Complements the fast smoke e2e (e2e_google_maps_scraper.py) with breadth:
diverse places (countries, scripts, categories), URL-kind coverage (name-only
URLs, CID), and review semantics (sort order, date cutoff, pagination
uniqueness, personal-data stripping, localization).

Verification style: ground-truth invariants instead of screenshots — known
coordinates/websites/address keywords for world-famous places, and internal
consistency rules (newest sort is monotonically non-increasing, cutoff dates
hold, review IDs are unique across pages, etc.).

Run from the backend directory:
    .\\.venv\\Scripts\\python.exe scripts/e2e_google_maps_deep.py
"""

import asyncio
import itertools
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

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

_CHECKS: list[tuple[str, bool, str]] = []


def _check(label: str, ok: bool, detail: str = "") -> bool:
    _CHECKS.append((label, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{f' — {detail}' if detail else ''}")
    return ok


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _near(actual: float | None, expected: float, tol: float = 0.05) -> bool:
    return actual is not None and abs(actual - expected) <= tol


def _iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


# Ground truth: world-famous places whose facts don't drift. Name-only URLs
# exercise the HTML -> fid resolution path for every one of them.
_PLACES = [
    {
        "label": "Eiffel Tower (FR landmark)",
        "url": "https://www.google.com/maps/place/Eiffel+Tower/",
        "title_contains": "eiffel",
        "lat": 48.8584,
        "lng": 2.2945,
        "address_contains": ["paris", "75007", "france"],
        "website_contains": "toureiffel",
    },
    {
        "label": "Tokyo Tower (JP, non-Latin locale)",
        "url": "https://www.google.com/maps/place/Tokyo+Tower/",
        "title_contains": "tokyo tower",
        "lat": 35.6586,
        "lng": 139.7454,
        "address_contains": ["tokyo", "japan", "minato"],
    },
    {
        "label": "Sydney Opera House (AU)",
        "url": "https://www.google.com/maps/place/Sydney+Opera+House/",
        "title_contains": "opera house",
        "lat": -33.8568,
        "lng": 151.2153,
        "address_contains": ["sydney", "nsw", "australia"],
    },
    {
        "label": "The Plaza Hotel (US hotel category)",
        "url": "https://www.google.com/maps/place/The+Plaza+Hotel+New+York/",
        "title_contains": "plaza",
        "lat": 40.7646,
        "lng": -73.9744,
        "address_contains": ["new york", "ny"],
        "category_contains": "hotel",
    },
]

_KIMS_CID_URL = "https://maps.google.com/?cid=7838756667406262025"  # Kim's Island
_KIMS_PLACE_ID = "ChIJJQz5EZzKw4kRCZ95UajbyGw"
_LOUVRE_URL = "https://www.google.com/maps/place/Louvre+Museum/"


async def scrape_one(url: str, **kwargs) -> dict | None:
    items = await scrape_places(
        GoogleMapsScrapeInput(startUrls=[{"url": url}], **kwargs)
    )
    return items[0] if items else None


async def step_diverse_places() -> None:
    _hr("A — diverse places via name-only URLs (HTML -> fid path)")
    for spec in _PLACES:
        it = await scrape_one(spec["url"])
        if it is None:
            _check(spec["label"], False, "no item returned")
            continue
        title = (it.get("title") or "").lower()
        loc = it.get("location") or {}
        addr = (it.get("address") or "").lower()
        problems = []
        if spec["title_contains"] not in title:
            problems.append(f"title={it.get('title')!r}")
        if not _near(loc.get("lat"), spec["lat"]) or not _near(
            loc.get("lng"), spec["lng"]
        ):
            problems.append(f"loc={loc}")
        if not any(k in addr for k in spec["address_contains"]):
            problems.append(f"address={it.get('address')!r}")
        if not it.get("placeId"):
            problems.append("no placeId")
        if not it.get("categories"):
            problems.append("no categories")
        if spec.get("website_contains") and spec["website_contains"] not in (
            it.get("website") or ""
        ):
            problems.append(f"website={it.get('website')!r}")
        if (
            spec.get("category_contains")
            and spec["category_contains"]
            not in (
                (it.get("categoryName") or "") + " ".join(it.get("categories") or [])
            ).lower()
        ):
            problems.append(f"categories={it.get('categories')}")
        _check(
            spec["label"],
            not problems,
            "; ".join(problems)
            or f"{it.get('title')!r} @ ({loc.get('lat'):.4f},{loc.get('lng'):.4f}) "
            f"cat={it.get('categoryName')!r} score={it.get('totalScore')}",
        )


async def step_cid_url() -> None:
    _hr("B — CID URL dispatch")
    it = await scrape_one(_KIMS_CID_URL)
    ok = it is not None and it.get("title") == "Kim's Island"
    _check(
        "?cid=... resolves to the right place",
        ok,
        f"title={it.get('title')!r}" if it else "no item",
    )
    if it:
        _check(
            "cid place has full detail (phone+hours)",
            bool(it.get("phone")) and bool(it.get("openingHours")),
            f"phone={it.get('phone')!r}, hours={len(it.get('openingHours') or [])} days",
        )


async def step_review_sorts() -> None:
    _hr("C — review sort semantics (Kim's Island)")
    newest = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=[_KIMS_PLACE_ID], maxReviews=10)
    )
    dates = [_iso(r.get("publishedAtDate")) for r in newest]
    dated = [d for d in dates if d]
    _check(
        "newest: publishedAtDate non-increasing",
        len(dated) >= 5 and all(a >= b for a, b in itertools.pairwise(dated)),
        f"{len(newest)} reviews, first={newest[0].get('publishAt') if newest else None}",
    )

    lowest = await scrape_reviews(
        GoogleMapsReviewsInput(
            placeIds=[_KIMS_PLACE_ID], maxReviews=10, reviewsSort="lowestRanking"
        )
    )
    highest = await scrape_reviews(
        GoogleMapsReviewsInput(
            placeIds=[_KIMS_PLACE_ID], maxReviews=10, reviewsSort="highestRanking"
        )
    )
    lo = [r["stars"] for r in lowest if r.get("stars")]
    hi = [r["stars"] for r in highest if r.get("stars")]
    lo_avg = sum(lo) / len(lo) if lo else 0
    hi_avg = sum(hi) / len(hi) if hi else 0
    _check(
        "lowestRanking avg < highestRanking avg",
        bool(lo and hi) and lo_avg < hi_avg,
        f"lowest avg={lo_avg:.2f} (first={lo[:3]}), highest avg={hi_avg:.2f} (first={hi[:3]})",
    )
    _check(
        "highestRanking page is all 5 stars",
        bool(hi) and all(s == 5 for s in hi),
        f"stars={hi}",
    )


async def step_start_date_cutoff() -> None:
    _hr("D — reviewsStartDate cutoff")
    baseline = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=[_KIMS_PLACE_ID], maxReviews=10)
    )
    dated = [(_iso(r.get("publishedAtDate")), r) for r in baseline]
    dated = [(d, r) for d, r in dated if d]
    if len(dated) < 6:
        _check("cutoff test has enough dated reviews", False, f"only {len(dated)}")
        return
    # Cut between the 4th and 5th newest review -> expect exactly 4 back.
    cutoff_dt = dated[4][0]
    cutoff = (
        dated[3][0].strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if dated[3][0] == cutoff_dt
        else cutoff_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    )
    got = await scrape_reviews(
        GoogleMapsReviewsInput(
            placeIds=[_KIMS_PLACE_ID], maxReviews=100, reviewsStartDate=cutoff
        )
    )
    got_dates = [_iso(r.get("publishedAtDate")) for r in got]
    cutoff_parsed = _iso(cutoff)
    _check(
        "all returned reviews >= cutoff",
        bool(got) and all(d is None or d >= cutoff_parsed for d in got_dates),
        f"cutoff={cutoff}, returned={len(got)} (expected ~4)",
    )
    _check(
        "cutoff actually limits the result",
        0 < len(got) < len(baseline) + 1 and len(got) <= 6,
        f"{len(got)} vs baseline {len(baseline)}",
    )


async def step_personal_data() -> None:
    _hr("E — personalData=false stripping")
    items = await scrape_reviews(
        GoogleMapsReviewsInput(
            placeIds=[_KIMS_PLACE_ID], maxReviews=3, personalData=False
        )
    )
    if not items:
        _check("reviews returned", False)
        return
    leaked = [
        k
        for k in ("name", "reviewerId", "reviewerUrl", "reviewerPhotoUrl")
        if any(r.get(k) for r in items)
    ]
    _check(
        "reviewer identity fields are absent",
        not leaked,
        f"leaked={leaked}" if leaked else f"{len(items)} reviews, ids+stars kept",
    )
    _check(
        "non-personal fields survive",
        all(r.get("reviewId") and r.get("stars") for r in items),
    )


async def step_localization() -> None:
    _hr("F — localization (language=fr)")
    items = await scrape_reviews(
        GoogleMapsReviewsInput(
            startUrls=[{"url": "https://www.google.com/maps/place/Eiffel+Tower/"}],
            maxReviews=5,
            language="fr",
        )
    )
    if not items:
        _check("french reviews returned", False)
        return
    rel = [r.get("publishAt") or "" for r in items]
    french = [s for s in rel if "il y a" in s or "mois" in s or "semaine" in s]
    _check(
        "relative dates come back in French",
        len(french) >= 3,
        f"publishAt={rel}",
    )
    _check(
        "items stamped language=fr",
        all(r.get("language") == "fr" for r in items),
    )


async def step_big_place_pagination() -> None:
    _hr("G — big place, 30 reviews across >=3 pages (Louvre)")
    items = await scrape_reviews(
        GoogleMapsReviewsInput(startUrls=[{"url": _LOUVRE_URL}], maxReviews=30)
    )
    ids = [r.get("reviewId") for r in items]
    _check(
        "30 reviews with unique IDs",
        len(items) == 30 and len(set(ids)) == 30,
        f"{len(items)} reviews, {len(set(ids))} unique",
    )
    ok_fields = all(
        r.get("name") and r.get("stars") is not None and r.get("publishedAtDate")
        for r in items
    )
    _check("every review has author/stars/date", ok_fields)
    _check(
        "place header stamped on all (Louvre)",
        all("louvre" in (r.get("title") or "").lower() for r in items),
        f"title={items[0].get('title')!r}" if items else "",
    )


async def step_search_discovery() -> None:
    _hr("I — search discovery: paging, rank, dedupe (pizza in New York)")
    items = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["pizza"],
            locationQuery="New York, NY",
            maxCrawledPlacesPerSearch=25,
        )
    )
    fids = [i.get("fid") for i in items]
    _check(
        "25 places across >1 page, all unique fids",
        len(items) == 25 and len(set(fids)) == 25,
        f"{len(items)} items, {len(set(fids))} unique",
    )
    _check(
        "ranks are 1..25 in order",
        [i.get("rank") for i in items] == list(range(1, 26)),
    )
    ny = sum(
        1
        for i in items
        if i.get("location")
        and 40.4 < (i["location"]["lat"] or 0) < 41.1
        and -74.3 < (i["location"]["lng"] or 0) < -73.6
    )
    _check(
        "locationQuery scopes results to NYC",
        ny >= 23,
        f"{ny}/25 within NYC bounds",
    )
    with_core = sum(
        1 for i in items if i.get("title") and i.get("placeId") and i.get("address")
    )
    _check("all items have title/placeId/address", with_core == 25, f"{with_core}/25")


async def step_search_filters() -> None:
    _hr("J — search filters (stars, website, matching)")
    starred = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["restaurant"],
            locationQuery="Chicago, IL",
            maxCrawledPlacesPerSearch=10,
            placeMinimumStars="fourAndHalf",
        )
    )
    scores = [i.get("totalScore") for i in starred]
    _check(
        "placeMinimumStars=fourAndHalf holds",
        bool(scores) and all(s is not None and s >= 4.5 for s in scores),
        f"scores={scores}",
    )

    no_web = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["restaurant"],
            locationQuery="Chicago, IL",
            maxCrawledPlacesPerSearch=5,
            website="withoutWebsite",
        )
    )
    _check(
        "website=withoutWebsite holds",
        bool(no_web) and all(not i.get("website") for i in no_web),
        f"{len(no_web)} items, websites={[i.get('website') for i in no_web]}",
    )

    matching = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["pizza"],
            locationQuery="Boston, MA",
            maxCrawledPlacesPerSearch=5,
            searchMatching="only_includes",
        )
    )
    titles = [i.get("title") for i in matching]
    _check(
        "searchMatching=only_includes keeps 'pizza' in titles",
        bool(titles) and all("pizza" in (t or "").lower() for t in titles),
        f"titles={titles}",
    )


async def step_search_closed() -> None:
    _hr("K — closed-place detection + skipClosedPlaces (Dean & DeLuca)")
    q = "Dean DeLuca 560 Broadway New York"
    found = await scrape_places(
        GoogleMapsScrapeInput(searchStringsArray=[q], maxCrawledPlacesPerSearch=3)
    )
    dean = next((i for i in found if "DeLuca" in (i.get("title") or "")), None)
    _check(
        "permanently closed place flagged",
        dean is not None and dean.get("permanentlyClosed") is True,
        f"title={dean.get('title') if dean else None}, closed={dean.get('permanentlyClosed') if dean else None}",
    )
    skipped = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=[q],
            maxCrawledPlacesPerSearch=3,
            skipClosedPlaces=True,
        )
    )
    _check(
        "skipClosedPlaces filters it out",
        not any("DeLuca" in (i.get("title") or "") for i in skipped),
        f"{len(skipped)} items after skip",
    )


async def step_search_url_and_geo() -> None:
    _hr("L — /maps/search/ URL routing + customGeolocation")
    via_url = await scrape_places(
        GoogleMapsScrapeInput(
            startUrls=[
                {"url": "https://www.google.com/maps/search/ramen+in+Osaka+Japan/"}
            ],
            maxCrawledPlacesPerSearch=5,
        )
    )
    osaka = sum(
        1
        for i in via_url
        if i.get("location") and 34.4 < (i["location"]["lat"] or 0) < 35.0
    )
    _check(
        "/maps/search/ startUrl yields Osaka ramen places",
        len(via_url) == 5 and osaka >= 4,
        f"{len(via_url)} items, {osaka} in Osaka",
    )

    geo = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["museum"],
            customGeolocation={
                "type": "Point",
                "coordinates": [2.3522, 48.8566],  # [lng, lat] Paris
                "radiusKm": 10,
            },
            maxCrawledPlacesPerSearch=5,
        )
    )
    paris = sum(
        1
        for i in geo
        if i.get("location")
        and 48.5 < (i["location"]["lat"] or 0) < 49.2
        and 1.9 < (i["location"]["lng"] or 0) < 2.8
    )
    _check(
        "customGeolocation Point scopes to Paris",
        len(geo) >= 3 and paris >= 3,
        f"{len(geo)} items, {paris} in Paris: {[i.get('title') for i in geo]}",
    )


async def step_search_pagination_stress() -> None:
    _hr("M — search pagination stress (60 results / 3+ pages, exhaustion)")
    items = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["restaurant"],
            locationQuery="Manhattan, New York",
            maxCrawledPlacesPerSearch=60,
        )
    )
    fids = [i.get("fid") for i in items]
    _check(
        "60 places, all fids unique (offset paging + dedupe)",
        len(items) == 60 and len(set(fids)) == 60,
        f"{len(items)} items, {len(set(fids))} unique",
    )
    _check(
        "ranks strictly sequential 1..60",
        [i.get("rank") for i in items] == list(range(1, 61)),
    )
    manhattan = sum(
        1
        for i in items
        if i.get("location") and 40.68 < (i["location"]["lat"] or 0) < 40.9
    )
    _check(
        "results stay in Manhattan across pages",
        manhattan >= 55,
        f"{manhattan}/60 in bounds",
    )

    # A hyper-specific query has few results: paging must terminate on its
    # own (no infinite loop, no error) well before the requested cap.
    sparse = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["Kim's Island Staten Island"],
            maxCrawledPlacesPerSearch=100,
        )
    )
    _check(
        "sparse query exhausts naturally below the cap",
        0 < len(sparse) < 25,
        f"{len(sparse)} results",
    )


async def step_detail_extras() -> None:
    _hr("N — detail-page extras (kgmid/cid/additionalInfo/links)")
    # pin the exact place by fid — a name search returns a different Joe's
    # branch run to run, which makes magnitude assertions flaky
    items = await scrape_places(
        GoogleMapsScrapeInput(
            startUrls=[
                {
                    "url": "https://www.google.com/maps/place/Joe's+Pizza+Broadway/"
                    "data=!4m2!3m1!1s0x89c259ab3c1ef289:0x3b67a41175949f55"
                }
            ],
            maxImages=5,
        )
    )
    if not items:
        _check("place returned", False)
        return
    it = items[0]
    dist = it.get("reviewsDistribution") or {}
    _check(
        "reviewsCount + distribution (NID-session fields)",
        (it.get("reviewsCount") or 0) > 20_000
        and (it.get("reviewsCount") == sum(dist.values())),
        f"count={it.get('reviewsCount')}, dist={dist}",
    )
    hist = it.get("popularTimesHistogram") or {}
    _check(
        "popular times histogram covers the week",
        set(hist) == {"Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"}
        and all(
            {"hour", "occupancyPercent"} <= set(slot)
            for d in hist.values()
            for slot in d
        ),
        f"days={sorted(hist)}",
    )
    _check(
        "image gallery fields (count/categories/urls capped at maxImages)",
        (it.get("imagesCount") or 0) > 1000
        and "All" in (it.get("imageCategories") or [])
        and len(it.get("imageUrls") or []) == 5,
        f"count={it.get('imagesCount')}, cats={len(it.get('imageCategories') or [])}, "
        f"urls={len(it.get('imageUrls') or [])}",
    )
    tags = it.get("reviewsTags") or []
    _check(
        "reviewsTags with counts",
        len(tags) >= 5 and all(t.get("title") and t.get("count") for t in tags),
        f"{tags[:2]}",
    )
    _check(
        "additionalInfo has full section set (not just Accessibility)",
        len(it.get("additionalInfo") or {}) >= 8,
        f"sections={list((it.get('additionalInfo') or {}).keys())}",
    )

    # scrapePlaceDetailPage on the SEARCH flow: search darrays lack the
    # session-gated fields, so each hit must get enriched via a detail RPC.
    enriched = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["ramen"],
            locationQuery="Chicago, IL",
            maxCrawledPlacesPerSearch=2,
            scrapePlaceDetailPage=True,
        )
    )
    _check(
        "search flow + scrapePlaceDetailPage enriches every hit",
        len(enriched) == 2
        and all(
            (e.get("reviewsCount") or 0) > 0 and e.get("reviewsDistribution")
            for e in enriched
        ),
        f"counts={[e.get('reviewsCount') for e in enriched]}",
    )
    fid = it.get("fid") or ""
    cid_ok = bool(fid) and it.get("cid") == str(int(fid.split(":")[1], 16))
    _check(
        "kgmid + cid derived from fid",
        bool(it.get("kgmid", "").startswith("/g/")) and cid_ok,
        f"kgmid={it.get('kgmid')}, cid={it.get('cid')}",
    )
    info = it.get("additionalInfo") or {}
    _check(
        "additionalInfo has sections with boolean options",
        bool(info)
        and all(
            isinstance(v, list) and all(isinstance(e, dict) for e in v)
            for v in info.values()
        ),
        f"sections={list(info.keys())}",
    )


async def step_hotel_fields() -> None:
    _hr("O — hotel fields (The Plaza: stars, dates, similar, ads)")
    items = await scrape_places(
        GoogleMapsScrapeInput(
            startUrls=[
                {
                    "url": "https://www.google.com/maps/place/The+Plaza/"
                    "data=!4m2!3m1!1s0x89c258f07d5da561:0x61f6aa300ba8339d"
                }
            ],
        )
    )
    if not items:
        _check("hotel returned", False)
        return
    it = items[0]
    _check(
        "hotelStars + check-in/out dates",
        it.get("hotelStars") == "5 stars"
        and (it.get("checkInDate") or "") < (it.get("checkOutDate") or ""),
        f"stars={it.get('hotelStars')}, {it.get('checkInDate')}..{it.get('checkOutDate')}",
    )
    similar = it.get("similarHotelsNearby") or []
    _check(
        "similarHotelsNearby with fid/score",
        len(similar) >= 3 and all(h.get("title") and h.get("fid") for h in similar),
        f"{len(similar)} hotels, first={similar[0].get('title') if similar else None}",
    )
    ads = it.get("hotelAds") or []
    _check(
        "hotelAds with booking links",
        bool(ads) and all(a.get("url", "").startswith("https://") for a in ads),
        f"{len(ads)} ads",
    )


async def step_all_places_scan() -> None:
    _hr("P — allPlacesNoSearchAction area scan (Times Square 400m)")
    items = await scrape_places(
        GoogleMapsScrapeInput(
            allPlacesNoSearchAction="all_places_no_search_mouse",
            customGeolocation={
                "type": "Point",
                "coordinates": [-73.9855, 40.758],
                "radiusKm": 0.4,
            },
            maxCrawledPlacesPerSearch=25,
        )
    )
    fids = [i.get("fid") for i in items]
    _check(
        "25 unique places without any search term",
        len(items) == 25 and len(set(fids)) == 25,
        f"{len(items)} items",
    )
    cats = {i.get("categoryName") for i in items if i.get("categoryName")}
    _check(
        "multiple categories represented (sweep, not one query)",
        len(cats) >= 5,
        f"{len(cats)} categories",
    )
    in_view = sum(
        1 for i in items if i.get("location") and 40.74 < i["location"]["lat"] < 40.78
    )
    _check("scan respects the viewport", in_view >= 23, f"{in_view}/25 in bounds")


async def step_short_url() -> None:
    _hr("Q — short link (maps.app.goo.gl Firebase redirect -> place)")
    # A real shared short link -> "Aux Merveilleux de Fred" (NYC). These are
    # Firebase Dynamic Links (JS interstitial), so this exercises the browser-
    # render redirect path in resolve_fid. fid is the ground-truth invariant.
    it = await scrape_one("https://maps.app.goo.gl/8YUvDPbQPrasqC528")
    _check(
        "maps.app.goo.gl short link resolves to the right place",
        it is not None
        and it.get("fid") == "0x89c259957da502cd:0xed3eb58a4ca08a95"
        and "merveilleux" in (it.get("title") or "").lower(),
        f"title={it.get('title') if it else None!r}, fid={it.get('fid') if it else None}",
    )


async def step_filter_variants() -> None:
    _hr("R — search filter variants (only_exact, categoryFilterWords)")
    # only_exact: the parsed title must equal the query exactly (Seattle
    # Starbucks are titled "Starbucks Coffee Company", not "Starbucks").
    exact = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["Starbucks Coffee Company"],
            locationQuery="Seattle, WA",
            maxCrawledPlacesPerSearch=8,
            searchMatching="only_exact",
        )
    )
    titles = [i.get("title") for i in exact]
    _check(
        "searchMatching=only_exact keeps only exact-title matches",
        bool(titles)
        and all((t or "").lower() == "starbucks coffee company" for t in titles),
        f"{len(titles)} items, titles={titles[:3]}",
    )
    # categoryFilterWords: drop places whose categories don't include a word.
    coffee = await scrape_places(
        GoogleMapsScrapeInput(
            searchStringsArray=["food"],
            locationQuery="Seattle, WA",
            maxCrawledPlacesPerSearch=6,
            categoryFilterWords=["coffee"],
        )
    )
    _check(
        "categoryFilterWords keeps only matching categories",
        bool(coffee)
        and all(
            any("coffee" in c.lower() for c in (i.get("categories") or []))
            for i in coffee
        ),
        f"{len(coffee)} items, cats={[i.get('categories') for i in coffee][:2]}",
    )


async def step_reviews_origin() -> None:
    _hr("S — reviewsOrigin=google filter")
    # The public BOQ feed only carries Google-origin reviews (partner reviews
    # aren't exposed anonymously), so the invariant is: nothing non-Google
    # leaks through when origin is pinned to google.
    items = await scrape_reviews(
        GoogleMapsReviewsInput(
            placeIds=[_KIMS_PLACE_ID], maxReviews=10, reviewsOrigin="google"
        )
    )
    origins = {(r.get("reviewOrigin") or "Google") for r in items}
    _check(
        "reviewsOrigin=google -> only Google-origin reviews",
        bool(items) and origins <= {"Google"},
        f"{len(items)} reviews, origins={origins}",
    )


async def step_inline_consistency() -> None:
    _hr("H — inline reviews[] match the standalone reviews endpoint")
    place = await scrape_one(
        f"https://www.google.com/maps/place/?q=place_id:{_KIMS_PLACE_ID}",
        maxReviews=5,
    )
    standalone = await scrape_reviews(
        GoogleMapsReviewsInput(placeIds=[_KIMS_PLACE_ID], maxReviews=5)
    )
    if not place or not standalone:
        _check("both sources returned data", False)
        return
    inline_ids = {r.get("reviewId") for r in (place.get("reviews") or [])}
    standalone_ids = {r.get("reviewId") for r in standalone}
    overlap = len(inline_ids & standalone_ids)
    _check(
        "inline and standalone reviews overlap (same feed)",
        overlap >= 3,  # feed ordering can shift slightly between calls
        f"{overlap}/5 shared review IDs",
    )


async def main() -> int:
    steps = [
        step_diverse_places(),
        step_cid_url(),
        step_review_sorts(),
        step_start_date_cutoff(),
        step_personal_data(),
        step_localization(),
        step_big_place_pagination(),
        step_inline_consistency(),
        step_search_discovery(),
        step_search_filters(),
        step_search_closed(),
        step_search_url_and_geo(),
        step_search_pagination_stress(),
        step_detail_extras(),
        step_hotel_fields(),
        step_all_places_scan(),
        step_short_url(),
        step_filter_variants(),
        step_reviews_origin(),
    ]
    for coro in steps:
        try:
            await coro
        except Exception as e:  # keep going; report the step as failed
            _check(f"step crashed: {coro}", False, repr(e))

    _hr("SUMMARY")
    passed = sum(1 for _, ok, _ in _CHECKS if ok)
    for label, ok, detail in _CHECKS:
        if not ok:
            print(f"  FAILED: {label} — {detail}")
    print(f"  {passed}/{len(_CHECKS)} checks passed")
    return 0 if passed == len(_CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
