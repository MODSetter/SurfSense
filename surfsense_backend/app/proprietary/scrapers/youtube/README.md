# YouTube Scraper

A platform-native YouTube scraper that is a **drop-in clone of the Apify
"YouTube Scraper" and "YouTube Comments Scraper" actors** — same input surface,
same output item shape. It talks to YouTube's internal **InnerTube** API plus
the public watch/channel HTML, egresses through a residential proxy, and streams
Apify-shaped dicts.

No API keys, no Apify account, no headless browser on the happy path.

---

## Quick start

```python
from app.proprietary.scrapers.youtube import (
    YouTubeScrapeInput, scrape_youtube,
    YouTubeCommentsInput, scrape_comments,
)

# Videos — by search query and/or direct URLs (video/channel/playlist/hashtag/search)
videos = await scrape_youtube(
    YouTubeScrapeInput(searchQueries=["surfsense"], maxResults=50)
)
videos = await scrape_youtube(
    YouTubeScrapeInput(startUrls=[{"url": "https://www.youtube.com/@SomeChannel"}],
                       maxResults=20, downloadSubtitles=True)
)

# Comments — one output item per top-level comment AND per reply
comments = await scrape_comments(
    YouTubeCommentsInput(
        startUrls=[{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}],
        maxComments=200, sortCommentsBy="TOP_COMMENTS",
    )
)
```

Both have a streaming twin — `iter_youtube()` / `iter_comments()` — that yields
items as they arrive (unbounded, continuation-paged). `scrape_*` is just a
collector with an optional `limit` guard.

The HTTP surface lives in `app/routes/youtube_routes.py`.

---

## Module map


| File                | Responsibility                                                                                                                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `__init__.py`       | Public exports (entry points + schemas).                                                                                                                                                   |
| `schemas.py`        | Pydantic input/output models mirroring the Apify camelCase spec. `extra="allow"` on outputs keeps the contract open.                                                                       |
| `scraper.py`        | Video orchestrator. Resolves URLs → per-flow async generators (`_video_flow`, `_search_flow`, `_channel_flow`, `_playlist_flow`), runs them through the `fan_out` worker pool.             |
| `comments.py`       | Comments orchestrator. Watch page → comments-section continuation → `/next` paging, with concurrent per-thread reply fetching.                                                             |
| `innertube.py`      | **The network seam.** Proxy-only fetch (`fetch_html`, `post_innertube`), reusable sticky-IP sessions, reactive IP rotation, `StealthyFetcher` fallback, and the InnerTube payload builder. |
| `parsers.py`        | Pure, I/O-free JSON/HTML traversal + normalization (`find_all`/`find_first`/`dig`, `parse_video_page`, `parse_search_response`, comment/continuation token extractors, `parse_count`, …).  |
| `url_resolver.py`   | Classify a URL into `video` / `channel` / `playlist` / `hashtag` / `search` and extract its id.                                                                                            |
| `search_filters.py` | Encode Apify search filters into YouTube's `sp=` base64 protobuf (sort/date/type/length/feature flags), composable.                                                                        |
| `subtitles.py`      | Subtitle download via `youtube-transcript-api`, shaped to Apify `subtitles[]`.                                                                                                             |


Everything in `parsers.py` is deterministic and unit-tested offline; everything
that touches the network is funneled through `innertube.py`.

---

## How it fetches (the important part)

All network I/O goes through `**fetch_html**` (GET watch/channel pages) and
`**post_innertube**` (POST InnerTube `browse`/`search`/`next`). Design rules:

1. **Proxy-only egress.** Every request goes through the residential proxy
  (`app/utils/proxy.get_proxy_url`). We never connect directly — a direct hit
   would expose and risk-block the server IP.
2. **Session reuse = sticky IP.** Within one flow (a continuation chain, or the
  jobs a worker pulls), a single keep-alive `FetcherSession` is reused. This
   roughly **halves warm latency** (~2.1s → ~1.0s) because only the first
   request pays the TCP+TLS handshake, and it pins one sticky exit IP instead of
   drawing a new (often slow) residential node per request.
3. **Reactive IP rotation.** A sticky IP is kept until it's actually blocked. On
  `403`/`429` or a connection error, the session rotates to a fresh IP and
   retries, up to `_MAX_ROTATIONS` (3). A probe of 120 sequential requests on
   one IP saw zero blocks, so rotation is reactive, not proactive.
