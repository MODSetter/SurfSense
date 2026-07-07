# Reddit scraper (anonymous, no browser)

Platform-native Reddit scraper (anonymous, no browser). Standalone
module: it depends only on `app.utils.proxy` + `scrapling` and exposes a stable
public API. It is **not** wired into routes, `connector_service.py`, ingestion,
or Celery — integration later is a thin `reddit_routes.py` + one `include_router`
line, identical to the `youtube` / `google_maps` siblings.

## Approach

Reddit deprecated **cold** unauthenticated `.json` (r/modnews, May 2026): a bare
anonymous GET to `/…/.json` now 403s. What still works — and what maintained
anonymous scrapers (e.g. yt-dlp) now do — is:

> Bootstrap an anonymous session cookie (`loid`) with one plain HTTP GET to
> `www.reddit.com/svc/shreddit/<slug>`, then GET
> `www.reddit.com/<path>/.json?raw_json=1` through that same
> Chrome-impersonated, sticky-IP session. Rotate the residential IP + re-warm on
> block.

`loid` is Reddit's equivalent of the Google Maps scraper's `NID`: an anonymous,
logged-out id that unlocks the public API. **No browser, no Chromium, no
`solve_cloudflare`** — this collapses Reddit onto the cheap HTTP tier the
siblings already use. Confirmed live 2026-07-04 through a residential proxy (see
`scripts/e2e_reddit_scraper.py` step 0): `svc/shreddit` warm-up → 200 + `loid`
(with `old.reddit` as a fallback), then sequential `.json` fetches → 200.

## Anonymous only — no authentication, ever

No OAuth, no login, no `reddit_session` account cookie, no Devvit. The only
cookie held is the anonymous `loid`. There is **no** authenticate option in the
input surface or the fetch layer, by design. A persistent block after IP
rotation surfaces as `RedditAccessBlockedError` (mirrors google_maps'
`SignInRequiredError`) rather than a silent empty result.

## Module map

| File | Responsibility |
|---|---|
| `__init__.py` | Public exports: `RedditScrapeInput`, `RedditItem`, `iter_reddit`, `scrape_reddit`, `RedditAccessBlockedError`. |
| `schemas.py` | `RedditScrapeInput` (`extra="allow"`, no auth fields) + single flat `RedditItem` keyed by `dataType` + `StartUrl`. |
| `fetch.py` | The core. Rotate-on-block sticky `_RotatingSession` + `_current_session` ContextVar + `warm_session` (loid) + `fetch_json`. No browser imports. |
| `url_resolver.py` | Classify a Reddit URL → `post`/`subreddit`/`user`/`search`; non-Reddit → `None`. |
| `parsers.py` | Pure JSON→item mapping (`parse_post`, `parse_comment`, `parse_community`, `flatten_comments`, `children`/`after`). I/O-free. |
| `scraper.py` | Orchestrator: `_post_flow`/`_subreddit_flow`/`_user_flow`/`_search_flow`, `_paginate_listing`, `_dispatch`, `fan_out`, `iter_reddit`, `scrape_reddit`. |

## How it works

1. `iter_reddit` resolves `startUrls` (or builds a search per `searches` entry)
   and fans them out on a pool of warm proxy sessions (`fan_out`, 16-way). Each
   worker opens one sticky-IP session and warms `loid` once, reusing it across
   the sequential targets it pulls.
2. Each flow pages its listing via the `after` cursor (`_paginate_listing`),
   filtering by child `kind`, the NSFW gate, and `postDateLimit`.
3. `fetch_json` warms `loid` on first use, rotates the IP + re-warms on 403,
   backs off on 429, returns `None` on 404, and paces each sticky IP to ~1 req/s
   to stay under Reddit's per-IP rate limit.
4. Parsers map raw `.json` things to flat `RedditItem`s; the orchestrator stamps
   `scrapedAt` and applies caps as request-time policy.

## Testing

- Offline unit tests: `tests/unit/platforms/reddit/` — `test_skeleton.py`
  (schema + URL resolver), `test_parsers.py` (fixture-pinned mapping),
  `test_fetch_resilience.py` (warm / rotate / backoff loop with fake sessions,
  no network).
- Live e2e (needs network + residential proxy): `scripts/e2e_reddit_scraper.py`
  — step 0 is the go/no-go `loid` probe; later steps exercise the flows and dump
  trimmed fixtures into `tests/unit/platforms/reddit/fixtures/`.

```bash
cd surfsense_backend
.venv/bin/python -m pytest tests/unit/platforms/reddit/
.venv/bin/python scripts/e2e_reddit_scraper.py   # live; regenerates fixtures
```

## TODO / out of scope (v1)

- Sticky-IP provider support: the fetch layer assumes a sticky exit IP per
  session (the `loid` binds to it). The `dataimpulse` provider does not yet emit
  a sticky `__sid.<id>` username suffix — add it (proxy layer) before high-volume
  production use.
- `/api/morechildren` deep-comment expansion — `more` stubs terminate the tree
  walk today.
- Routes / `connector_service.py` / ingestion / Celery wiring.
- RSS degraded-mode path (documented, not implemented).
