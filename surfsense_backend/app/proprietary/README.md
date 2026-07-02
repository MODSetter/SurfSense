# `app.proprietary` — non-Apache-2 license boundary

Everything in this directory tree is licensed **separately** from the rest of
SurfSense (which is Apache-2.0), under the **Business Source License 1.1** —
see [`LICENSE`](./LICENSE). In short: source-available; production use is
permitted (including self-hosting the whole app) *except* offering it to third
parties as a commercial product or hosted/managed service; each released
version converts to Apache-2.0 four years after its release.

## Why this exists

This package holds the product moat:

- the in-house **undetectable web crawler** (Scrapling tiers + stealth/captcha
  hardening), and
- (future) **platform-specific actors** that scrape/extract structured data from
  individual platforms.

Keeping it in one clearly-named directory makes the license boundary
unambiguous: a single rule — *everything under `app/proprietary/**` is not
Apache-2.0* — instead of per-file headers scattered across the tree.

## Layout

- `web_crawler/` — the Scrapling-based crawler engine. Public API:
  `WebCrawlerConnector`, `CrawlOutcome`, `CrawlOutcomeStatus`
  (`from app.proprietary.web_crawler import ...`).
- `platforms/` — (future, Phase 8) platform-specific actors; scaffolded/empty.

## Rules

- **Do not** add Apache-2.0-intended code here.
- Apache-2.0 code elsewhere **may import from** this package (the indexer and the
  chat `scrape_webpage` tools do); that does not move them under this license.
- Depend only on the public API exported from each subpackage's `__init__`, not
  on internal modules, so the boundary stays clean and swappable.
- **Boundary test:** put code here only if it is used *exclusively* by the moat.
  Generic infrastructure that Apache-2 features also depend on stays Apache-2
  even when the crawler uses it too. Example: `app/utils/proxy/` (provider
  abstraction, registry, `CustomProxyProvider` + rotation — a thin wrapper over
  Scrapling's public `ProxyRotator`) is shared with the YouTube/transcript and
  chat features, so it stays Apache-2; only the crawl-ladder-coupled
  rotation-retry orchestration (`web_crawler/connector.py::_run_tier_with_proxy_retry`)
  lives here.