4. **Browser fallback.** If all proxy attempts fail on an HTML page, `fetch_html`
  falls back to `StealthyFetcher` (headless, `solve_cloudflare=True`) in a
   worker thread. Optional — needs patchright browsers installed. Age-gated
   content requires login and is **not** bypassable.

The active session is bound to the current async task via a `ContextVar`
(`_current_session`), so parsers and orchestrators never thread a session
argument through every call — each concurrent flow transparently uses its own
session/IP.

### InnerTube payloads

`build_innertube_payload(...)` builds the `WEB` client `context` payload
(I/O-free, unit-testable). Some endpoints reject a keyless POST; `scraper._post`
retries once with the public web key (`INNERTUBE_PUBLIC_API_KEY`) when the
keyless call returns nothing. `hl=<lang>` on a `/next` call returns the
creator-localized title/description (the translation flow).

---

## Concurrency model

Independent jobs — each `startUrl`, each `searchQuery`, each comment video — run
concurrently through `**fan_out**`, a warm **worker pool** (`_FANOUT_CONCURRENCY = 16`):

- Each worker opens **one** proxy session and reuses it across the sequential
jobs it pulls, so only the first job per worker pays the handshake.
- **A bad job yields nothing rather than aborting the batch** (per-job
try/except). One dead URL / comments-disabled video never kills the run.
- Results stream out as each job finishes; **within** a flow, continuation
paging stays sequential.
- If the consumer stops early (collector hits its `limit`), workers are
cancelled and **awaited** so every session's `finally` closes — no leaked
keep-alive connections.

Comment reply threads for a page are fetched **concurrently** on the same
multiplexed session (`asyncio.gather`), capped at the remaining budget.

---

## Data flow

- **Video by URL** → fetch watch HTML → `parse_video_page` (reads
`ytInitialData` + `ytInitialPlayerResponse`) → optional subtitles + translation.
- **Search** → InnerTube `/search` (+ `sp=` filter protobuf) → paginate via
continuation tokens up to `maxResults`.
- **Channel** → fetch the videos-tab seed once (reused for channel-wide metadata
  - the About panel via `/browse`), then page `videos` / `shorts` / `streams`
  tabs, each capped independently (`maxResults` / `maxResultsShorts` /
  `maxResultStreams`). `sortVideosBy` uses the sort chips; `oldestPostDate` cuts
  off newest-first.
- **Playlist** → `/browse` `VL<id>`, paged via the continuation token → resolve
  each video via the video flow.
- **Hashtag** → the dedicated hashtag page (`/hashtag/<tag>`), whose feed is
  `videoRenderer` lockups (parsed like search) — not a `#tag` search.
- **Comments** → watch HTML seeds the comments-section token → `/next` returns
comment entities + per-thread reply tokens + the page token. `maxComments`
counts **every** emitted item (comments + replies).

### `commentsCount`

For the **comments** scraper, the authoritative total is read from the
comments-section header (`commentsHeaderRenderer.countText`), not the watch-page
HTML where it's lazy-loaded/absent. **Known gap:** the **video** scraper's
`VideoItem.commentsCount` still comes from search/watch HTML and is often `null`
— it would need an extra `/next` call to backfill (intentionally not done to
keep the video path cheap).

---

## API spec

Mirrors the Apify "YouTube Scraper" and "YouTube Comments Scraper" actors
(camelCase, `extra="allow"`). Inputs use Pydantic defaults; **every field is
additive** — unknown inputs are accepted, unsourced outputs come back as
`None`/`[]` — so parity grows without breaking consumers. `schemas.py` is the
source of truth.

### Video scraper — input (`YouTubeScrapeInput`)


