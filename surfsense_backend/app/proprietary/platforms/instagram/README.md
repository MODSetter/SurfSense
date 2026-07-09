# Instagram scraper (anonymous, no browser)

Platform-native Instagram scraper (anonymous, no browser). Standalone module: it
depends only on `app.utils.proxy` + `scrapling` and exposes a stable public API.
Its input/output surface is a **reference-compatible** mirror of the public
Instagram scraper actor spec (same `resultsType` / `directUrls` / camelCase field
names, additive `extra="allow"` parity), so callers written against that surface
work unchanged. It is **not** wired into ingestion or Celery — the capability
layer under `app/capabilities/instagram/` is what turns these primitives into
REST + agent + MCP surfaces.

## Approach

Instagram's public web app exposes anonymous, logged-out JSON behind a handful of
`www.instagram.com` endpoints once a session carries an anonymous `csrftoken` +
`mid` cookie pair and the `x-ig-app-id` web header:

> Warm an anonymous session with one plain GET to `www.instagram.com/` (mints
> `csrftoken` + `mid`), then GET the web JSON endpoints through that same
> Chrome-impersonated, sticky-IP session. Rotate the residential IP + re-warm on
> a login wall (401/403), back off on 429.

Endpoints used (anonymous web tier only):

| Flow | Endpoint |
|---|---|
| profile / posts / reels | `api/v1/users/web_profile_info/?username=…` |
| comments | `p/<shortcode>/?__a=1&__d=dis` |
| hashtag | `api/v1/tags/web_info/?tag_name=…` |
| place | `api/v1/locations/web_info/?location_id=…` |
| discovery search | `web/search/topsearch/?query=…` |

**No browser, no Chromium, no `solve_cloudflare`** — this stays on the cheap HTTP
tier the sibling scrapers already use.

## Anonymous only — no authentication, ever

No login, no `sessionid` account cookie, no app password. The only cookies held
are the anonymous `csrftoken` / `mid` minted by the warm-up. There is **no**
authenticate option in the input surface or the fetch layer, by design. A
persistent block after IP rotation surfaces as `InstagramAccessBlockedError`
(mirrors Reddit's `RedditAccessBlockedError`) rather than a silent empty result,
so the capability layer can map it to a `403 INSTAGRAM_ACCESS_BLOCKED`.

## Module map

| File | Responsibility |
|---|---|
| `__init__.py` | Public exports: `InstagramScrapeInput`, item models, `iter_instagram`, `scrape_instagram`, `InstagramAccessBlockedError`. |
| `schemas.py` | `InstagramScrapeInput` (`extra="allow"`, no auth fields) + optional-field item models (`InstagramMediaItem`, `InstagramComment`, `InstagramProfile`, `InstagramHashtag`, `InstagramPlace`) each with `to_output()`. |
| `fetch.py` | The core. Rotate-on-block sticky `_RotatingSession` + `_current_session` ContextVar + `warm_session` (csrftoken/mid) + `fetch_json`. No browser imports. |
| `url_resolver.py` | Classify an Instagram URL → `profile`/`post`/`reel`/`hashtag`/`place`; non-Instagram → `None`. Strips `_u/`, `profilecard/`; story → profile. |
| `parsers.py` | Pure JSON→dict mapping (`parse_media`, `parse_comment`, `parse_profile`, `parse_hashtag`, `parse_place`, `_edges`). I/O-free. |
| `scraper.py` | Orchestrator: `_media_flow`/`_comments_flow`/`_details_flow`/`_discover`, `_targets`, `fan_out`, `iter_instagram`, `scrape_instagram`. |

## How it works

1. `iter_instagram` resolves `directUrls` (or runs a discovery `search` per the
   comma-split queries) into targets and fans them out on a pool of warm proxy
   sessions (`fan_out`, 8-way; 4-way for comments). Each worker opens one
   sticky-IP session and warms `csrftoken`/`mid` once, reusing it across the
   sequential targets it pulls.
2. `resultsType` selects the flow: `posts`/`reels`/`mentions` → media feeds,
   `comments` → per-post comment items, `details` → profile/hashtag/place
   metadata. Media items de-dupe by `id` across targets.
3. `fetch_json` warms the session on first use, rotates the IP + re-warms on
   401/403, backs off on 429, returns `None` on 404.
4. Parsers map raw web JSON to flat dicts; the orchestrator stamps `scrapedAt`
   and applies `resultsLimit` / `onlyPostsNewerThan` as request-time policy.

## Observed limits & calibration caveats

- Anonymous web JSON is rate-limited per IP; the sticky-session pool keeps each
  IP's request rate modest but a hot pool will still hit login walls — that's the
  `InstagramAccessBlockedError` path, not a bug.
- `likesCount` is frequently withheld on anonymous responses (surfaces as `-1` or
  absent upstream); treat it as best-effort.
- Comments on the anonymous media page cap at ~50/post; deeper paging needs the
  GraphQL cursor endpoint whose doc-id drifts (see the `ponytail:` note in
  `scraper.py`/`fetch.py`).
- The `$3.50 / 1k items` default meter assumes the proxy-bytes-per-item measured
  on the reference targets; re-measure with the `references/` scale harness before
  high-volume production use.

## Testing

- Offline unit tests: `tests/unit/platforms/instagram/` — `test_skeleton.py`
  (schema + URL resolver), `test_parsers.py` (fixture-pinned mapping),
  `test_fetch_resilience.py` (warm / rotate / backoff loop with fake sessions, no
  network), `test_budget.py` (fair-share caps + de-dup).
- Live e2e (needs network + residential proxy): `scripts/e2e_instagram_scraper.py`
  — step 0 is the go/no-go cookie probe; later steps exercise the flows and dump
  trimmed, PII-anonymized fixtures.

```bash
cd surfsense_backend
.venv/bin/python -m pytest tests/unit/platforms/instagram/
.venv/bin/python scripts/e2e_instagram_scraper.py   # live; regenerates fixtures
```

## TODO / out of scope (v1)

- Deep feed pagination past the first web page of media (GraphQL cursor doc-id).
- Deep comment pagination past the ~50/post embedded ceiling.
- Sticky-IP provider parity (same `__sid` caveat as the Reddit sibling).
