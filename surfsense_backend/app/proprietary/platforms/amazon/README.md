# Amazon Product Scraper

Current status: product details, search and category discovery, offers, sellers,
best-seller rankings, on-page reviews, localized delivery sessions, and product
variants are implemented. The `amazon.scrape` capability exposes the scraper
with per-product billing and a hard per-run result ceiling.

## Scope

The scraper reads public pages available to anonymous visitors. It does not log
in, use account cookies, or retrieve account-gated content. Delivery
localization uses an anonymous session cookie pinned to the same proxy exit.

Deep review pagination currently requires an account on Amazon and is therefore
out of scope. Reviews embedded in a public product page are returned in
`productPageReviews` and `productPageReviewsFromOtherCountries`.

## Architecture

- `schemas.py` defines the stable input, product, and error models.
- `url_resolver.py` classifies product, search, best-sellers, and shortened URLs.
- `fetch.py` owns proxy-aware HTTP access, block detection, retries, and
  anonymous location sessions.
- `parsers.py` contains pure, defensive HTML parsers.
- `scraper.py` coordinates discovery, enrichment, concurrency, limits, and
  in-stream errors.

## Implementation progress

- Done: public product detail parsing and shortened-link dispatch.
- Done: search/category paging with card-only and detailed modes.
- Done: public offers and seller enrichment.
- Done: best-seller rankings and product-page reviews.
- Done: anonymous localized delivery sessions on sticky proxy exits.
- Done: variant expansion, variant prices, capability registration, and billing.

## Verification

Offline fixtures cover every parser and flow:

```bash
cd surfsense_backend
uv run pytest tests/unit/platforms/amazon tests/unit/capabilities/amazon
```

The manual live check requires proxy credentials:

```bash
uv run python scripts/e2e_amazon_scraper.py
```