| Field                                                                                                   | Type / values                                | Default | Notes                                                                              |
| ------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ------- | ---------------------------------------------------------------------------------- |
| `searchQueries`                                                                                         | `string[]`                                   | `[]`    | Discovery by query. Ignored when `startUrls` is set.                               |
| `startUrls`                                                                                             | `[{ "url": string }]`                        | `[]`    | Direct URLs: video, channel, playlist, hashtag, search. Overrides `searchQueries`. |
| `maxResults`                                                                                            | `int ≥ 0`                                    | `0`     | Cap of regular videos **per query and per channel**. `0` = fetch none.             |
| `maxResultsShorts`                                                                                      | `int ≥ 0`                                    | `0`     | Cap of Shorts per channel.                                                         |
| `maxResultStreams`                                                                                      | `int ≥ 0`                                    | `0`     | Cap of live/streams per channel.                                                   |
| `downloadSubtitles`                                                                                     | `bool`                                       | `false` | Populate `subtitles[]`.                                                            |
| `subtitlesLanguage`                                                                                     | `string`                                     | `"en"`  | Also drives the translation flow when non-`en` (see `translatedTitle`).            |
| `subtitlesFormat`                                                                                       | `srt` | `vtt` | `xml` | `plaintext`          | `"srt"` |                                                                                    |
| `preferAutoGeneratedSubtitles`                                                                          | `bool`                                       | `false` |                                                                                    |
| `saveSubsToKVS`                                                                                         | `bool`                                       | `false` | Accepted for parity; no-op (Apify key-value-store concept).                        |
| `sortingOrder`                                                                                          | `relevance` | `rating` | `date` | `views`    | `null`  | Search only.                                                                       |
| `dateFilter`                                                                                            | `hour` | `today` | `week` | `month` | `year` | `null`  | Search only.                                                                       |
| `videoType`                                                                                             | `video` | `movie`                            | `null`  | Search only.                                                                       |
| `lengthFilter`                                                                                          | `under4` | `between420` | `plus20`           | `null`  | Search only (<4min / 4–20min / >20min).                                            |
| `isHD` `hasSubtitles` `hasCC` `is3D` `isLive` `isBought` `is4K` `is360` `hasLocation` `isHDR` `isVR180` | `bool`                                       | `null`  | Search feature filters (encoded into `sp=`).                                       |
| `oldestPostDate`                                                                                        | `string` (date)                              | `null`  | Channel cutoff; day-accurate (relative times).                                     |
| `sortVideosBy`                                                                                          | `NEWEST` | `POPULAR` | `OLDEST`              | `null`  | Channel videos tab sort chip.                                                      |


### Video scraper — output (`VideoItem`)


| Field                                                          | Type                                | Populated?                                                          |
| -------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------- |
| `title` `id` `url` `viewCount` `date` `duration`               | str/int                             | yes                                                                 |
| `type`                                                         | `video` | `shorts` | `stream`       | yes                                                                 |
| `thumbnailUrl`                                                 | str                                 | yes                                                                 |
| `input` `fromYTUrl` `order`                                    | str/int                             | yes (provenance: source query/URL, origin URL, index)               |
| `text`                                                         | str                                 | yes (description)                                                   |
| `descriptionLinks`                                             | `[{ url, text }]`                   | yes                                                                 |
| `hashtags`                                                     | `string[]`                          | yes                                                                 |
| `likes` `commentsCount` `commentsTurnedOff`                    | int/bool                            | partial (often `null` on the video path — see `commentsCount` note) |
| `location`                                                     | str                                 | when present                                                        |
| `collaborators`                                                | `[{ name, username, url }]`         | when present                                                        |
| `translatedTitle` `translatedText`                             | str                                 | when `subtitlesLanguage != "en"`                                    |
| `subtitles`                                                    | `[{ srtUrl, type, language, srt }]` | when `downloadSubtitles`                                            |
| `isMembersOnly` `isPaidContent`                                | bool                                | yes (default `false`)                                               |
| `isMonetized` `isAgeRestricted`                                | bool                                | best-effort (`null` when unknown)                                   |
| `channelName` `channelUrl` `channelUsername` `channelId`       | str                                 | yes                                                                 |
| `numberOfSubscribers` `channelTotalVideos` `channelTotalViews` | int                                 | channel/deep fields                                                 |
| `channelDescription` `channelLocation` `channelJoinedDate`     | str                                 | channel About panel                                                 |
| `isChannelVerified` `channelBannerUrl` `channelAvatarUrl`      | bool/str                            | channel fields                                                      |


### Comments scraper — input (`YouTubeCommentsInput`)


