# Google Maps Scraper

A platform-native Google Maps scraper intended as a **drop-in clone of the
Apify "Google Maps Scraper" and "Google Maps Reviews Scraper" actors** — same
input surface, same output item shape. Built on the same layout and
progressive-implementation approach as the sibling `../youtube` scraper.

**Current status: search + place details + reviews live.** Search terms
(`searchStringsArray` x `locationQuery`/geolocation) are discovered via the
public `search?tbm=map` RPC with offset paging and the Apify result filters.
Direct place URLs and bare `placeIds` are scraped via Google's public
`/maps/preview/place` RPC; reviews (both the standalone Reviews endpoint and
inline `reviews[]` on places when `maxReviews > 0`) come from the public
`GetLocalBoqProxy` review feed with full token-based pagination. No login,
proxy-only egress.

## Public vs. gated data

All core Maps data is **public — no Google account needed**: search results,
place details (phone, website, hours, price, coordinates, plus code, address
components), and reviews (text, ratings, reviewer profiles, owner responses)
are served by Google's internal endpoints (`/maps/preview/place`,
`GetLocalBoqProxy`, `search?tbm=map`) which return XSSI-guarded JSON to
anonymous requests. Only a residential proxy is required (Google blocks
datacenter IPs) — already wired via `app/utils/proxy`.

**Session-gated (but still login-free) fields:** Google trims the rich detail
fields — `reviewsCount`, `reviewsDistribution`, popular times, image
galleries, `reviewsTags`, and most `additionalInfo` sections — from responses
that carry **no session cookie**. A plain GET to `/maps` mints an `NID` cookie
that unlocks all of them (no login, no browser needed at runtime;
`fetch.get_session_cookies` mints them into a small rotating pool with a
30-minute TTL). The full-page `pb` selector these fields also require was
captured once from a headless browser render of a place page and genericized
into `_PLACE_DETAIL_PB`.

