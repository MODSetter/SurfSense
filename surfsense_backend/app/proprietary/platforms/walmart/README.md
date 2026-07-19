# Walmart Scraper

Two verbs read Walmart's public, anonymous pages: `walmart.scrape` (products +
search/category/browse listings, per-product billing) and `walmart.reviews`
(deep paginated reviews, per-review billing).

## Scope

The scraper reads public pages available to anonymous visitors — no login, no
account cookies. Data is extracted from the Next.js `__NEXT_DATA__` JSON blob
embedded in each page (with an `__APP_DATA__` fallback), not from the rendered
DOM, because Walmart obfuscates CSS classes and A/B-tests layout constantly.

`walmart.scrape` returns a free sample of on-page reviews (rating distribution,
aspects, top reviews) under `reviewsSample`. `walmart.reviews` fetches the full
review history from the public `/reviews/product/{usItemId}` page, which
robots.txt permits (unlike `/search`).

## Architecture

- `schemas.py` defines the stable input, product, review, and error models.
- `url_resolver.py` classifies product (`/ip/`) vs listing (`/search`, `/cp/`,
  `/browse/`) URLs and extracts the numeric `usItemId`.
- `next_data.py` extracts and navigates the hidden Next.js JSON state.
- `fetch.py` owns proxy-aware HTTP access (US-pinned), block detection, and
  retries.
- `parsers.py` contains pure, defensive JSON parsers.
- `scraper.py` coordinates discovery, enrichment, pagination, concurrency,
  limits, and in-stream error items.

## Anti-bot

Walmart runs Akamai (edge/TLS) + PerimeterX/HUMAN (behavioral JS). Requests go
through US residential proxies with TLS-impersonated headers; blocked responses
(body markers, `412`/`429`/`503`, or the `200`-OK CAPTCHA body) rotate to a
fresh proxy exit.

Known ceilings and upgrade paths (see `fetch.py` / `scraper.py` `ponytail:`
notes): reviews page at 10/page; search capped at Walmart's 25-page limit;
session warming (seed `_px3`/`_pxhd` on a sticky exit) is the next lever if
block rates on the SSR pages climb, and the `/orchestra/*` GraphQL API is
deliberately avoided (rotating persisted-query hashes make it brittle).

## Verification

Offline fixtures cover the parsers and both flows:

    uv run pytest tests/unit/platforms/walmart/

A manual live check (requires network + residential proxy):

    uv run python scripts/e2e_walmart_scraper.py