| Field               | Type / values                   | Default          | Notes                                                               |
| ------------------- | ------------------------------- | ---------------- | ------------------------------------------------------------------- |
| `startUrls`         | `[{ "url": string }]`           | `[]`             | Video URLs only (non-video URLs skipped).                           |
| `maxComments`       | `int ≥ 1`                       | `1`              | Counts **every** emitted item (top-level comments **and** replies). |
| `sortCommentsBy`    | `TOP_COMMENTS` | `NEWEST_FIRST` | `"NEWEST_FIRST"` |                                                                     |
| `oldestCommentDate` | `string` (date)                 | `null`           | Forces newest-first and stops at the cutoff.                        |


### Comments scraper — output (`CommentItem`)


| Field                                    | Type                | Notes                                         |
| ---------------------------------------- | ------------------- | --------------------------------------------- |
| `cid`                                    | str                 | Comment id.                                   |
| `comment`                                | str                 | Text.                                         |
| `author`                                 | str                 |                                               |
| `type`                                   | `comment` | `reply` |                                               |
| `replyToCid`                             | str                 | Parent `cid` (replies only).                  |
| `replyCount`                             | int                 | Replies under a top-level comment.            |
| `voteCount`                              | int                 | Likes.                                        |
| `authorIsChannelOwner` `hasCreatorHeart` | bool                |                                               |
| `publishedTimeText`                      | str                 | Relative time ("2 days ago").                 |
| `videoId` `pageUrl` `title`              | str                 | Source video.                                 |
| `commentsCount`                          | int                 | Authoritative total from the comments header. |


---

## Configuration

- **Proxy** — required for real runs; configured via `app/utils/proxy.py`
(residential rotating gateway env vars). With no proxy configured the fetchers
fall back to one-shot direct `AsyncFetcher` calls (fine for local tests, not
for production).
- **Concurrency** — `scraper._FANOUT_CONCURRENCY` (16). The gateway handled 64
parallel flows with zero failures in a ramp probe, so this leaves headroom.
- **Rotation** — `innertube._BLOCK_STATUSES` (`403`, `429`) and
`_MAX_ROTATIONS` (3).

---

## Testing

- **Offline unit tests** (no network) — run these on every change:
  ```bash
  cd surfsense_backend
  .venv/Scripts/python.exe -m pytest tests/unit/scrapers/youtube/
  ```
  - `test_parsers.py` — parser/normalization + filter-protobuf + URL-resolver
  cases against hand-built and (if present) captured real fixtures.
  - `test_fetch_resilience.py` — deterministic rotate-on-block (`429`/error →
  rotate → `200`, exhaustion, no-rotate on `404`, stealthy fallback) and the
  `fan_out` no-session-leak-on-early-stop guarantee, all with stubbed sessions.
- **Live functional harness** — `scripts/e2e_youtube_scraper.py` (needs live
network + optional proxy creds). Exercises video/search/channel/comments/
location/collaborators/translation end to end, and **regenerates the offline
fixtures** into `tests/unit/scrapers/youtube/fixtures/`:
  ```bash
  .venv/Scripts/python.exe scripts/e2e_youtube_scraper.py
  ```

---

## Extending it

- **Add an output field** → populate it in the relevant `parsers.py` function
and add it to `schemas.py`. Because outputs are `extra="allow"`, forgetting the
schema line won't drop the value, but declaring it documents the contract.
- **Add a URL kind** → extend `url_resolver.resolve_url` + add a `_*_flow` in
`scraper.py` and a branch in `_dispatch`.
- **Add a search filter** → add the field to `YouTubeScrapeInput` and encode it
in `search_filters.build_search_params` (verify byte-for-byte against a real
YouTube `sp=` token in the unit test).

### Known ceilings (grep `ponytail:` in the source for the live list)

- Hashtag scraping returns a single feed page (~20-35 videos); YouTube exposes
no continuation for the hashtag feed through this path. Upgrade path for more
depth: fall back to the `#tag` search route.
- Playlist video ids are paged sequentially (each continuation depends on the
last), then the per-video watch-page fetches run concurrently via `fan_out`
(~150 videos ≈ 70s). Because resolution is fanned out, items stream back in
completion order, not playlist order — sort by the `order` field to restore it.
- `oldestPostDate` / `oldestCommentDate` cutoffs are day-accurate at best
(channel/list pages only expose coarse relative times like "2 years ago").
- Keyless-vs-keyed InnerTube retry does one extra request on the keyed path
instead of remembering which worked.
- Video-path `commentsCount` (see above).

