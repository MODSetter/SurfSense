# `app.proprietary` — non-Apache-2 license boundary

Everything in this directory tree is licensed **separately** from the rest of
SurfSense (which is Apache-2.0). See [`LICENSE`](./LICENSE).

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