> Note: the older review RPCs other scrapers documented (`listugcposts`,
> `listentitiesreviews`) now return empty pages / 404 to anonymous callers —
> they appear to require a signed-in session. The `GetLocalBoqProxy` feed (used
> by Google's own search local panel) is the one that still works publicly and
> is what `fetch.iter_reviews_pages` uses.

If Google ever serves a sign-in/consent wall instead of data,
`SignInRequiredError` is raised and the route returns **403 "Google sign in
required"** rather than an empty result.

Not sourced from Maps at all (Apify enrichment add-ons that hit third-party
data brokers / the business's own website — out of scope for public-Maps-only):
`maximumLeadsEnrichmentRecords`, `leadsEnrichmentDepartments`,
`verifyLeadsEnrichmentEmails`, `scrapeSocialMediaProfiles`, `scrapeContacts`,
`enableCompetitorAnalysis`. These stay at their schema defaults (`None`/`[]`).

## Quick start

```python
from app.proprietary.scrapers.google_maps import (
    GoogleMapsScrapeInput, scrape_places,
    GoogleMapsReviewsInput, scrape_reviews,
)

# Places — search terms, direct URLs, and placeIds are all additive.
# maxReviews > 0 also attaches inline reviews[] to each place item.
places = await scrape_places(
    GoogleMapsScrapeInput(
        searchStringsArray=["coffee shop"],
        locationQuery="Seattle, WA",
        maxCrawledPlacesPerSearch=20,
        startUrls=[{"url": "https://www.google.com/maps/place/..."}],
        placeIds=["ChIJJQz5EZzKw4kRCZ95UajbyGw"],
        maxReviews=10,
    )
)

# Reviews — one flat item per review (review fields + place header fields)
reviews = await scrape_reviews(
    GoogleMapsReviewsInput(
        placeIds=["ChIJJQz5EZzKw4kRCZ95UajbyGw"],
        maxReviews=100,
        reviewsSort="newest",
    )
)
```

Both have a streaming twin — `iter_places()` / `iter_reviews()`. The HTTP
surface lives in `app/routes/google_maps_routes.py` (`POST /google-maps/scrape`
and `POST /google-maps/reviews`).

## Module map

| File              | Responsibility                                                                                                                        |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `__init__.py`     | Public exports (entry points + schemas).                                                                                                     |
| `schemas.py`      | Pydantic input/output models mirroring the Apify camelCase specs. `extra="allow"` on outputs keeps the contract open.                        |
| `scraper.py`      | Places orchestrator. `_place_flow` (live): fid → detail RPC → `PlaceItem` (+ inline reviews). `_search_flow` (live): tbm=map paging + filters. |
| `reviews.py`      | Reviews orchestrator (live). Pages the BOQ feed per place, applies sort/date-cutoff/origin/personal-data rules, one flat item per review.    |
| `fetch.py`        | Proxy-only fetch seam: `fetch_html`, `fetch_rpc_json` (XSSI-strip + HTML-wrapper tolerant), `fetch_place_darray`, `iter_reviews_pages`, `iter_search_pages`. |
| `parsers.py`      | Pure array-path parsing: place `darray` → PlaceItem fields (paths from gosom), BOQ review arrays → ReviewFields dicts.                       |
| `url_resolver.py` | Classify a URL into `place` / `search` / `reviews` / `cid` / `shortlink`; extract the feature ID (`0x..:0x..`).                              |

## How place scraping works

1. Resolve the **feature ID** (`0x<hex>:0x<hex>`): from the URL's `data=!1s…`
   blob when present, else fetch the place page once and regex it from HTML
   (covers `?q=place_id:ChIJ…` and `?cid=…`). Name-only URLs
   (`/maps/place/Eiffel+Tower/`) serve a JS shell with no fid in the HTML, so
   those fall back to a `search?tbm=map` lookup of the name
   (`fetch.fid_from_search`) and take the top result's fid. Short links
   (`maps.app.goo.gl` / `goo.gl`) are Firebase Dynamic Links — a plain GET only
   returns a JS interstitial, so they're browser-rendered so the JS follows the
   redirect to the real `/maps/place/…` URL, then the fid is read from that.
2. GET `/maps/preview/place?…&pb=!1m13!1s{fid}…` through the proxy, with the
   NID session cookie. The `pb` is the same selector the Maps web app sends
   (browser-captured, genericized), so the response is the **full** payload
   including the session-gated fields. `)]}'`-guarded JSON; `jd[6]` is the
   place detail array ("darray") that all field paths index into.
3. `parse_place()` maps darray positions → Apify-shaped fields (title,
   categories, address components, phone, website, rating, plus code, hours,
   coordinates, placeId…). Only keys whose path hit are set; the rest keep
   schema defaults.

Detail extras parsed from the same darray (no extra requests):

- `kgmid` (`darray[89]`, e.g. `/g/11bw4ws2mt`) and `cid` — the CID is just the
  decimal value of the fid's second hex half, so it's derived, not fetched.
- `additionalInfo` — all about sections at `darray[100][1]` in Apify's shape
  (`{"Accessibility": [{"Wheelchair accessible entrance": true}, …]}`).
- `reviewsCount` (`[4][8]`) + `reviewsDistribution` (`[175][3]`).
- `popularTimesHistogram` / `popularTimesLiveText` / `popularTimesLivePercent`
  (`darray[84]`).
- `imagesCount` (`[37][1]`), `imageCategories` (gallery tab names at
  `[171][0]`), `imageUrls` (hero photos + tab thumbnails; emitted only when
  `maxImages > 0`, capped at it). Full multi-thousand-photo galleries would
  need the signed-in photo-listing RPC, so `imageUrls` tops out around a
  dozen per place.
- `reviewsTags` (`[153][0]` → `[{title, count}]`).
- `tableReservationLinks` + `reserveTableUrl` (`darray[46]`), `orderBy` /
  `googleFoodUrl` (order-online providers at `darray[75]`), `menu`
  (`darray[38][0]`).

Hotel places (detected by the star string at `darray[35][6]`) additionally
get: `hotelStars`, `hotelDescription`, `checkInDate`/`checkOutDate` (the
dates Google quoted prices for, `[35][0..1]`), `similarHotelsNearby`
(`[35][29][0]` — title/fid/score/count/location/description), and `hotelAds`
(`[35][44]` — booking-partner title/url/price). Probed live on The Plaza NYC.

Search-result darrays are served **without** the session-gated fields (the
NID cookie doesn't help `search?tbm=map` — verified live), so when
`scrapePlaceDetailPage=true` or `maxImages > 0` the search flow makes one
detail RPC per emitted place and merges the full payload over the search
fields — same trade Apify makes (search-only is one request per ~20 places;
detail adds one per place).

**`allPlacesNoSearchAction`** (area scan with no search term): Apify's
implementation OCRs / mouse-overs rendered map pins — the public RPC has no
"list everything" query (`*` and empty return nothing). Ours approximates the
scan with a broad category sweep (`restaurant`, `store`, `hotel`, …17 terms)
over the requested viewport, deduped by fid, until
`maxCrawledPlacesPerSearch`. `searchString` carries the action value on scan
items. Verified live: 25 unique places / 14 distinct categories from a 400 m
Times Square viewport.

## How search discovery works

1. Build the query: `"{search term} in {location}"` when `locationQuery` (or
   the city/state/... geolocation fields) is set — Google localizes from the
   query text, so no geocoding round-trip is needed. A `customGeolocation`
   GeoJSON Point instead sets a real lat/lng/radius viewport.
2. Page `search?tbm=map` (~20 results per page, `!8i` offset). Each result
   entry embeds a **full place darray** at `entry[14]` — same shape as the
   detail RPC — so `parse_place()` runs directly on it and no per-place detail
   request is needed. Single-match queries put the one place in slot 0 of the
   results list; multi-result pages start at slot 1 (both handled).
3. Dedupe by fid (Google reshuffles results between pages), stamp
   `rank`/`searchString`/`searchPageUrl`, apply the Apify filters client-side
   (`searchMatching`, `categoryFilterWords`, `placeMinimumStars`, `website`,
   `skipClosedPlaces`), and stop at `maxCrawledPlacesPerSearch`, an empty
   page, or a page with no new fids. Verified live to 60 unique results
   (3+ pages) with strictly sequential ranks, and to terminate on its own for
   sparse queries that exhaust before the cap.

Closed places: `darray[88][0]` carries a status enum (`CLOSED` verified live
on a permanently-closed place) that maps to `permanentlyClosed`.

## Performance

Every RPC is a ~2s proxy round-trip, so wall-clock time is dominated by how
many requests run in series, not by parsing. Independent requests are
overlapped (bounded, order preserved via `gather_bounded`):

- **Detail enrichment** (`scrapePlaceDetailPage` / `maxImages`) and inline
  reviews fire concurrently across a search page instead of one place at a
  time — the biggest lever (a 20-place enriched search went from ~50s to ~10s,
  `_DETAIL_CONCURRENCY=8`).
- **Search pages** are prefetched in waves sized from the result cap
  (`_prefetch_for`) so a 60-result / 3-page search overlaps its pages.
- **Bulk `placeIds`** are fetched in parallel.
- **NID mint** coalesces concurrent cold callers onto one in-flight request
  (the pool lock isn't held across the network call), so a burst of parallel
  detail fetches doesn't serialize behind N sequential ~2s mints.

Reviews within a single place stay sequential — pagination is
continuation-token based (each token embeds the previous page's last-review
key plus a signature, so page N+1's token can't be forged or precomputed).
The only lever there is page size: the feed is asked for the ~60/page ceiling
(`_REVIEWS_PAGE_SIZE`) instead of the old 10/20, cutting the sequential
round-trips ~3x (1000 reviews: ~113s → ~40s).

## How review scraping works

1. Resolve the feature ID exactly as above (reviews accept the same
   `startUrls` / `placeIds` inputs).
2. Fetch the place detail once for the header fields (title, address,
   location, …) that Apify stamps onto every review item.
3. Page `GetLocalBoqProxy` (~60 reviews per page — the feed's ceiling, asked
   via `_REVIEWS_PAGE_SIZE`; opaque continuation token in `node[6]`) until
   `maxReviews`, the `reviewsStartDate` cutoff (newest-first), or the feed is
   exhausted. Sort modes map to codes 1–4
   (mostRelevant/newest/highestRanking/lowestRanking).
4. `parse_review()` maps each ~48-slot review array → ReviewFields (author,
   stars, text, ISO publish date, images, owner response, guided
   context/per-aspect ratings, origin). `personalData=false` strips reviewer
   name/id/URL/photo (reviewId stays), per Apify semantics.

## API spec

Mirrors the Apify "Google Maps Scraper" and "Google Maps Reviews Scraper"
actors (camelCase, `extra="allow"`). Unknown inputs are accepted, unsourced
outputs come back as `None`/`[]`/`{}` — parity grows without breaking
consumers. `schemas.py` is the source of truth; the tables below list what the
implementation actually **sources** vs. still **stubs**.

### Places — input (`GoogleMapsScrapeInput`)

| Field | Type / default | Status | Notes |
|---|---|---|---|
| `searchStringsArray` | `list[str]` `[]` | ✅ | search-term discovery; additive with the others |
| `startUrls` | `list[{url}]` `[]` | ✅ | place / CID / short / search / reviews URLs |
| `placeIds` | `list[str]` `[]` | ✅ | bare `ChIJ…` ids (fetched in parallel) |
| `allPlacesNoSearchAction` | enum `""` | ✅* | area scan via broad-category sweep (approximation) |
| `locationQuery` | `str` | ✅ | e.g. `"San Jose, CA"`, appended as `"{q} in {loc}"` |
| `city`/`state`/`county`/`postalCode`/`countryCode` | `str` | ✅ | discrete location parts (alt. to `locationQuery`) |
| `customGeolocation` | GeoJSON `Point`+`radiusKm` | ✅ | real lat/lng/radius viewport |
| `maxCrawledPlacesPerSearch` | `int\|None` | ✅ | `None` = all; caps emitted places |
| `language` | `str` `"en"` | ✅ | `hl=` on every RPC |
| `searchMatching` | `all\|only_includes\|only_exact` | ✅ | title-match filter |
| `categoryFilterWords` | `list[str]` `[]` | ✅ | category client-filter |
| `placeMinimumStars` | enum `""` | ✅ | min `totalScore` filter |
| `website` | `allPlaces\|withWebsite\|withoutWebsite` | ✅ | website-presence filter |
| `skipClosedPlaces` | `bool` `false` | ✅ | drops permanently/temporarily closed |
| `scrapePlaceDetailPage` | `bool` `false` | ✅ | adds detail-RPC extras (see below) |
| `maxReviews` | `int` `0` | ✅ | `0` = none; attaches `reviews[]` |
| `reviewsSort`/`reviewsStartDate`/`reviewsFilterString`/`reviewsOrigin`/`scrapeReviewsPersonalData` | — | ✅ | as in the Reviews scraper |
| `maxImages` | `int` `0` | ✅ | caps `imageUrls` (URLs only, no author/date) |
| `scrapeContacts`, `scrapeSocialMediaProfiles`, `*LeadsEnrichment*`, `enableCompetitorAnalysis`, `maxCompetitorsToAnalyze`, `scrapeTableReservationProvider`, `scrapeOrderOnline`, `includeWebResults`, `scrapeDirectories`, `maxQuestions`, `scrapeImageAuthors` | — | ⛔ stub | accepted; out of scope / login-walled (see TODO) |

`✅*` = approximation, not pin-complete.

### Places — output (`PlaceItem`), sourced fields

- **Identity:** `title`, `description`, `price`, `categoryName`, `categories`,
  `placeId`, `fid`, `cid`, `kgmid`
- **Location:** `address`, `neighborhood`, `street`, `city`, `postalCode`,
  `state`, `countryCode`, `location{lat,lng}`, `plusCode`
- **Contact:** `website`, `phone`, `phoneUnformatted`, `menu`
- **Ratings/status:** `totalScore`, `reviewsCount`, `reviewsDistribution`,
  `permanentlyClosed`, `temporarilyClosed`
- **Images:** `imageUrl`, `imagesCount`, `imageCategories`, `imageUrls`
- **Detail-page (with `scrapePlaceDetailPage`):** `openingHours`,
  `additionalInfo`, `reviewsTags`, `popularTimesHistogram`,
  `popularTimesLiveText`, `popularTimesLivePercent`
- **Hotels (hotel places):** `hotelStars`, `hotelDescription`, `checkInDate`,
  `checkOutDate`, `similarHotelsNearby`, `hotelAds`
- **Reviews (with `maxReviews>0`):** `reviews[]` (see review fields below)
- **Provenance/meta:** `searchString`, `rank`, `searchPageUrl`, `url`,
  `scrapedAt`
- **Stubbed** (`[]`/`{}`/`None`): `peopleAlsoSearch`, `questionsAndAnswers`,
  `images` (author/date objects), `webResults`, `bookingLinks`,
  `tableReservationLinks`, `gasPrices`, `ownerUpdates`, leads/contact/social
  enrichment.

### Reviews — input (`GoogleMapsReviewsInput`) & output (`ReviewItem`)

Input: `startUrls`, `placeIds`, `maxReviews` (default `10000000` = "all"),
`reviewsSort`, `reviewsStartDate`, `language`, `reviewsOrigin`, `personalData`.

Output is **one flat item per review** — the review fields merged with the
parent place header. Sourced review fields: `reviewId`, `name`/`text`/
`textTranslated`, `stars`, `publishAt` (relative) + `publishedAtDate` (ISO),
`likesCount`, `reviewerId`/`reviewerUrl`/`reviewerPhotoUrl`/
`reviewerNumberOfReviews`/`isLocalGuide`, `reviewOrigin`, `reviewImageUrls`,
`reviewContext`, `reviewDetailedRating`, `responseFromOwnerText`
(+ `responseFromOwnerDate` as relative text only — see TODO).

Notable input semantics (matching Apify):

- Places: `searchStringsArray`, `startUrls`, and `placeIds` are **additive**
  (unlike YouTube where startUrls override queries).
- `maxCrawledPlacesPerSearch=None` (unset) means "all places".
- Reviews: `maxReviews` defaults to `10000000` ("all"); `reviewsStartDate`
  forces newest-first and stops at the cutoff.
- `personalData` / `scrapeReviewsPersonalData` default `true`; when off,
  reviewer id/name/URL/photo must be stripped (reviewId always stays).

## Testing

Offline unit tests (no network; parser tests pin real captured fixtures):

```bash
cd surfsense_backend
.venv/Scripts/python.exe -m pytest tests/unit/scrapers/google_maps/
```

Live end-to-end (real network + proxy; also regenerates fixtures):

```bash
.venv/Scripts/python.exe scripts/e2e_google_maps_scraper.py
```

Deep live verification (diverse places worldwide + review semantics: sort
order, date cutoff, pagination uniqueness, personal-data stripping, French
localization, CID URLs, name-only URLs, short links, search-filter variants
`only_exact` / `categoryFilterWords`, and `reviewsOrigin=google`):

```bash
.venv/Scripts/python.exe scripts/e2e_google_maps_deep.py
```

## Implementation TODO (progressive, like YouTube)

- Owner-response dates are only exposed as relative text ("11 months ago") in
  the BOQ feed; `responseFromOwnerDate` carries that string, not an ISO date.
  (The detail RPC's inline reviews don't carry reply timestamps either, and
  `listugcposts` still returns no reviews even with the NID cookie.)
- Full image galleries (`images` with author/date, beyond the ~dozen
  `imageUrls`): needs the signed-in photo-listing RPC.
- Q&A (`questionsAndAnswers`): `darray[126]` is empty everywhere we probed —
  Google appears to have retired public Q&A. `peopleAlsoSearch`: not in the
  detail darray; likely a separate RPC.
- A pin-complete `allPlacesNoSearchAction` (the category sweep covers most
  pins but not businesses outside the swept categories); would need browser
  rendering + tile OCR like Apify's.
